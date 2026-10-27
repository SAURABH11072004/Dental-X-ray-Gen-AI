#!/usr/bin/env python
"""Offline abstention-rule experiment for the finding classifier (does NOT change production).

Question: can a different rejection rule reduce "No reliable class candidate" without making accepted predictions less reliable?

Production baseline (backend/services/pipeline.py, unchanged): abstain if normalised entropy H(p) >= 0.39660 (chosen earlier by
Youden's J on the calibration split; Data/reports/uncertainty_thresholds.json). Flip disagreement and detection flags never abstain.

Data and leakage control
* TUNING split  = calibration (the split the production threshold was chosen on). Rules are ranked and the candidate is picked here.
* CONFIRMATION  = validation (never used to pick the rule). Caveat: validation picked the classifier's best epoch, so its
  absolute numbers are slightly optimistic for every rule alike.
* The test split is never read (the script refuses it).
* Populations per split:
    det  - ground-truth finding boxes matched one-to-one to a production detector box (IoU >= 0.5), classified from the DETECTOR crop
           exactly as the app does (primary population: this is what users see);
    gt   - the same findings classified from the ground-truth box (secondary);
    unlabelled - detector boxes that match no finding but do match a fully annotated tooth of the pixel-identical tooth-annotation
           twin. They have NO finding label; they are NOT assumed healthy and are NEVER counted as false positives. Only the share
           that a rule names a class for is reported, as a warning signal.

Acceptance criteria (fixed before the run; vs the production baseline on the same split and population "det")
    C1 coverage gain >= +0.10 on calibration and >= +0.05 on validation
    C2 risk (error rate among accepted) increase <= +0.02 on both splits
    C3 Deep Caries and Periapical Lesion: precision drop <= 0.05 and end-to-end recall not lower, on both splits
    C4 macro-F1 (end-to-end, abstentions count as misses) not lower than baseline - 0.01, on both splits
    C5 validation: bootstrap (2000 resamples of crops) 95% upper bound of the risk increase <= 0.05
  Among rules passing C1-C4 on calibration, the one with the highest calibration coverage is the candidate; it is recommended only if it
  also passes C1-C5 on validation. Otherwise the recommendation is to keep the baseline.

Usage
    python scripts/abstention_threshold_experiment.py collect     # GPU; caches per-crop probabilities (refuses to overwrite)
    python scripts/abstention_threshold_experiment.py analyze     # CPU; writes report.json / report.md (re-runnable)
Outputs: docs/audit_evidence/ml_improvement/abstention/ (separate from production configuration).
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from dentexmodel.config import get_settings
from dentexmodel.uncertainty.abstention import Rule, acceptance_rate, selective_metrics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit_evidence" / "ml_improvement" / "abstention"
SPLITS = ("calibration", "val")             # tuning, confirmation; test is never read
IOU = 0.5
GRID = {"entropy": [0.30, 0.35, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.01],
        "max_prob": [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85],
        "margin": [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]}
CRIT = {"coverage_gain_cal": 0.10, "coverage_gain_val": 0.05, "risk_increase_max": 0.02, "minority_precision_drop_max": 0.05,
        "macro_f1_drop_max": 0.01, "bootstrap_risk_ub_max": 0.05, "bootstrap_n": 2000, "minority": ["Deep Caries", "Periapical Lesion"]}


def production_threshold(s) -> float:
    d = json.loads((s.data_root / "reports" / "uncertainty_thresholds.json").read_text(encoding="utf-8"))
    return float(d["review_if_any"]["normalised_entropy_ge"])


# ------------------------------------------------------------------------------------------------------------------- collect
def collect(split: str) -> dict:
    if split not in SPLITS:
        raise SystemExit(f"refusing split '{split}': this experiment only reads {SPLITS}")
    from PIL import Image
    from dentexmodel.data.coco import annotation_finding
    from dentexmodel.data.dataset import DatasetService
    from dentexmodel.data.preprocess import load_gray
    from dentexmodel.data.splits import load_split_file
    from dentexmodel.evaluation.test_ledger import file_sha256
    from dentexmodel.inference import torch_models as TM
    from dentexmodel.inference.registry import active_model
    from dentexmodel.training import trainers as Tr
    from dentexmodel.training.trainers import assignments_sha
    from evaluate_end_to_end import match, xyxy

    s = get_settings()
    TM.require_torch()
    det_info, cls_info = active_model(s, "detection"), active_model(s, "classification")
    names = cls_info.metadata["class_names"]
    idx = {c: i for i, c in enumerate(names)}
    size = int(cls_info.metadata.get("image_size", 224))
    svc = DatasetService(s)
    assign = load_split_file(s.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = svc.manifest("main")
    qed = [r for r in rows if r.annotation_status == "annotated" and not r.is_test_data and r.annotation_level == Tr.TASK_LEVEL["classification"]
           and assign.get(r.image_id) == split]
    qe_by_hash = {}
    for r in rows:
        if r.annotation_status == "annotated" and r.annotation_level == "quadrant_enumeration" and r.content_hash:
            qe_by_hash.setdefault(r.content_hash, r)
    twins = {h: r for h, r in qe_by_hash.items() if h in {q.content_hash for q in qed}}
    for h, r in twins.items():
        if assign.get(r.image_id) != split:
            raise SystemExit(f"split leak: tooth-annotation twin {r.image_id} of a {split} radiograph is in {assign.get(r.image_id)}")
    twin_items = {r.content_hash: anns for r, anns, _ in Tr._annotations_for(s, svc, list(twins.values()))}
    crops, unlabelled, images, t0 = [], [], 0, time.time()
    for row, anns, cats in Tr._annotations_for(s, svc, qed):
        path = s.data_root / row.file_path
        with Image.open(path) as im:
            pil_rgb = np.asarray(im.convert("RGB"))
        rgb01 = np.repeat(load_gray(path)[..., None], 3, axis=2)          # production loading
        finds = []
        for a in anns:                                                    # same filter as the trainer / end-to-end evaluation
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox") or lab not in idx:
                continue
            b = xyxy(a["bbox"])
            if Tr.crop_region(pil_rgb, b, size) is None:
                continue
            finds.append({"label": lab, "box": b})
        if not finds:
            continue
        images += 1
        pg = TM.classify_regions(rgb01, [f["box"] for f in finds], s)["probabilities"]       # production path, GT boxes
        det = TM.detect_teeth(rgb01, row.image_id, s)
        dboxes = [d.box for d in det.detections]
        pd = TM.classify_regions(rgb01, dboxes, s)["probabilities"] if dboxes else []      # production path, detector boxes
        m = match([f["box"] for f in finds], dboxes, IOU)
        for i, f in enumerate(finds):
            hit = m.get(i)
            crops.append({"image_id": row.image_id, "label": f["label"], "gt_probs": pg[i], "det_probs": pd[hit[0]] if hit else None,
                          "matched": bool(hit), "match_iou": round(hit[1], 4) if hit else None})
        teeth = [xyxy(x["bbox"]) for x in twin_items.get(row.content_hash, []) if x.get("bbox")] if row.content_hash in twins else None
        if teeth:
            used = {j for j, _ in m.values()}
            tm = {j for j, _ in match(teeth, dboxes, IOU).values()}
            for j in range(len(dboxes)):
                if j not in used and j in tm:
                    unlabelled.append({"image_id": row.image_id, "probs": pd[j]})
    out = {"split": split, "generated": datetime.now(timezone.utc).isoformat(), "duration_s": round(time.time() - t0, 1),
           "class_names": names, "n_radiographs": images, "n_findings": len(crops), "n_unlabelled_tooth_boxes": len(unlabelled),
           "models": {"detection": {"version": det_info.version, "sha256": file_sha256(det_info.path)},
                      "classification": {"version": cls_info.version, "sha256": file_sha256(cls_info.path)}},
           "data": {"manifest_sha256": file_sha256(s.processed_dir / "manifest.json"), "split_assignments_sha": assignments_sha(s.splits_dir / "dentex_splits.json")},
           "crops": crops, "unlabelled": unlabelled}
    return out


# ------------------------------------------------------------------------------------------------------------------- analyze
def rules(baseline: float) -> list:
    out = [Rule("entropy", baseline)]
    for fam, ts in GRID.items():
        out += [Rule(fam, t) for t in ts]
    return out


def population(d: dict, pop: str):
    names = d["class_names"]
    idx = {c: i for i, c in enumerate(names)}
    key = "det_probs" if pop == "det" else "gt_probs"
    sel = [c for c in d["crops"] if pop == "gt" or c["matched"]]
    return [idx[c["label"]] for c in sel], [c[key] for c in sel], names


def bootstrap_risk_diff(y, probs, base: Rule, cand: Rule, names, n, seed=0) -> dict:
    from dentexmodel.uncertainty.abstention import decide
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    dec_b = [decide(p, base) for p in probs]
    dec_c = [decide(p, cand) for p in probs]
    acc_b = np.array([d not in (None, "missing") for d in dec_b]); err_b = np.array([d not in (None, "missing") and d != t for d, t in zip(dec_b, y)])
    acc_c = np.array([d not in (None, "missing") for d in dec_c]); err_c = np.array([d not in (None, "missing") and d != t for d, t in zip(dec_c, y)])
    diffs = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        rb = err_b[i].sum() / max(1, acc_b[i].sum())
        rc = err_c[i].sum() / max(1, acc_c[i].sum())
        diffs.append(rc - rb)
    return {"mean": float(np.mean(diffs)), "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]}


EPS = 1e-9      # limits are inclusive; without this, e.g. 0.80 - 0.75 = 0.05000000000000004 would count as a drop above 0.05


def check(base: dict, cand: dict, split: str) -> dict:
    gain = CRIT["coverage_gain_cal"] if split == "calibration" else CRIT["coverage_gain_val"]
    res = {"C1_coverage_gain": cand["coverage"] - base["coverage"] >= gain - EPS,
           "C2_risk_increase": (cand["risk"] or 0) - (base["risk"] or 0) <= CRIT["risk_increase_max"] + EPS}
    c3 = True
    for c in CRIT["minority"]:
        b, k = base["per_class"][c], cand["per_class"][c]
        if b["precision"] is not None and (k["precision"] is None or b["precision"] - k["precision"] > CRIT["minority_precision_drop_max"] + EPS):
            c3 = False
        if (k["recall_all"] or 0) < (b["recall_all"] or 0) - EPS:
            c3 = False
    res["C3_minority_classes"] = c3
    res["C4_macro_f1"] = cand["macro_f1_all"] >= base["macro_f1_all"] - CRIT["macro_f1_drop_max"] - EPS
    return res


def analyze() -> dict:
    s = get_settings()
    base_t = production_threshold(s)
    data = {sp: json.loads((OUT / f"probs_{sp}.json").read_text(encoding="utf-8")) for sp in SPLITS}
    if data["calibration"]["models"] != data["val"]["models"]:
        raise SystemExit("calibration and validation caches were produced by different models")
    names = data["val"]["class_names"]
    base = Rule("entropy", base_t)
    res = {"generated": datetime.now(timezone.utc).isoformat(), "baseline_rule": {"family": "entropy", "threshold": base_t, "operator": ">=",
           "formula": "H(p) = -sum_k p_k ln p_k / ln K, K=4", "source": "Data/reports/uncertainty_thresholds.json (calibration split, Youden's J)"},
           "criteria": CRIT, "grid": GRID, "models": data["val"]["models"], "data": {sp: {k: data[sp][k] for k in ("n_radiographs", "n_findings", "n_unlabelled_tooth_boxes", "data", "generated")} for sp in SPLITS},
           "splits": {}}
    for sp in SPLITS:
        d = data[sp]
        res["splits"][sp] = {}
        for pop in ("det", "gt"):
            y, P, _ = population(d, pop)
            res["splits"][sp][pop] = [selective_metrics(y, P, r, names) for r in rules(base_t)]
        res["splits"][sp]["unlabelled"] = [acceptance_rate([u["probs"] for u in d["unlabelled"]], r, names) for r in rules(base_t)]
        res["splits"][sp]["support"] = {c: sum(1 for x in d["crops"] if x["label"] == c and x["matched"]) for c in names}
    # ---- selection on calibration (population det), confirmation on validation
    cal, val = res["splits"]["calibration"]["det"], res["splits"]["val"]["det"]
    passing = []
    for i, r in enumerate(rules(base_t)[1:], 1):
        ck = check(cal[0], cal[i], "calibration")
        cal[i]["criteria_calibration"] = ck
        if all(ck.values()):
            passing.append(i)
    sel = max(passing, key=lambda i: (cal[i]["coverage"], -(cal[i]["risk"] or 0))) if passing else None
    res["passing_on_calibration"] = [cal[i]["rule"]["name"] for i in passing]
    if sel is None:
        res["candidate"] = None
        res["recommendation"] = "keep the production baseline: no rule met C1-C4 on the calibration split"
    else:
        r = rules(base_t)[sel]
        ckv = check(val[0], val[sel], "val")
        y, P, _ = population(data["val"], "det")
        bs = bootstrap_risk_diff(y, P, base, r, names, CRIT["bootstrap_n"])
        ckv["C5_bootstrap_risk_upper_bound"] = bs["ci95"][1] <= CRIT["bootstrap_risk_ub_max"]
        res["candidate"] = {"index": sel, "rule": cal[sel]["rule"], "criteria_validation": ckv, "bootstrap_val_risk_diff": bs,
                            "passes_all": all(ckv.values())}
        res["recommendation"] = (f"candidate '{r.name}' met all criteria; it still needs review and explicit approval before any production change"
                                 if all(ckv.values()) else
                                 f"keep the production baseline: the calibration candidate '{r.name}' failed on validation ({', '.join(k for k, v in ckv.items() if not v)})")
    return res


# ------------------------------------------------------------------------------------------------------------------- report
def fmt(v, nd=3):
    return "–" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def write_report(res: dict):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "report.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    names = res["models"] and list(res["splits"]["val"]["det"][0]["per_class"].keys())
    L = ["# Abstention-rule experiment (finding classifier)", "",
         f"Generated {res['generated']}. Offline only: production thresholds, checkpoints, API and UI are unchanged.", "",
         "## Baseline (production, unchanged)", "",
         f"* Rule: abstain if normalised entropy `H(p) >= {res['baseline_rule']['threshold']:.5f}`, `{res['baseline_rule']['formula']}`; "
         f"source: {res['baseline_rule']['source']}.",
         "* Only entropy causes an abstention. Flip disagreement (>= 0.0762), weak detection, unstable masks and numbering flags mark a region "
         "for review but never withhold the class.",
         f"* Models: detection `{res['models']['detection']['version']}` ({res['models']['detection']['sha256'][:12]}), "
         f"classification `{res['models']['classification']['version']}` ({res['models']['classification']['sha256'][:12]}).", "",
         "## Data and leakage control", "",
         "| Split | Role | Radiographs | Findings | Matched to a detector box (population `det`) | Unlabelled tooth boxes |", "|---|---|---:|---:|---:|---:|"]
    for sp, role in (("calibration", "tuning (rule selection)"), ("val", "confirmation only")):
        dd = res["data"][sp]
        sup = res["splits"][sp]["support"]
        L.append(f"| {sp} | {role} | {dd['n_radiographs']} | {dd['n_findings']} | {sum(sup.values())} ({', '.join(f'{k} {v}' for k, v in sup.items())}) | {dd['n_unlabelled_tooth_boxes']} |")
    L += ["", "The test split is never read. Validation also selected the classifier's best epoch, so its absolute values are slightly optimistic "
          "for every rule alike. Unlabelled tooth boxes have no finding label: they are not assumed healthy and are never counted as false "
          "positives; only the share that a rule names a class for is reported.", "",
          "## Acceptance criteria (fixed before the run)", "",
          "C1 coverage gain >= +0.10 (calibration) / +0.05 (validation); C2 risk increase <= +0.02; C3 Deep Caries and Periapical Lesion precision drop "
          "<= 0.05 and end-to-end recall not lower; C4 end-to-end macro-F1 >= baseline - 0.01; C5 (validation) bootstrap 95% upper bound of the risk "
          "increase <= 0.05. Candidate = highest calibration coverage among rules passing C1–C4 on calibration; recommended only if it also passes C1–C5 "
          "on validation.", "",
          "Note on the analysis code: the first analysis run compared the limits without a floating-point tolerance, so a precision drop of "
          "exactly 0.05 (0.80 → 0.75, one crop) counted as a failure. The limits are inclusive by definition; the comparison was corrected "
          "(tolerance 1e-9) and the analysis re-run. The criteria values themselves were not changed.", ""]
    for sp in ("calibration", "val"):
        rows = res["splits"][sp]["det"]
        un = res["splits"][sp]["unlabelled"]
        L += [f"## Results — {sp} split, detector crops (`det`)", "",
              "| Rule | Accepted | Abstained | Coverage | Risk | Macro P | Macro R (all) | Macro F1 (accepted) | Macro F1 (all) | DC P / R(all) / F1(all) | PL P / R(all) / F1(all) | Unlabelled named | C1–C4 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|"]
        for i, r in enumerate(rows):
            dc, pl = r["per_class"]["Deep Caries"], r["per_class"]["Periapical Lesion"]
            ck = r.get("criteria_calibration") if sp == "calibration" else None
            tag = "**baseline**" if i == 0 else ("pass" if ck and all(ck.values()) else ("fail: " + ",".join(k.split("_")[0] for k, v in ck.items() if not v) if ck else ""))
            L.append(f"| {'**' + r['rule']['name'] + '**' if i == 0 else r['rule']['name']} | {r['accepted']} ({r['accepted'] / r['n']:.0%}) | {r['abstained']} ({r['abstained'] / r['n']:.0%}) | "
                     f"{fmt(r['coverage'])} | {fmt(r['risk'])} | {fmt(r['macro_precision'])} | {fmt(r['macro_recall_all'])} | {fmt(r['macro_f1_accepted'])} | {fmt(r['macro_f1_all'])} | "
                     f"{fmt(dc['precision'], 2)} / {fmt(dc['recall_all'], 2)} / {fmt(dc['f1_all'], 2)} | {fmt(pl['precision'], 2)} / {fmt(pl['recall_all'], 2)} / {fmt(pl['f1_all'], 2)} | "
                     f"{un[i]['named']}/{un[i]['n'] - un[i]['missing']} ({un[i]['named_rate']:.0%}) | {tag} |")
        L.append("")
    for sp in ("calibration", "val"):
        rows = res["splits"][sp]["gt"]
        L += [f"### {sp} split, ground-truth crops (`gt`, secondary)", "", "| Rule | Coverage | Risk | Macro F1 (all) | DC R(all) | PL R(all) |", "|---|---:|---:|---:|---:|---:|"]
        for r in rows:
            L.append(f"| {r['rule']['name']} | {fmt(r['coverage'])} | {fmt(r['risk'])} | {fmt(r['macro_f1_all'])} | {fmt(r['per_class']['Deep Caries']['recall_all'], 2)} | {fmt(r['per_class']['Periapical Lesion']['recall_all'], 2)} |")
        L.append("")
    def cm_block(r, title):
        cols = r["confusion_columns"]
        out = [f"**{title}** — {r['rule']['name']}", "", "| true \\ predicted | " + " | ".join(cols) + " |", "|---|" + "---:|" * len(cols)]
        for k, row in enumerate(r["confusion"]):
            out.append(f"| {names[k]} | " + " | ".join(str(v) for v in row) + " |")
        out += ["", "| Class | Support | TP | FP | FN | Precision | Recall (accepted) | Recall (all) | F1 (all) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for c, p in r["per_class"].items():
            out.append(f"| {c} | {p['support']} | {p['tp']} | {p['fp']} | {p['fn']} | {fmt(p['precision'])} | {fmt(p['recall_accepted'])} | {fmt(p['recall_all'])} | {fmt(p['f1_all'])} |")
        return out + [""]
    L += ["## Confusion matrices and per-class results (detector crops)", "",
          "FP = accepted predictions of the class whose label differs; FN = crops of the class not correctly accepted (wrong class, abstained or missing).", ""]
    cand = res.get("candidate")
    for sp in ("calibration", "val"):
        rows = res["splits"][sp]["det"]
        L += cm_block(rows[0], f"{sp} — baseline")
        if cand:
            L += cm_block(rows[cand["index"]], f"{sp} — candidate")
    L += ["## Selection", "", f"Rules passing C1–C4 on calibration: {', '.join(res['passing_on_calibration']) or 'none'}.", ""]
    if cand:
        L += [f"Candidate: **{cand['rule']['name']}**. Validation checks: " + ", ".join(f"{k} {'pass' if v else 'FAIL'}" for k, v in cand["criteria_validation"].items()) + ".",
              f"Bootstrap (validation, {CRIT['bootstrap_n']} resamples) risk difference candidate − baseline: mean {cand['bootstrap_val_risk_diff']['mean']:+.3f}, "
              f"95% CI [{cand['bootstrap_val_risk_diff']['ci95'][0]:+.3f}, {cand['bootstrap_val_risk_diff']['ci95'][1]:+.3f}].", ""]
    L += ["## Recommendation", "", f"**{res['recommendation']}.**", "",
          "## Limitations", "",
          "* Risk can only be measured on teeth that carry a DENTEX finding label. On teeth without a label (most teeth in a radiograph) the effect of "
          "a looser rule is unknown: the extra named classes there may be false alarms, and the ‘Unlabelled named’ column shows how many more teeth "
          "would get a class. The classifier has no healthy class, so this cannot be resolved without new labels.",
          "* Deep Caries and Periapical Lesion have few examples per split; their precision and recall move by large steps with one crop.",
          "* One model, one seed, one dataset; validation also selected the classifier's epoch. No test-split confirmation (by design).",
          "* Nothing here is deployed. Changing the production threshold requires review and explicit approval, then an update of "
          "Data/reports/uncertainty_thresholds.json.", "",
          "## Reproduce", "", "```", ".venv\\Scripts\\python.exe scripts\\abstention_threshold_experiment.py collect   # GPU, ~1-2 min, caches probabilities",
          ".venv\\Scripts\\python.exe scripts\\abstention_threshold_experiment.py analyze   # CPU, writes report.json / report.md",
          ".venv\\Scripts\\python.exe -m pytest tests\\test_abstention_rules.py -q", "```", ""]
    (OUT / "report.md").write_text("\n".join(L), encoding="utf-8")
    return OUT / "report.md"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["collect", "analyze"])
    ap.add_argument("--force", action="store_true", help="collect: overwrite existing probability caches")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.stage == "collect":
        for sp in SPLITS:
            f = OUT / f"probs_{sp}.json"
            if f.exists() and not a.force:
                print(f"{f} exists (use --force to recollect)")
                continue
            d = collect(sp)
            f.write_text(json.dumps(d, default=float), encoding="utf-8")
            print(f"{sp}: {d['n_radiographs']} radiographs, {d['n_findings']} findings, {d['n_unlabelled_tooth_boxes']} unlabelled tooth boxes ({d['duration_s']}s) -> {f}")
        return 0
    res = analyze()
    p = write_report(res)
    print(res["recommendation"])
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
