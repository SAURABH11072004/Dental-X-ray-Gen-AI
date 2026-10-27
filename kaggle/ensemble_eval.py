#!/usr/bin/env python
"""5-seed BASE ensemble (mean softmax probability) on the DENTEX validation split. Protocol: reports/ensemble_protocol.md.

    .venv\\Scripts\\python.exe kaggle\\ensemble_eval.py

Reuses the Kaggle notebook's own crop builders, prediction and metric code (kaggle/dentamind_kaggle.py) so every number uses the same
definitions as the BASE comparison. The DENTEX test split is never loaded. Writes reports/ensemble_evaluation.json and .md.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import dentamind_kaggle as DK  # noqa: E402
from dsutil import CLASSES  # noqa: E402

RUN_DIR = HERE / "artifacts_external_run1"
CK_DIR = RUN_DIR / "base_checkpoints"
# protocol section 1: fixed members, identified by full SHA-256 (checkpoint_manifest.json of the Kaggle run)
MEMBERS = {
    42: "0846c7595f9e567960d223988a284e8aab552b7a53be172f719e02508117c6ad",
    43: "48c2b6718afdef0e273598e60b8feb51f3129db3d11da4d9f9c790cc2eb779cf",
    44: "270cb3f190b99a9d56bc3c086a56223264e69bdc9ad989e77fe765d3ceb75a4b",
    45: "05ed85068fec18102e5686d619488c50aef0fda69f4046a842dfe26cd62e22f8",
    46: "653eaab4cfea1efa0b1bc3de683c707f28128aed97f9eee50619baa9ec59a30e",
}
REPRO_TOL = 0.005            # protocol section 4
BOOT_N, BOOT_SEED = 2000, 0  # protocol section 5 (reported, not used for acceptance)


class EnsembleError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------------------- members
def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_members(ck_paths, members=MEMBERS) -> dict:
    """ck_paths: a folder holding BASE_s<seed>.pth, or {seed: path}. Returns {seed: path}. Stops on a missing file or a hash that
    differs from the registered one (never substitutes another file)."""
    if not isinstance(ck_paths, dict):
        ck_paths = {s: Path(ck_paths) / f"BASE_s{s}.pth" for s in members}
    out, problems = {}, []
    for seed, want in sorted(members.items()):
        p = Path(ck_paths[seed]) if ck_paths.get(seed) else Path(f"<no path for seed {seed}>")
        if not p.is_file():
            problems.append(f"BASE_s{seed}: missing ({p})")
            continue
        got = sha256(p)
        if got != want:
            problems.append(f"BASE_s{seed}: sha256 {got[:16]}... != registered {want[:16]}...")
            continue
        out[seed] = p
    if problems:
        raise EnsembleError("ensemble members not usable: " + "; ".join(problems))
    return out


def check_class_order(class_names) -> None:
    if list(class_names) != list(CLASSES):
        raise EnsembleError(f"class order {list(class_names)} differs from {list(CLASSES)}")


def load_member(path, torch, tv, device):
    """Same construction as evaluate_checkpoint; strict load; output layer must have one unit per class."""
    m = DK.new_model(torch, tv, pretrained=False)
    sd = torch.load(path, map_location="cpu", weights_only=True)
    if tuple(sd["fc.weight"].shape) != (len(CLASSES), m.fc.in_features):
        raise EnsembleError(f"{Path(path).name}: output layer {tuple(sd['fc.weight'].shape)} does not match {len(CLASSES)} classes")
    m.load_state_dict(sd, strict=True)
    return m.to(device).eval()


# ------------------------------------------------------------------------------------------------------------- ensemble
def average_probs(prob_list) -> np.ndarray:
    """Arithmetic mean of member softmax outputs (protocol section 2). All members must give the same (N, C) shape, C = len(CLASSES),
    finite values, rows summing to 1."""
    if not prob_list:
        raise EnsembleError("no member probabilities")
    arrs = [np.asarray(p, dtype=np.float64) for p in prob_list]
    shape = arrs[0].shape
    if len(shape) != 2 or shape[1] != len(CLASSES):
        raise EnsembleError(f"member output shape {shape} is not (N, {len(CLASSES)})")
    for i, a in enumerate(arrs):
        if a.shape != shape:
            raise EnsembleError(f"member {i} output shape {a.shape} differs from {shape}")
        if not np.isfinite(a).all() or (a < 0).any() or not np.allclose(a.sum(1), 1.0, atol=1e-4):
            raise EnsembleError(f"member {i} output is not a probability distribution per row")
    return np.mean(np.stack(arrs), axis=0)


def macro_f1(y, pred, n=len(CLASSES)) -> float:
    """Same definition as DK.report (classes with no prediction count as F1 0), vectorised for the bootstrap."""
    cm = np.bincount(np.asarray(y) * n + np.asarray(pred), minlength=n * n).reshape(n, n)
    tp, pp, sup = np.diag(cm), cm.sum(0), cm.sum(1)
    prec = np.divide(tp, pp, out=np.zeros(n), where=pp > 0)
    rec = np.divide(tp, sup, out=np.zeros(n), where=sup > 0)
    return float(np.divide(2 * prec * rec, prec + rec, out=np.zeros(n), where=(prec + rec) > 0).mean())


def bootstrap_diff(y, ens_pred, member_preds, n_boot=BOOT_N, seed=BOOT_SEED) -> dict:
    """95 % percentile interval of macro-F1(ensemble) - mean_k macro-F1(member k), resampling findings with replacement."""
    rng = np.random.default_rng(seed)
    y, ens_pred = np.asarray(y), np.asarray(ens_pred)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        diffs[b] = macro_f1(y[i], ens_pred[i]) - np.mean([macro_f1(y[i], np.asarray(p)[i]) for p in member_preds])
    return {"n_boot": n_boot, "seed": seed, "mean": float(diffs.mean()), "ci95": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
            "share_positive": float((diffs > 0).mean())}


def ensemble_acceptance(ens: dict, members: dict, setting="det_matched") -> dict:
    """Protocol section 5. ens = {"gt": report, "det_matched": report}; members = {seed: same}. Thresholds from DK.ACCEPT."""
    A = DK.ACCEPT
    seeds = sorted(members)
    if len(seeds) < A["seed_pairs_min"]:
        return {"pass": False, "reason": f"only {len(seeds)} members"}
    mean = lambda f: float(np.mean([f(members[s]) for s in seeds]))  # noqa: E731
    f1 = lambda r: r[setting]["macro_f1"]  # noqa: E731
    pc = lambda c, m: mean(lambda r: r[setting]["per_class"][c][m])  # noqa: E731
    gain = ens[setting]["macro_f1"] - mean(f1)
    beats = int(sum(ens[setting]["macro_f1"] > f1(members[s]) for s in seeds))
    e = lambda c, m: ens[setting]["per_class"][c][m]  # noqa: E731
    c1 = gain > A["gain_min"] and beats >= A["seed_pairs_min"]
    c2 = all(e(c, "recall") >= pc(c, "recall") for c in DK.MINORITY)
    c3 = all(e(c, "f1") >= pc(c, "f1") - A["class_f1_drop_max"] for c in CLASSES)
    gt_delta = ens["gt"]["macro_f1"] - mean(lambda r: r["gt"]["macro_f1"])
    c4 = gt_delta >= -A["gt_macro_f1_drop_max"]
    c5 = all(e(c, "precision") >= pc(c, "precision") - A["minority_precision_drop_max"] for c in DK.MINORITY)
    return {"setting": setting, "members": seeds, "macro_f1_gain_vs_base_mean": gain, "members_beaten": beats,
            "minority_recall_delta": {c: e(c, "recall") - pc(c, "recall") for c in DK.MINORITY},
            "minority_precision_delta": {c: e(c, "precision") - pc(c, "precision") for c in DK.MINORITY},
            "class_f1_delta": {c: e(c, "f1") - pc(c, "f1") for c in CLASSES}, "gt_macro_f1_delta": gt_delta,
            "criteria": {"1_gain_gt_0.027_and_beats_4_of_5": bool(c1), "2_minority_recall_not_lower": bool(c2),
                         "3_no_class_f1_drop_gt_0.05": bool(c3), "4_gt_macro_f1_drop_le_0.02": bool(c4),
                         "5_minority_precision_drop_le_0.10": bool(c5)},
            "pass": bool(c1 and c2 and c3 and c4 and c5)}


def reproduction_check(local: dict, kaggle: dict, tol=REPRO_TOL) -> dict:
    """Protocol section 4: every member's local macro-F1 (gt and det_matched) must match the Kaggle run within tol."""
    rows, ok = {}, True
    for s in sorted(local):
        r = {}
        for setting in ("gt", "det_matched"):
            a, b = local[s][setting]["macro_f1"], kaggle[str(s)][setting]["macro_f1"]
            r[setting] = {"local": a, "kaggle": b, "abs_diff": abs(a - b)}
            ok &= abs(a - b) <= tol
        rows[s] = r
    return {"tolerance": tol, "pass": bool(ok), "members": rows}


# ------------------------------------------------------------------------------------------------------------- latency
def latency(torch, models, X, device, reps=5):
    """Seconds per crop for one member and for the full ensemble; batch 64 and batch 1; after warm-up."""
    def timed(fn):
        fn()                                   # warm-up
        if device.type == "cuda":
            torch.cuda.synchronize()
        t = time.perf_counter()
        for _ in range(reps):
            fn()
        if device.type == "cuda":
            torch.cuda.synchronize()
        return (time.perf_counter() - t) / reps
    xb, x1 = X[:64], X[:1]
    one = models[:1]
    run = lambda ms, x: [DK.predict(torch, m, x, device) for m in ms]  # noqa: E731
    out = {"device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu", "reps": reps,
           "single_member_batch64_s_per_crop": timed(lambda: run(one, xb)) / len(xb),
           "ensemble_batch64_s_per_crop": timed(lambda: run(models, xb)) / len(xb),
           "single_member_batch1_s": timed(lambda: run(one, x1)),
           "ensemble_batch1_s": timed(lambda: run(models, x1))}
    out["ratio_batch64"] = out["ensemble_batch64_s_per_crop"] / out["single_member_batch64_s_per_crop"]
    out["ratio_batch1"] = out["ensemble_batch1_s"] / out["single_member_batch1_s"]
    return out


# ------------------------------------------------------------------------------------------------------------- main
def local_config() -> dict:
    """Paths in this repository. The Kaggle notebook (kaggle/make_ensemble_notebook.py) passes its own input locations instead."""
    return {"ck_paths": CK_DIR, "class_meta": RUN_DIR / "checkpoints/baseline__BASE_s43.json",
            "run_records": {s: RUN_DIR / f"runs/BASE_s{s}.json" for s in MEMBERS}, "kaggle_eval": RUN_DIR / "validation_eval.json",
            "data_root": ROOT / "Data", "split_dir": ROOT / "data/splits",
            "det_cache": ROOT / "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json",
            "out_dir": ROOT / "reports", "environment": "local"}


def main(cfg: dict | None = None):
    import torch
    import torchvision as tv
    cfg = cfg or local_config()
    t0 = time.time()
    paths = verify_members(cfg["ck_paths"])
    check_class_order(json.loads(Path(cfg["class_meta"]).read_text(encoding="utf-8"))["class_names"])
    for s in MEMBERS:                         # every member comes from the same BASE configuration of the same run
        r = json.loads(Path(cfg["run_records"][s]).read_text(encoding="utf-8"))
        if r["experiment"] != "BASE" or r["checkpoint_sha256"] != MEMBERS[s]:
            raise EnsembleError(f"run record BASE_s{s} does not describe the registered checkpoint")

    data_root = Path(cfg["data_root"])
    rows = DK.load_split(cfg["split_dir"], "validation")       # validation only; the test split is never read
    n_ok, problems = DK.verify_images(rows, data_root)
    if problems:
        raise EnsembleError(f"validation images not byte-identical to the manifest: {problems}")
    Xg, y, _ = DK.build_crops(rows, data_root)
    Xd, mi, missed = DK.build_detector_crops(rows, data_root, cfg["det_cache"], lambda r: r["project_image_id"])
    print(f"validation: {len(y)} findings, {n_ok} radiographs, detector-matched {len(mi)}, unmatched {missed}", flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    probs = {}
    for s, p in paths.items():
        m = load_member(p, torch, tv, device)
        probs[s] = {"gt": DK.predict(torch, m, Xg, device), "det": DK.predict(torch, m, Xd, device)}
        del m
        if device.type == "cuda":
            torch.cuda.empty_cache()
        print(f"member s{s} predicted", flush=True)
    yd = y[mi]
    members = {s: {"gt": DK.report(y, pr["gt"].argmax(1), pr["gt"]), "det_matched": DK.report(yd, pr["det"].argmax(1), pr["det"])}
               for s, pr in probs.items()}

    kaggle_eval = json.loads(Path(cfg["kaggle_eval"]).read_text(encoding="utf-8"))["eval"]["BASE"]
    repro = reproduction_check(members, kaggle_eval)
    result = {"protocol": "reports/ensemble_protocol.md", "generated_utc": datetime.now(timezone.utc).isoformat(),
              "environment": cfg.get("environment"), "script_sha256": sha256(__file__),
              "members": {s: {"sha256": MEMBERS[s], "path": str(paths[s])} for s in MEMBERS},
              "data": {"split": "data/splits/combined_validation.csv", "findings": int(len(y)), "radiographs": int(n_ok),
                       "detector_matched": int(len(mi)), "detector_unmatched": int(missed), "test_split_loaded": False},
              "software": DK.software(), "reproduction_check": repro, "member_results": members}
    out_dir = Path(cfg["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / ("ensemble_evaluation.json" if cfg.get("environment") == "local" else "ensemble_evaluation_kaggle.json")
    if not repro["pass"]:
        result["stopped"] = "reproduction check failed (protocol section 4); no ensemble comparison made"
        out_json.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
        raise SystemExit(result["stopped"])

    pg = average_probs([probs[s]["gt"] for s in sorted(probs)])
    pd = average_probs([probs[s]["det"] for s in sorted(probs)])
    ens = {"gt": DK.report(y, pg.argmax(1), pg), "det_matched": DK.report(yd, pd.argmax(1), pd)}
    result["ensemble"] = ens
    result["acceptance"] = ensemble_acceptance(ens, members)
    result["bootstrap_det_matched"] = bootstrap_diff(yd, pd.argmax(1), [probs[s]["det"].argmax(1) for s in sorted(probs)])
    result["bootstrap_gt"] = bootstrap_diff(y, pg.argmax(1), [probs[s]["gt"].argmax(1) for s in sorted(probs)])

    models = [load_member(paths[s], torch, tv, device) for s in sorted(paths)]
    result["latency"] = latency(torch, models, Xd, device)
    del models
    result["runtime_s"] = round(time.time() - t0, 1)
    out_json.write_text(json.dumps(result, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"reproduction_pass": repro["pass"], "acceptance": result["acceptance"]["criteria"],
                      "pass": result["acceptance"]["pass"]}, indent=1))
    print("wrote", out_json)


if __name__ == "__main__":
    main()
