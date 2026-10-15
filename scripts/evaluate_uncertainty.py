#!/usr/bin/env python
"""Does the classifier's uncertainty actually flag its mistakes? Measured on real held-out crops.

* Thresholds are chosen on the **calibration** split (never on test) and then evaluated on the **test** split (run once).
* Signals per tooth crop: normalised predictive entropy (1 pass) and flip-TTA disagreement (original vs horizontally flipped crop;
  a Jensen-Shannon divergence normalised by log 2, so it spans 0..1 like entropy). TTA is NOT an ensemble.
* Reported: accuracy, expected calibration error (ECE, 15 bins, top-label), multiclass Brier score, AUROC of each signal for
  detecting errors, the chosen thresholds and the error rate inside / outside the flagged set.
* Temperature scaling is fitted on the calibration split and reported (ECE before/after on test) but NOT applied in the app: the
  displayed class scores remain uncalibrated model scores.

Writes Data/reports/uncertainty_evaluation.json/.md and Data/reports/uncertainty_thresholds.json (used by the pipeline).
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from dentexmodel.config import get_settings
from dentexmodel.errors import DentaMindError
from dentexmodel.inference.registry import active_model
from dentexmodel.training import trainers as T
from dentexmodel.uncertainty.measures import entropy as entropy_fn
from dentexmodel.utils.logging_utils import setup_logging
from evaluate_model import items_for_split


def auroc(score, positive) -> float | None:
    """P(score of a random positive > score of a random negative), ties count half. positive = misclassified."""
    s, y = np.asarray(score, float), np.asarray(positive, bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return None
    ranks = np.argsort(np.argsort(np.concatenate([pos, neg]))) + 1.0
    # average ranks for ties
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):
        m = allv == v
        ranks[m] = ranks[m].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def ece(probs, labels, bins=15):
    conf, pred = probs.max(1), probs.argmax(1)
    acc = (pred == labels).astype(float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(acc[m].mean() - conf[m].mean())
    return float(total)


def brier(probs, labels):
    onehot = np.eye(probs.shape[1])[labels]
    return float(((probs - onehot) ** 2).sum(1).mean())


def js_norm(p, q):
    m = (p + q) / 2
    h = lambda a: -(a * np.log(a + 1e-12)).sum(-1)
    return np.maximum(h(m) - (h(p) + h(q)) / 2, 0) / np.log(2)


def collect(settings, info, split, torch, tv, device):
    items = items_for_split(settings, "classification", split, None)
    size = int(info.metadata.get("image_size", 224))
    X, y = T._crops(settings, items, size)
    names = info.metadata["class_names"]
    idx = {c: i for i, c in enumerate(names)}
    keep = [i for i, c in enumerate(y) if c in idx]
    X = np.stack([X[i] for i in keep])
    labels = np.array([idx[y[i]] for i in keep])
    model = getattr(tv.models, info.architecture)(weights=None)
    model.fc = torch.nn.Linear(model.fc.in_features, len(names))
    model.load_state_dict(torch.load(info.path, map_location=device, weights_only=True), strict=True)
    model.to(device).eval()

    def logits(arr):
        out = []
        with torch.no_grad():
            for i in range(0, len(arr), 64):
                out.append(model(T._norm(torch.from_numpy(np.ascontiguousarray(arr[i:i + 64])), device, torch)).float().cpu().numpy())
        return np.concatenate(out)

    return logits(X), logits(X[:, :, ::-1]), labels, names


def softmax(z, t=1.0):
    z = z / t
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)


def fit_temperature(logit, labels):
    best, bt = 1e9, 1.0
    for t in np.arange(0.5, 5.01, 0.05):
        p = softmax(logit, t)
        nll = -np.log(p[np.arange(len(labels)), labels] + 1e-12).mean()
        if nll < best:
            best, bt = nll, float(t)
    return bt


def signals(l1, l2):
    p1, p2 = softmax(l1), softmax(l2)
    return p1, entropy_fn(p1), js_norm(p1, p2)


def summarize(l1, l2, labels):
    p, ent, jsd = signals(l1, l2)
    err = p.argmax(1) != labels
    return {"n": int(len(labels)), "accuracy": float(1 - err.mean()), "ece": ece(p, labels), "brier": brier(p, labels),
            "auroc_entropy_for_errors": auroc(ent, err), "auroc_tta_disagreement_for_errors": auroc(jsd, err),
            "auroc_one_minus_maxprob_for_errors": auroc(1 - p.max(1), err),
            "mean_entropy_correct": float(ent[~err].mean()), "mean_entropy_wrong": float(ent[err].mean()) if err.any() else None}, p, ent, jsd, err


def youden_threshold(score, err):
    best, bt = -1, None
    for t in np.unique(score):
        flag = score >= t
        tpr = flag[err].mean() if err.any() else 0
        fpr = flag[~err].mean() if (~err).any() else 0
        if tpr - fpr > best:
            best, bt = tpr - fpr, float(t)
    return bt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--final-test", action="store_true", help="also evaluate on the locked test split (once, authorized, recorded)")
    ap.add_argument("--authorized-by", default="", help="with --final-test: name of the person authorizing it (recorded)")
    ap.add_argument("--reason", default="", help="with --final-test: why this is the final evaluation (recorded, >= 20 characters)")
    ap.add_argument("--reproduce", action="store_true", help="with --final-test: re-run an already-recorded test evaluation into --out-dir")
    ap.add_argument("--out-dir", default=None, help="write the reports here instead of Data/reports")
    a = ap.parse_args()
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    info = active_model(s, "classification")
    from dentexmodel.evaluation import test_ledger as TL
    test_ctx, kind = None, ("reproduction" if a.reproduce else "uncertainty")
    if a.final_test:
        try:
            test_ctx = TL.authorize(s, info, kind, a.authorized_by, a.reason, a.out_dir)
        except DentaMindError as exc:
            print("Refusing test-split evaluation:", exc.message, exc.hint or "")
            return 2
    rep = Path(a.out_dir) if a.out_dir else s.data_root / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    old = rep / "uncertainty_evaluation.json"
    if old.is_file() and not a.out_dir:
        # never lose a historical test result: record it in the ledger and keep the previous report next to the new one
        TL.ensure_ledger(s)
        prev = json.loads(old.read_text(encoding="utf-8"))
        if prev.get("test_split"):
            stamp = str(prev.get("generated", "unknown"))[:19].replace(":", "")
            (rep / f"uncertainty_evaluation.{stamp}.json").write_text(old.read_text(encoding="utf-8"), encoding="utf-8")
    torch, tv = T._require_torch()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = {"generated": datetime.now(timezone.utc).isoformat(), "model_version": info.version, "classes": info.metadata["class_names"]}
    l1c, l2c, yc, names = collect(s, info, "calibration", torch, tv, device)
    cal, pc, entc, jsc, errc = summarize(l1c, l2c, yc)
    temp = fit_temperature(l1c, yc)
    # review flag = normalised entropy >= Youden-optimal threshold (error detection on calibration crops);
    # "unstable under flip" flag = TTA disagreement above the 90th percentile of calibration crops (a rare-event flag, reported separately)
    thr = {"entropy": youden_threshold(entc, errc), "tta_disagreement": float(np.percentile(jsc, 90))}
    out["calibration_split"] = {**cal, "temperature_fit": temp, "thresholds_chosen_here": thr,
                                "ece_after_temperature": ece(softmax(l1c, temp), yc), "brier_after_temperature": brier(softmax(l1c, temp), yc)}
    if a.final_test:
        l1t, l2t, yt, _ = collect(s, info, "test", torch, tv, device)
        tst, pt, entt, jst, errt = summarize(l1t, l2t, yt)
        flag = entt >= thr["entropy"]
        unstable = jst >= thr["tta_disagreement"]
        out["test_split"] = {**tst, "ece_after_temperature_fitted_on_calibration": ece(softmax(l1t, temp), yt),
                             "brier_after_temperature": brier(softmax(l1t, temp), yt),
                             "flagged_for_review_fraction": float(flag.mean()),
                             "error_rate_flagged": float(errt[flag].mean()) if flag.any() else None,
                             "error_rate_not_flagged": float(errt[~flag].mean()) if (~flag).any() else None,
                             "errors_caught_fraction": float(flag[errt].mean()) if errt.any() else None,
                             "tta_unstable_fraction": float(unstable.mean()),
                             "error_rate_tta_unstable": float(errt[unstable].mean()) if unstable.any() else None,
                             "error_rate_tta_stable": float(errt[~unstable].mean()) if (~unstable).any() else None}
    out["interpretation"] = ("Thresholds are provisional: chosen by Youden's J on the calibration split, one seed, one dataset. Scores shown in the app "
                             "remain uncalibrated model scores; temperature scaling is reported here but not applied.")
    out["checkpoint_sha256"] = test_ctx["sha"] if test_ctx else TL.file_sha256(info.path)
    if test_ctx:
        out["test_set_status"] = TL.test_status_for_report(test_ctx)
        out["authorized_by"], out["authorization_reason"] = a.authorized_by.strip(), a.reason.strip()
    (rep / "uncertainty_evaluation.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    if test_ctx:
        e = TL.record(s, info, kind, test_ctx, a.authorized_by, a.reason, out["test_split"], out["test_split"].get("n"),
                      str(rep / "uncertainty_evaluation.json"), "scripts/evaluate_uncertainty.py")
        print(f"recorded in the test-set ledger as entry {e['seq']} ({kind})")
    (rep / "uncertainty_thresholds.json").write_text(json.dumps({
        "provisional": True, "model_version": info.version, "chosen_on": "calibration split", "review_if_any": {
            "normalised_entropy_ge": thr["entropy"]}, "unstable_under_flip_if": {"tta_disagreement_ge": thr["tta_disagreement"]},
        "generated": out["generated"]}, indent=1), encoding="utf-8")
    f = lambda v: "n/a" if v is None else f"{v:.3f}"
    lines = ["# Uncertainty evaluation (finding classifier)", "", f"Model `{info.version}`. Generated {out['generated']}.", "",
             "| Split | n | Accuracy | ECE | Brier | AUROC entropy->error | AUROC TTA disagreement->error |", "|---|---:|---:|---:|---:|---:|---:|"]
    for nm, d in (("calibration", out["calibration_split"]), ("test", out.get("test_split"))):
        if d:
            lines.append(f"| {nm} | {d['n']} | {f(d['accuracy'])} | {f(d['ece'])} | {f(d['brier'])} | {f(d['auroc_entropy_for_errors'])} | {f(d['auroc_tta_disagreement_for_errors'])} |")
    c = out["calibration_split"]
    lines += ["", f"Temperature fitted on calibration: {c['temperature_fit']:.2f} (calibration ECE {f(c['ece'])} -> {f(c['ece_after_temperature'])}).",
              f"Provisional thresholds (calibration split): review if normalised entropy >= {f(thr['entropy'])}; 'unstable under flip' if TTA disagreement >= {f(thr['tta_disagreement'])} (90th percentile)."]
    if "test_split" in out:
        t = out["test_split"]
        lines += ["", f"On the test split the flagged set is {t['flagged_for_review_fraction']:.1%} of crops; error rate flagged {f(t['error_rate_flagged'])} vs "
                  f"not flagged {f(t['error_rate_not_flagged'])}; {f(t['errors_caught_fraction'])} of all errors are flagged. "
                  f"TTA-unstable crops: {t['tta_unstable_fraction']:.1%} (error rate {f(t['error_rate_tta_unstable'])} vs {f(t['error_rate_tta_stable'])} for stable). "
                  f"ECE on test: {f(t['ece'])} raw, {f(t['ece_after_temperature_fitted_on_calibration'])} after temperature scaling (not applied in the app)."]
    lines += ["", out["interpretation"], ""]
    (rep / "uncertainty_evaluation.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
