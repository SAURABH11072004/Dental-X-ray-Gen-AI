"""CV5 acceptance rule for candidates vs the BASE reference. Protocol: reports/cv5_acceptance_protocol.md (revision 3, approved 2026-10-25).

Implements, and only implements, what the protocol specifies:
* paired radiograph-level bootstrap (Appendix C) and the criteria P-A..P-D, S1..S7, H (section 5);
* validity gates: fold-file check and gate R (section 4.3), gate V6 (section 3.1);
* run classification and collapse check (section 9), lifetime budget (section 10.1), winner rule (section 10.2);
* the V-a held-out fold-0 report from stored predictions (section 10.3) and the per-run training manifest it requires.

It trains nothing and runs no inference. Thresholds are module constants copied from the protocol; changing one is a protocol amendment.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import cv5_lib as CV
import dentamind_kaggle as DK
from dsutil import CLASSES

PROTOCOL = "reports/cv5_acceptance_protocol.md (revision 3, approved 2026-10-25)"
DELTA = 0.027                                   # P-A, operator >=
K_LIFETIME = 15                                 # U6: Bonferroni over the fixed lifetime budget
B, BOOT_SEED = 20_000, 0                        # Appendix C
PB_LEVEL = 1 - 0.05 / K_LIFETIME
H_LEVEL = 0.95                                  # U7: hard-harm and safeguard CIs, unadjusted
SEEDS_MIN_WINS = FOLDS_MIN_WINS = 4
DC, PL = CLASSES.index("Deep Caries"), CLASSES.index("Periapical Lesion")
# (name, setting, class index or None for macro, metric, margin)
SAFEGUARDS = [("S1", "det", DC, "recall", 0.03), ("S2", "det", PL, "recall", 0.05),
              ("S3", "det", DC, "precision", 0.04), ("S4", "det", PL, "precision", 0.04),
              ("S5a", "det", CLASSES.index("Caries"), "f1", 0.02), ("S5b", "det", DC, "f1", 0.03),
              ("S5c", "det", CLASSES.index("Impacted"), "f1", 0.02), ("S5d", "det", PL, "f1", 0.03),
              ("S6", "gt", None, "macro_f1", 0.02),
              ("S7a", "e2e", DC, "recall", 0.03), ("S7b", "e2e", PL, "recall", 0.05)]
HARM = [("H_DC_recall", DC, "recall"), ("H_PL_recall", PL, "recall"),
        ("H_DC_precision", DC, "precision"), ("H_PL_precision", PL, "precision")]
R2_TOL = 1e-4                                   # gate R, max |probability difference|
COLLAPSE_SHARE = 0.99                           # section 9
MAX_ATTEMPTS = 3
FAMILY_CAP = {"F1": 3, "F2": 3, "F3": 3, "F4": 3, "F5": 1, "combination": 2}
FINAL_FOLD, FINAL_SEED = 0, 42                  # V-a
DISCLOSURE = ("Held-out fold 0 was part of the population on which all confirmatory candidates were compared and the winner was "
              "selected. This report is independent of the checkpoint's training data but not independent confirmation of the "
              "selected winner.")
NC = len(CLASSES)
UNMATCHED = NC                                  # extra predicted column for end-to-end (unmatched = wrong)


class AcceptError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------------------- predictions
def labels(arm: dict) -> dict:
    """arm = {seed: {"gt": (N, C) probs, "det": (N, C) probs, NaN rows = no detector match}} -> predicted classes per setting.
    det: argmax on matched rows (-1 elsewhere); e2e: det argmax, unmatched -> UNMATCHED."""
    out = {}
    for s, p in arm.items():
        det = np.asarray(p["det"], float)
        ok = ~np.isnan(det).any(1)
        dl = np.where(ok, np.nan_to_num(det, nan=-1).argmax(1), -1)
        out[s] = {"gt": np.asarray(p["gt"], float).argmax(1), "det": dl, "e2e": np.where(ok, dl, UNMATCHED), "matched": ok}
    return out


def metrics_from_confusion(cm: np.ndarray) -> dict:
    """cm: (..., C, C+1) counts, rows = true class, last column = unmatched. Undefined precision / recall / F1 count as 0."""
    tp = np.diagonal(cm[..., :NC], axis1=-2, axis2=-1).astype(float)
    pp = cm[..., :NC].sum(-2).astype(float)
    sup = cm.sum(-1).astype(float)
    prec = np.divide(tp, pp, out=np.zeros_like(tp), where=pp > 0)
    rec = np.divide(tp, sup, out=np.zeros_like(tp), where=sup > 0)
    f1 = np.divide(2 * prec * rec, prec + rec, out=np.zeros_like(tp), where=(prec + rec) > 0)
    return {"precision": prec, "recall": rec, "f1": f1, "macro_f1": f1.mean(-1), "support": sup}


def _group_confusion(y, pred, mask, gidx, n_groups) -> np.ndarray:
    """(G, C*(C+1)) confusion counts per radiograph group for the findings in mask."""
    out = np.zeros((n_groups, NC * (NC + 1)), np.int64)
    cell = y * (NC + 1) + pred
    np.add.at(out, (gidx[mask], cell[mask]), 1)
    return out


def _weights(rng, n_groups, n_boot, chunk=2000):
    """Yields (draws, counts): draws = rng.choice(G, size=(n, G), replace=True) per chunk; counts[b, g] = times group g was drawn."""
    for start in range(0, n_boot, chunk):
        n = min(chunk, n_boot - start)
        d = rng.choice(n_groups, size=(n, n_groups), replace=True)
        c = np.bincount((d + n_groups * np.arange(n)[:, None]).ravel(), minlength=n * n_groups).reshape(n, n_groups)
        yield d, c


# ------------------------------------------------------------------------------------------------------------- comparison
def compare(y, groups, folds, ref: dict, cand: dict, *, n_boot=B, seed=BOOT_SEED, ensemble=False) -> dict:
    """Section 5 + Appendix C. y: true class per primary finding; groups: radiograph group; folds: held-out fold.
    ref / cand: arms as in labels(). The detector-matched set comes from the reference (same detector boxes for both arms)."""
    y, groups, folds = np.asarray(y), np.asarray(groups), np.asarray(folds)
    R, C = labels(ref), labels(cand)
    rs, cs = sorted(R), sorted(C)
    matched = R[rs[0]]["matched"]
    for arm in (R, C):
        for s in arm:
            if not np.array_equal(arm[s]["matched"], matched):
                raise AcceptError(f"seed {s}: detector-matched set differs from the reference (same detector boxes required)")
    if not ensemble and rs != cs:
        raise AcceptError(f"seed sets differ: reference {rs}, candidate {cs}")
    uniq, gidx = np.unique(groups, return_inverse=True)
    G = len(uniq)
    masks = {"det": matched, "gt": np.ones(len(y), bool), "e2e": np.ones(len(y), bool)}

    gc = {(a, s, st): _group_confusion(y, arm[s][st], masks[st], gidx, G)
          for a, arm in (("ref", R), ("cand", C)) for s in arm for st in masks}

    def seed_mean(a, seeds, st, w):            # w: (n, G) group weights -> metrics of the seed-mean arm
        ms = [metrics_from_confusion((w @ gc[(a, s, st)]).reshape(-1, NC, NC + 1)) for s in seeds]
        return {k: np.mean([m[k] for m in ms], 0) for k in ("precision", "recall", "f1", "macro_f1")}, ms

    def quantity(m, cls, metric):
        return m[metric] if cls is None else m[metric][..., cls]

    ones = np.ones((1, G))
    point = {st: {"ref": seed_mean("ref", rs, st, ones)[0], "cand": seed_mean("cand", cs, st, ones)[0]} for st in masks}

    def pdelta(st, cls, metric):
        return float(quantity(point[st]["cand"], cls, metric)[0] - quantity(point[st]["ref"], cls, metric)[0])

    # bootstrap: one generator, the same draws for every metric and setting
    rng = np.random.default_rng(seed)
    qs = [("macro_f1", "det", None, "macro_f1")] + [(n, st, c, m) for n, st, c, m, _ in SAFEGUARDS] + [(n, "det", c, m) for n, c, m in HARM]
    boot = {q[0]: np.empty(n_boot) for q in qs}
    degenerate = {st: [0] * NC for st in masks}
    hsh = hashlib.sha256(np.asarray(uniq).astype(str).astype("U").tobytes())
    b0 = 0
    for d, w in _weights(rng, G, n_boot):
        hsh.update(d.astype("<i4").tobytes())
        mr = {st: seed_mean("ref", rs, st, w) for st in masks}
        mc = {st: seed_mean("cand", cs, st, w)[0] for st in masks}
        for name, st, cls, metric in qs:
            boot[name][b0:b0 + len(w)] = quantity(mc[st], cls, metric) - quantity(mr[st][0], cls, metric)
        for st in masks:
            sup = mr[st][1][0]["support"]
            for k in range(NC):
                degenerate[st][k] += int((sup[:, k] == 0).sum())
        b0 += len(w)

    def ci(name, level):
        a = (1 - level) / 2 * 100
        return [float(np.percentile(boot[name], a)), float(np.percentile(boot[name], 100 - a))]

    out = {"protocol": PROTOCOL, "n_findings": int(len(y)), "n_detector_matched": int(matched.sum()), "n_radiographs": int(G),
           "reference_seeds": rs, "candidate_seeds": cs, "ensemble": bool(ensemble),
           "bootstrap": {"generator": f"numpy.random.default_rng({seed})", "B": int(n_boot), "k": K_LIFETIME,
                         "draw_call": "rng.choice(G, size=(2000, G), replace=True) per chunk of 2000 resamples",
                         "draws_sha256": hsh.hexdigest(), "degenerate_resamples_per_class": degenerate}}
    crit = {}
    d_macro = pdelta("det", None, "macro_f1")
    crit["P-A"] = {"delta": d_macro, "threshold": DELTA, "pass": d_macro >= DELTA}
    lo, hi = ci("macro_f1", PB_LEVEL)
    crit["P-B"] = {"level": PB_LEVEL, "ci": [lo, hi], "pass": lo > 0}
    if ensemble:
        crit["P-C"] = {"applicable": False, "pass": True, "note": "ensemble: P-C not applicable (section 6.1)"}
    else:
        per_seed = {}
        for s in rs:
            per_seed[str(s)] = float(metrics_from_confusion((ones @ gc[("cand", s, "det")]).reshape(-1, NC, NC + 1))["macro_f1"][0]
                                     - metrics_from_confusion((ones @ gc[("ref", s, "det")]).reshape(-1, NC, NC + 1))["macro_f1"][0])
        wins = sum(v > 0 for v in per_seed.values())
        crit["P-C"] = {"applicable": True, "per_seed_delta": per_seed, "wins": wins, "pass": wins >= SEEDS_MIN_WINS}
    per_fold = {}
    for f in sorted(set(folds.tolist())):
        wf = np.zeros((1, G))
        wf[0, np.unique(gidx[folds == f])] = 1
        per_fold[str(f)] = float(seed_mean("cand", cs, "det", wf)[0]["macro_f1"][0] - seed_mean("ref", rs, "det", wf)[0]["macro_f1"][0])
    fwins = sum(v > 0 for v in per_fold.values())
    crit["P-D"] = {"per_fold_delta": per_fold, "wins": fwins, "pass": fwins >= FOLDS_MIN_WINS}
    for name, st, cls, metric, margin in SAFEGUARDS:
        dv = pdelta(st, cls, metric)
        crit[name] = {"setting": st, "class": None if cls is None else CLASSES[cls], "metric": metric, "delta": dv,
                      "margin": margin, "ci95": ci(name, H_LEVEL), "pass": dv >= -margin}
    for name, cls, metric in HARM:
        lo_h, hi_h = ci(name, H_LEVEL)
        crit[name] = {"class": CLASSES[cls], "metric": metric, "delta": pdelta("det", cls, metric), "ci95": [lo_h, hi_h],
                      "pass": not hi_h < 0}
    out["criteria"] = crit
    out["point"] = {st: {a: {k: v[0].tolist() if np.ndim(v[0]) else float(v[0]) for k, v in point[st][a].items()} for a in point[st]}
                    for st in point}
    out["delta_b_macro_f1"] = boot["macro_f1"].tolist()
    out["all_criteria_pass"] = all(c["pass"] for c in crit.values())
    return out


# ------------------------------------------------------------------------------------------------------------- verdict
RUN_CLASSES = ("ok", "infrastructure", "divergence", "incomplete")
N_RUNS = 25                                     # 5 folds x 5 seeds (V4)


def verdict(comparison: dict | None, *, confirmatory: bool, validity: dict, run_classes: dict, n_runs: int = N_RUNS) -> dict:
    """Section 5.4 / 9 (owner decision 2026-10-25: any divergence is FAIL; infrastructure failures are NO VERDICT).

    validity: {"V1": bool, "V2": bool, "V3": bool, "V5": bool, "V6": bool or None (no imports)}. V1 here covers CV gates 1-3;
    gates 4/5 (runs complete, one prediction per finding) and V4 are run-level and are derived from run_classes, because section 9
    classifies their failure as infrastructure / incomplete. run_classes: {run: one of RUN_CLASSES} for every one of the n_runs runs;
    a run absent from it counts as incomplete.

    Precedence: an integrity gate (V1-3, V2, V3, V5, V6) failing -> NO VERDICT (the run evidence itself cannot be trusted);
    any divergence -> FAIL, even when other runs failed for infrastructure reasons or are incomplete; infrastructure / incomplete
    -> NO VERDICT; otherwise the criteria. comparison may be None when the runs never completed."""
    if not confirmatory:
        raise AcceptError("no exploratory candidate verdicts under this protocol (section 3); only confirmatory candidates are evaluated")
    if "V4" in validity:
        raise AcceptError("V4 (all runs complete) is derived from run_classes; do not pass it separately")
    missing = [g for g in ("V1", "V2", "V3", "V5") if g not in validity]
    if missing:
        raise AcceptError(f"validity gates not reported: {missing}")
    unknown = sorted(r for r, c in run_classes.items() if c not in RUN_CLASSES)
    if unknown:
        raise AcceptError(f"unclassified runs: {unknown}")
    if len(run_classes) > n_runs:
        raise AcceptError(f"{len(run_classes)} runs reported, expected {n_runs}")
    bad = sorted(g for g, ok in validity.items() if ok is False)
    if bad:
        return {"verdict": "NO VERDICT", "reason": f"validity gate(s) failed: {bad}"}
    div = sorted(r for r, c in run_classes.items() if c == "divergence")
    if div:
        return {"verdict": "FAIL", "reason": f"divergence in {div}"}
    inf = sorted(r for r, c in run_classes.items() if c == "infrastructure")
    inc = sorted(r for r, c in run_classes.items() if c == "incomplete")
    absent = n_runs - len(run_classes)
    if inf or inc or absent:
        return {"verdict": "NO VERDICT", "reason": f"V4 failed: infrastructure failure after {MAX_ATTEMPTS} attempts {inf}, "
                                                   f"incomplete {inc}, unreported runs {absent}"}
    if comparison is None:
        raise AcceptError("all runs ok but no comparison supplied")
    failed = sorted(n for n, c in comparison["criteria"].items() if not c["pass"])
    return {"verdict": "FAIL", "reason": f"criteria failed: {failed}"} if failed else {"verdict": "ACCEPT", "reason": "all criteria pass"}


def winner(candidates: list) -> dict | None:
    """Section 10.2. candidates: [{"name", "verdict", "delta", "pb_lower", "n_params", "registered_at" (ISO 8601 UTC)}]."""
    ok = [c for c in candidates if c["verdict"] == "ACCEPT"]
    if not ok:
        return None
    return sorted(ok, key=lambda c: (-c["delta"], -c["pb_lower"], c["n_params"], c["registered_at"]))[0]


# ------------------------------------------------------------------------------------------------------------- runs and budget
def collapse_share(confusion) -> float:
    """Largest predicted-class share of a run's inner-validation GT-box confusion matrix (rows true, columns predicted)."""
    col = np.asarray(confusion).sum(0)
    return float(col.max() / col.sum())


def classify_run(*, completed: bool, attempts: int, loss_nonfinite: bool, inner_confusion=None,
                 exception_outside_compute: bool | None = None, manifest_ok: bool = True) -> str:
    """Section 9. Divergence is checked first: a NaN/inf loss (in any attempt) or a collapse is a recipe failure and is never retried.
    A run that did not complete is an infrastructure failure only if its exception was raised outside the forward / backward / loss
    computation (CUDA runtime error, out of memory, timeout, lost session); it is retried up to MAX_ATTEMPTS. Any other non-completion
    is "incomplete" (gate 4 fails for a reason not covered above) and is not retried. A completed run whose genuine training
    manifest is missing or does not verify (section 10.3 condition 1) is "incomplete": its evidence is not usable."""
    if loss_nonfinite:
        return "divergence"
    if completed:
        if inner_confusion is None:
            raise AcceptError("completed run without its inner-validation confusion matrix")
        if collapse_share(inner_confusion) >= COLLAPSE_SHARE:
            return "divergence"
        return "ok" if manifest_ok else "incomplete"
    if exception_outside_compute is None:
        raise AcceptError("run did not complete: state whether its exception was raised outside the forward/backward/loss computation")
    if not exception_outside_compute:
        return "incomplete"
    if attempts >= MAX_ATTEMPTS:
        return "infrastructure"
    raise AcceptError(f"run not complete after {attempts} attempt(s): retry with the identical config and seed")


def budget(registry: list) -> dict:
    """Section 9 / 10.1. registry entries: {"name", "family", "status"}; status one of "registered", "started" (training began;
    any later outcome), "withdrawn", "pre_training_validity_failure". A slot is used by started and withdrawn candidates; a
    registered, not yet started candidate reserves its slot (it cannot be withdrawn for free); a pre-training validity failure frees it."""
    used, reserved = {f: 0 for f in FAMILY_CAP}, {f: 0 for f in FAMILY_CAP}
    for e in registry:
        if e["family"] not in FAMILY_CAP:
            raise AcceptError(f"{e['name']}: unknown family {e['family']}")
        if e["status"] in ("started", "withdrawn"):
            used[e["family"]] += 1
        elif e["status"] == "registered":
            reserved[e["family"]] += 1
        elif e["status"] != "pre_training_validity_failure":
            raise AcceptError(f"{e['name']}: unknown status {e['status']}")
    held = {f: used[f] + reserved[f] for f in FAMILY_CAP}
    if any(n > FAMILY_CAP[f] for f, n in held.items()) or sum(held.values()) > K_LIFETIME:
        raise AcceptError(f"budget exceeded: {held} (caps {FAMILY_CAP}, lifetime {K_LIFETIME})")
    return {"used": used, "reserved": reserved, "total_used": sum(used.values()), "remaining": K_LIFETIME - sum(held.values())}


# ------------------------------------------------------------------------------------------------------------- validity gates
def check_fold_file(path) -> dict:
    got = CV.sha256_file(path)
    return {"sha256": got, "expected": CV.FOLD_FILE_SHA256, "pass": got == CV.FOLD_FILE_SHA256}


def gate_r(y, stored: dict, recomputed: dict) -> dict:
    """Section 4.3. stored / recomputed: {run: {"gt": (n, C), "det": (n, C) with NaN rows unmatched, "idx": (n,)}}; y indexed by idx.
    R1 exact argmax (and identical matched set); R2 max |p diff| <= R2_TOL; R3 argmax metrics identical; ECE / NLL reported."""
    rows, mism, maxd, r3 = {}, 0, 0.0, True
    if sorted(stored) != sorted(recomputed):
        return {"pass": False, "reason": "run sets differ", "stored": sorted(stored), "recomputed": sorted(recomputed)}
    for run in sorted(stored):
        a, b = stored[run], recomputed[run]
        if not np.array_equal(a["idx"], b["idx"]):
            return {"pass": False, "reason": f"{run}: finding index differs"}
        yy = np.asarray(y)[a["idx"]]
        rr = {}
        for st in ("gt", "det"):
            pa, pb = np.asarray(a[st], float), np.asarray(b[st], float)
            ma, mb = ~np.isnan(pa).any(1), ~np.isnan(pb).any(1)
            if not np.array_equal(ma, mb):
                return {"pass": False, "reason": f"{run} {st}: matched set differs"}
            la, lb = pa[ma].argmax(1), pb[ma].argmax(1)
            n_mis = int((la != lb).sum())
            d = float(np.abs(pa[ma] - pb[ma]).max()) if ma.any() else 0.0
            ra, rb = DK.report(yy[ma], la, pa[ma]), DK.report(yy[ma], lb, pb[ma])
            same = all(ra[k] == rb[k] for k in ("accuracy", "macro_f1", "per_class", "confusion"))
            mism += n_mis
            maxd = max(maxd, d)
            r3 &= same
            rr[st] = {"argmax_mismatches": n_mis, "max_abs_prob_diff": d, "argmax_metrics_identical": same,
                      "ece_diff": rb["ece_10bin"] - ra["ece_10bin"], "nll_diff": rb["nll"] - ra["nll"]}
        rows[run] = rr
    return {"R1_argmax_mismatches": mism, "R2_max_abs_prob_diff": maxd, "R2_tolerance": R2_TOL, "R3_identical": bool(r3),
            "pass": mism == 0 and maxd <= R2_TOL and bool(r3), "runs": rows}


def dhash(path, size=8) -> int:
    """Identical to scripts/check_leakage.py dhash (64-bit difference hash of a 9x8 grayscale thumbnail)."""
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    return int("".join("1" if v else "0" for v in (a[:, 1:] > a[:, :-1]).flatten()), 2)


def thumb(path) -> np.ndarray:
    """Standardised 256x128 grayscale thumbnail, as in scripts/check_leakage.py (Pearson correlation = mean of the product)."""
    from PIL import Image
    with Image.open(path) as im:
        a = np.asarray(im.convert("L").resize((256, 128), Image.BILINEAR), dtype=np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)


def gate_v6(imports: list, protected: list, max_hamming=4, min_corr=0.97) -> dict:
    """Section 3.1 item 4. imports / protected: [{"id", "group", "sha256", "path", ("role")}]; protected = CV pool, calibration,
    test and eval_locked images. A hit on group, SHA-256, or dHash <= 4 confirmed by correlation >= 0.97 refuses the import."""
    pg = {p["group"]: p for p in protected}
    ps = {p["sha256"]: p for p in protected}
    ph = [(dhash(p["path"]), p) for p in protected]
    thumbs = {}

    def th(r):
        if r["path"] not in thumbs:
            thumbs[r["path"]] = thumb(r["path"])
        return thumbs[r["path"]]

    hits = []
    for r in imports:
        if r["group"] in pg:
            hits.append({"import": r["id"], "rule": "group", "protected": pg[r["group"]]["id"]})
        if r["sha256"] in ps:
            hits.append({"import": r["id"], "rule": "sha256", "protected": ps[r["sha256"]]["id"]})
        h = dhash(r["path"])
        for hp, p in ph:
            if bin(h ^ hp).count("1") <= max_hamming and p["sha256"] != r["sha256"]:
                c = float((th(r) * th(p)).mean())
                if c >= min_corr:
                    hits.append({"import": r["id"], "rule": "near_duplicate", "protected": p["id"], "correlation": c})
    return {"imports": len(imports), "protected": len(protected), "hits": hits, "pass": not hits,
            "rule": f"group identity; SHA-256; dHash Hamming <= {max_hamming} confirmed by thumbnail correlation >= {min_corr}"}


# ------------------------------------------------------------------------------------------------------------- V-a
def training_manifest(*, run: str, fold: int, seed: int, cfg: dict, fit_rows: list, inner_rows: list, imports: list,
                      checkpoint_path, fold_file_sha256: str, best_epoch: int, fit_arrays_sha256: str,
                      inner_arrays_sha256: str, trainer: str = "dentamind_kaggle:train_run") -> dict:
    """Per-run training manifest written by the run itself right after its checkpoint is saved (section 10.3 condition 1).
    Rows are split-CSV rows (project_image_id, image_sha256, image_path, source_dataset); imports likewise. fit / inner arrays are
    the exact crop arrays the run trained and selected its epoch on (their file SHA-256)."""
    def imgs(rows):
        seen = {}
        for r in rows:
            k = r["project_image_id"]
            seen.setdefault(k, {"image_id": k, "content_sha256": r["image_sha256"], "file_path": r["image_path"],
                                "dataset_source": r["source_dataset"], "n_items": 0})["n_items"] += 1
        return list(seen.values())
    images = {"train": imgs(list(fit_rows) + list(imports)), "val": imgs(inner_rows)}
    return {"format": "dentamind-training-manifest-v1", "created": datetime.now(timezone.utc).isoformat(), "task": "findings_classification",
            "annotation_level": "finding", "images": images, "counts": {k: len(v) for k, v in images.items()},
            "seed": seed, "training_config": cfg, "cv": {"run": run, "fold": fold, "seed": seed, "fold_file_sha256": fold_file_sha256,
                                                          "best_epoch": int(best_epoch), "fit_arrays_sha256": fit_arrays_sha256,
                                                          "inner_arrays_sha256": inner_arrays_sha256, "trainer": trainer,
                                                          "imports": len(imports), "protocol": PROTOCOL},
            "checkpoint_file": Path(checkpoint_path).name, "checkpoint_bytes": Path(checkpoint_path).stat().st_size,
            "checkpoint_sha256": CV.sha256_file(checkpoint_path),
            "excluded_by_design": "held-out fold, calibration and test radiographs are never read by this run's training"}


def write_training_manifest(checkpoint_path, manifest: dict) -> dict:
    """Same file convention as dentexmodel.training.provenance.write: <checkpoint stem>.training_manifest.json beside the checkpoint."""
    p = Path(checkpoint_path)
    m = p.with_name(p.stem + ".training_manifest.json")
    m.write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return {"file": m.name, "sha256": CV.sha256_file(m), "format": manifest["format"], "counts": manifest["counts"]}


def _sums(artifact_dir: Path) -> dict:
    out = {}
    for line in (artifact_dir / "SHA256SUMS.txt").read_text().splitlines():
        h, name = line.split(maxsplit=1)
        out[name.lstrip("*").replace("\\", "/")] = h
    return out


def heldout_report(artifact_dir, run: str, pool_y, *, checkpoint_path, training_manifest_path, model_id: str, version: str) -> dict:
    """Section 10.3: the eval_<version>_val.json for the V-a final artifact, from STORED held-out predictions only (no inference).
    pool_y: true class index of every CV pool finding in POOL order (train + validation rows of the combined splits), which is the
    index space of heldout_pred.npz "idx". Refuses unless the run is fold 0 / seed 42, the archive files verify, and the checkpoint hash agrees in all four places."""
    a = Path(artifact_dir)
    if not run.endswith(f"_f{FINAL_FOLD}_s{FINAL_SEED}"):
        raise AcceptError(f"{run}: the final artifact is fold {FINAL_FOLD}, seed {FINAL_SEED} (section 10.3)")
    sums = _sums(a)
    for f in (f"runs/{run}__heldout_pred.npz", f"runs/{run}__cv_run.json", "checkpoint_manifest.json"):
        if sums.get(f) != CV.sha256_file(a / f):
            raise AcceptError(f"{f} does not match SHA256SUMS.txt")
    cvr = json.loads((a / "runs" / f"{run}__cv_run.json").read_text())
    ck = json.loads((a / "checkpoint_manifest.json").read_text())[run]["sha256"]
    tm = json.loads(Path(training_manifest_path).read_text(encoding="utf-8"))
    got = CV.sha256_file(checkpoint_path)
    shas = {"checkpoint_file": got, "cv_run.json": cvr["checkpoint_sha256"], "checkpoint_manifest.json": ck,
            "training_manifest": tm.get("checkpoint_sha256")}
    if len(set(shas.values())) != 1:
        raise AcceptError(f"checkpoint SHA-256 disagrees: {shas}")
    if tm.get("cv", {}).get("trainer", DEFAULT_TRAINER) not in REAL_TRAINERS:
        raise AcceptError(f"{run}: trained by {tm['cv']['trainer']} (pre-flight), not by the real trainer")
    if tm.get("cv", {}).get("run") != run or cvr["fold"] != FINAL_FOLD or cvr["seed"] != FINAL_SEED:
        raise AcceptError("training manifest or cv_run.json does not describe this run")
    d = np.load(a / "runs" / f"{run}__heldout_pred.npz", allow_pickle=False)
    yy = np.asarray(pool_y)[d["idx"]]
    gt, det = d["gt"].astype(float), d["det"].astype(float)
    m = ~np.isnan(det).any(1)
    metrics = {"gt": DK.report(yy, gt.argmax(1), gt), "det_matched": DK.report(yy[m], det[m].argmax(1), det[m])}
    return {"generated": datetime.now(timezone.utc).isoformat(), "model_version": version, "model_id": model_id,
            "task": "findings_classification", "split": "held-out CV fold 0 (stored predictions)", "n_images": None,
            "n_findings": int(len(yy)), "n_detector_matched": int(m.sum()), "final_test": False, "metrics": metrics,
            "checkpoint_sha256": got, "source": {"artifact_dir": str(a), "run": run, "heldout_pred_sha256": sums[f"runs/{run}__heldout_pred.npz"]},
            "no_new_inference": True, "disclosure": DISCLOSURE, "protocol": PROTOCOL}


# ------------------------------------------------------------------------------------------------------------- candidate runs (section 9)
# A candidate run is trained in a fresh process (as DK.train_run_isolated does) by worker(), which calls the unchanged trainer
# DK.train_run, records where any exception came from, and - right after the trainer has saved and hashed best.pth, in the same
# process - writes that run's training manifest. run_isolated() retries only infrastructure failures, at most MAX_ATTEMPTS in total
# per run (also across resumed sessions); a computation exception, a non-finite loss or a failed manifest write is final and never
# retried. run_status() turns the files of one run directory into its section-9 class.
INFRA_MARKERS = ("cuda out of memory", "cuda error: out of memory", "cudnn_status_alloc_failed", "cublas_status_alloc_failed",
                 "illegal memory access", "unspecified launch failure", "cuda driver version is insufficient",
                 "no cuda gpus are available", "uncorrectable ecc error", "cuda error: launch timed out")
NOT_INFRA_MARKERS = ("device-side assert",)     # a kernel assert (e.g. a label out of range) is a computation fault
KILLED_RETURNCODES = (-9, 137)                  # SIGKILL (OOM killer / session teardown); any other silent exit is ambiguous
ATTEMPTS_FILE, FAILURE_FILE, PREDICTION_FAILURES_FILE = "run_attempts.json", "run_failure.json", "prediction_failures.json"
CHECKPOINT_NAME = "best.pth"
MANIFEST_NAME = "best.training_manifest.json"
DEFAULT_TRAINER = "dentamind_kaggle:train_run"
INTERVENTION_TRAINER = "cv5_interventions:train_run"    # candidate configs with intervention keys in ExpConfig.extra
REAL_TRAINERS = (DEFAULT_TRAINER, INTERVENTION_TRAINER)
PREFLIGHT_TRAINER_ENV = "DENTAMIND_PREFLIGHT_TRAINER"   # pre-flight only: fake trainer "module:function"; runs are never eligible


def trainer_for(cfg) -> str:
    """The real trainer for a config: DK.train_run for the BASE recipe (no extra), the intervention trainer otherwise."""
    return INTERVENTION_TRAINER if getattr(cfg, "extra", None) else DEFAULT_TRAINER


def exception_origin(exc: BaseException) -> str:
    """Section 9. "infrastructure" only for clearly recognised failures of the machine rather than the recipe: out-of-memory (device
    or host; torch.cuda.OutOfMemoryError), CUDA illegal memory access / unspecified launch failure, missing or broken GPU driver, ECC
    error, kernel launch timeout. Anything else - including other "CUDA error: ..." messages and cuDNN / cuBLAS status errors that
    can be caused by the computation - is "computation": ambiguous failures are never retried automatically. Timeouts and
    processes killed by SIGKILL are classified as infrastructure by run_isolated()."""
    msg = f"{type(exc).__name__}: {exc}".lower()
    if any(m in msg for m in NOT_INFRA_MARKERS):
        return "computation"
    if isinstance(exc, MemoryError) or type(exc).__name__ == "OutOfMemoryError":
        return "infrastructure"
    if isinstance(exc, RuntimeError) and any(m in msg for m in INFRA_MARKERS):
        return "infrastructure"
    return "computation"


def nonfinite_loss(history) -> bool:
    """Section 9 (i): training loss NaN or +-inf at any logged step (the per-epoch train_loss that DK.train_run logs)."""
    return any(not np.isfinite(float(h["train_loss"])) for h in history or [])


def _read(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default


def _write(p: Path, obj) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    tmp.replace(p)


def _state_history(run_dir: Path) -> list:
    """Epoch history saved by DK.train_run in state.pt (used to detect a non-finite loss before an exception)."""
    st = run_dir / "state.pt"
    if not st.is_file():
        return []
    try:
        import torch
        return list(torch.load(st, map_location="cpu", weights_only=False).get("hist") or [])
    except Exception:                           # unreadable state: no evidence either way
        return []


def write_rows(path, fit_rows: list, inner_rows: list, imports: list = ()) -> Path:
    """The rows a fold's runs train / select their epoch on, as passed to the worker for its manifest."""
    keep = ("sample_id", "project_image_id", "image_sha256", "image_path", "source_dataset", "radiograph_group", "target_class")
    trim = lambda rows: [{k: r[k] for k in keep if k in r} for r in rows]      # noqa: E731
    p = Path(path)
    _write(p, {"fit": trim(fit_rows), "inner": trim(inner_rows), "imports": trim(imports)})
    return p


def _resolve(spec: str):
    import importlib
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)


def _write_run_manifest(spec: dict, res: dict, out: Path) -> dict:
    ck = out / CHECKPOINT_NAME
    if not ck.is_file():
        raise AcceptError(f"{ck} missing after training")
    if CV.sha256_file(ck) != res["checkpoint_sha256"]:
        raise AcceptError("checkpoint on disk differs from the hash the trainer recorded")
    if res["config"] != spec["cfg"] or int(res["seed"]) != int(spec["seed"]):
        raise AcceptError("trainer result does not describe this run's config / seed")
    rows = json.loads(Path(spec["rows_json"]).read_text(encoding="utf-8"))
    m = training_manifest(run=spec["run"], fold=spec["fold"], seed=spec["seed"], cfg=res["config"], fit_rows=rows["fit"],
                          trainer=spec.get("trainer", DEFAULT_TRAINER),
                          inner_rows=rows["inner"], imports=rows.get("imports", []), checkpoint_path=ck,
                          fold_file_sha256=spec["fold_file_sha256"], best_epoch=res["best_epoch"],
                          fit_arrays_sha256=CV.sha256_file(spec["fit_npz"]), inner_arrays_sha256=CV.sha256_file(spec["inner_npz"]))
    ref = write_training_manifest(ck, m)
    side = ck.with_suffix(".json")              # registry sidecar written by the trainer; test_ledger reads training_manifest from it
    if side.is_file():
        meta = json.loads(side.read_text(encoding="utf-8"))
        meta["training_manifest"] = ref
        side.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return ref


def worker(spec: dict) -> int:
    """One training attempt in a fresh process. Writes <run>/attempt_<n>.json: status "completed" (trained, manifest written),
    "exception" (with origin) or "manifest_failed". Exit code 0 only for "completed"."""
    import traceback
    out = Path(spec["out"]) / spec["run"]
    out.mkdir(parents=True, exist_ok=True)
    rec_path = out / f"attempt_{spec['attempt']}.json"
    rec = {"attempt": spec["attempt"], "run": spec["run"], "fold": spec["fold"], "seed": spec["seed"],
           "started": datetime.now(timezone.utc).isoformat()}
    load = lambda f: (lambda z: {"X": z["X"], "y": z["y"]})(np.load(f))     # noqa: E731  (as DK._worker)
    rec["trainer"] = spec.get("trainer", DEFAULT_TRAINER)
    rec["preflight"] = rec["trainer"] not in REAL_TRAINERS
    if (out / "result.json").is_file() or (out / CHECKPOINT_NAME).is_file():
        rec.update(status="manifest_failed", stage="start", origin=None, type="StaleArtifacts",
                   message="checkpoint or result.json present before this attempt trained: refusing a late manifest")
        _write(rec_path, rec)
        return 4
    try:
        res = _resolve(spec.get("trainer", DEFAULT_TRAINER))(DK.ExpConfig(**spec["cfg"]), spec["seed"], load(spec["fit_npz"]),
                                                             load(spec["inner_npz"]), spec["out"], log=print)
    except Exception as e:
        rec.update(status="exception", stage="training", origin=exception_origin(e), type=type(e).__name__, message=str(e)[:2000],
                   traceback=traceback.format_exc()[-4000:], loss_nonfinite=nonfinite_loss(_state_history(out)))
        _write(rec_path, rec)
        return 3
    rec.update(loss_nonfinite=nonfinite_loss(res.get("history")), best_epoch=res.get("best_epoch"),
               checkpoint_sha256=res.get("checkpoint_sha256"))
    try:
        rec["manifest"] = _write_run_manifest(spec, res, out)
    except Exception as e:
        rec.update(status="manifest_failed", stage="manifest", origin=None, type=type(e).__name__, message=str(e)[:2000],
                   traceback=traceback.format_exc()[-4000:])
        _write(rec_path, rec)
        return 4
    rec["status"] = "completed"
    _write(rec_path, rec)
    return 0


def _final(out: Path, cls: str, reason: str, entry: dict | None = None) -> dict:
    f = {"class": cls, "reason": reason, "recorded": datetime.now(timezone.utc).isoformat(), "attempt": entry}
    _write(out / FAILURE_FILE, f)
    return {"status": "final_failure", **f}


def run_isolated(cfg, seed: int, fold: int, fit_npz, inner_npz, rows_json, runs_dir, *, fold_file_sha256=CV.FOLD_FILE_SHA256,
                 log=print, attempts=MAX_ATTEMPTS, timeout_s=3 * 3600, trainer=None, extra_path=(), python=None) -> dict:
    """Train one candidate run with section-9 retry rules. Returns {"status": "completed" | "final_failure" |
    "infrastructure_exhausted", ...}. Attempts are counted in <run>/run_attempts.json and persist across resumed sessions."""
    import dataclasses
    import os
    import subprocess
    import sys
    trainer = trainer or os.environ.get(PREFLIGHT_TRAINER_ENV) or trainer_for(cfg)
    run = f"{cfg.name}_s{seed}"
    out = Path(runs_dir) / run
    out.mkdir(parents=True, exist_ok=True)
    hist = _read(out / ATTEMPTS_FILE, [])
    final = _read(out / FAILURE_FILE)
    if final:
        return {"status": "final_failure", **final}
    if hist and hist[-1]["status"] == "completed":
        return {"status": "completed", "run": run, "attempts": hist}
    paths = [str(Path(m.__file__).resolve().parent) for m in (DK, CV, sys.modules["dsutil"])] + [str(p) for p in extra_path]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(dict.fromkeys(paths + [os.environ.get("PYTHONPATH", "")]))}
    while len(hist) < attempts:
        n = len(hist) + 1
        # An attempt that ended after the checkpoint (or result.json) was written but before its worker recorded completion has no
        # manifest. Retrying would let the trainer skip training and the worker write a manifest late: never allowed.
        left = [f for f in (CHECKPOINT_NAME, "result.json") if (out / f).is_file()]
        if left:
            return _final(out, "incomplete", f"{', '.join(left)} exists without a recorded completed attempt: no manifest was "
                                             "written by the run that created it, and none is written later", hist[-1] if hist else None)
        spec = {"run": run, "fold": fold, "seed": seed, "attempt": n, "cfg": dataclasses.asdict(cfg), "fit_npz": str(fit_npz),
                "inner_npz": str(inner_npz), "rows_json": str(rows_json), "out": str(runs_dir), "fold_file_sha256": fold_file_sha256,
                "trainer": trainer}
        p = subprocess.Popen([python or sys.executable, "-u", str(Path(__file__).resolve()), "--worker", json.dumps(spec)],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        tail = []
        try:
            for line in p.stdout:
                line = line.rstrip()
                tail = (tail + [line])[-40:]
                if line.startswith("  [") or "resumed" in line or "Error" in line:
                    log(line)
            rc = p.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = "timeout"
        rec = _read(out / f"attempt_{n}.json")
        if rc == "timeout":
            entry = {"attempt": n, "status": "exception", "stage": "training", "origin": "infrastructure", "type": "timeout",
                     "loss_nonfinite": nonfinite_loss(_state_history(out))}
        elif rec is None:                       # process died without a record
            killed = rc in KILLED_RETURNCODES
            entry = {"attempt": n, "status": "exception", "stage": "training", "origin": "infrastructure" if killed else "ambiguous",
                     "type": "killed" if killed else "exit_without_record", "returncode": rc,
                     "loss_nonfinite": nonfinite_loss(_state_history(out))}
        else:
            entry = {**rec, "returncode": rc}
        entry["tail"] = tail[-15:]
        hist.append(entry)
        _write(out / ATTEMPTS_FILE, hist)
        if entry["status"] == "completed" and rc == 0:
            log(f"[{run}] completed on attempt {n}; manifest {entry['manifest']['sha256'][:16]}")
            return {"status": "completed", "run": run, "attempts": hist}
        if entry.get("loss_nonfinite"):
            return _final(out, "divergence", "non-finite training loss", entry)
        if entry["status"] == "manifest_failed":
            return _final(out, "incomplete", f"training manifest could not be written: {entry.get('message')}", entry)
        if entry.get("origin") != "infrastructure":
            return _final(out, "incomplete", f"{entry.get('origin')} failure ({entry.get('type')}): not retried", entry)
        log(f"[{run}] attempt {n} infrastructure failure ({entry.get('type')}): " + " | ".join(tail[-4:]))
    log(f"[{run}] infrastructure failures in all {attempts} attempts")
    return {"status": "infrastructure_exhausted", "run": run, "attempts": hist}


def record_prediction_failure(run_dir, exc: BaseException) -> dict:
    """Held-out prediction failed after training. A computation fault is final (incomplete); an infrastructure fault may be
    redone on resume, at most MAX_ATTEMPTS times in total."""
    out = Path(run_dir)
    origin = exception_origin(exc)
    fails = _read(out / PREDICTION_FAILURES_FILE, []) + [{"origin": origin, "type": type(exc).__name__, "message": str(exc)[:2000]}]
    _write(out / PREDICTION_FAILURES_FILE, fails)
    if origin != "infrastructure":
        return _final(out, "incomplete", f"exception during held-out prediction ({type(exc).__name__}): not retried", fails[-1])
    if len(fails) >= MAX_ATTEMPTS:
        return _final(out, "infrastructure", f"held-out prediction failed {len(fails)} times (infrastructure)", fails[-1])
    return {"status": "retry_on_resume", "origin": origin, "failures": len(fails)}


def verify_run_manifest(run_dir, run: str, fold: int, seed: int) -> dict:
    """The run's own manifest describes this run and this checkpoint: file present and unmodified since the worker wrote it, same
    checkpoint SHA-256 as the file on disk and the trainer's record, same run / fold / seed / selected epoch / config."""
    out = Path(run_dir)
    problems = []
    ck, mp = out / CHECKPOINT_NAME, out / MANIFEST_NAME
    res, hist = _read(out / "result.json"), _read(out / ATTEMPTS_FILE, [])
    done = [h for h in hist if h.get("status") == "completed"]
    if not ck.is_file() or not mp.is_file() or res is None or not done:
        return {"ok": False, "problems": ["checkpoint, manifest, result.json or completed-attempt record missing"]}
    m = json.loads(mp.read_text(encoding="utf-8"))
    sha = CV.sha256_file(ck)
    ref = done[-1].get("manifest") or {}
    if ref.get("sha256") != CV.sha256_file(mp):
        problems.append("manifest file differs from the one the worker wrote")
    if not (sha == m.get("checkpoint_sha256") == res.get("checkpoint_sha256") == done[-1].get("checkpoint_sha256")):
        problems.append("checkpoint SHA-256 disagrees between file, manifest, result.json and attempt record")
    cvb = m.get("cv", {})
    want = {"run": run, "fold": fold, "seed": seed, "best_epoch": res.get("best_epoch")}
    for k, v in want.items():
        if cvb.get(k) != v:
            problems.append(f"manifest cv.{k} = {cvb.get(k)!r}, expected {v!r}")
    if m.get("seed") != seed or m.get("training_config") != res.get("config"):
        problems.append("manifest seed / training_config differ from result.json")
    side = _read(ck.with_suffix(".json"))
    if side is not None and (side.get("training_manifest") or {}).get("sha256") != ref.get("sha256"):
        problems.append("checkpoint sidecar does not reference this manifest")
    return {"ok": not problems, "problems": problems, "checkpoint_sha256": sha, "manifest_sha256": ref.get("sha256")}


def run_status(runs_dir, run: str, fold: int, seed: int) -> dict:
    """Section-9 class of one run from its directory: ok / divergence / infrastructure / incomplete (resumable or final)."""
    out = Path(runs_dir) / run
    base = {"run": run, "fold": fold, "seed": seed}
    if not out.is_dir():
        return {**base, "class": "incomplete", "reason": "not started", "resumable": True, "final_model_eligible": False}
    final = _read(out / FAILURE_FILE)
    hist = _read(out / ATTEMPTS_FILE, [])
    base["attempts"] = len(hist)
    base["exception_origins"] = [h.get("origin") for h in hist if h.get("status") != "completed"]
    if final:
        return {**base, "class": final["class"], "reason": final["reason"], "resumable": False, "final_model_eligible": False}
    if hist and hist[-1]["status"] == "completed":
        res = _read(out / "result.json")
        nonfinite = nonfinite_loss(res["history"]) or any(h.get("loss_nonfinite") for h in hist)
        man = verify_run_manifest(out, run, fold, seed)
        cls = classify_run(completed=True, attempts=len(hist), loss_nonfinite=nonfinite, inner_confusion=res["val_gt"]["confusion"],
                           manifest_ok=man["ok"])
        st = {**base, "class": cls, "manifest": man, "collapse_share": collapse_share(res["val_gt"]["confusion"]),
              "loss_nonfinite": nonfinite, "resumable": False}
        if cls == "ok" and not (out / "heldout_pred.npz").is_file():
            st.update({"class": "incomplete", "reason": "held-out prediction missing", "resumable": True})
        st["preflight"] = any(h.get("preflight") for h in hist)
        st["final_model_eligible"] = st["class"] == "ok" and man["ok"] and not st["preflight"]
        return st
    nonfinite = any(h.get("loss_nonfinite") for h in hist)
    try:
        cls = classify_run(completed=False, attempts=len(hist), loss_nonfinite=nonfinite,
                           exception_outside_compute=(hist[-1].get("origin") == "infrastructure") if hist else True)
        return {**base, "class": cls, "resumable": False, "final_model_eligible": False}
    except AcceptError as e:
        return {**base, "class": "incomplete", "reason": str(e), "resumable": True, "final_model_eligible": False}


def collect_status(runs_dir, expected: list) -> dict:
    """expected: [(fold, seed, run_name)] for all required runs (25). run_classes feeds verdict()."""
    st = {r: run_status(runs_dir, r, f, s) for f, s, r in expected}
    return {"runs": st, "run_classes": {r: v["class"] for r, v in st.items()}, "n_expected": len(expected),
            "all_ok": all(v["class"] == "ok" for v in st.values())}


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        sys.exit(worker(json.loads(sys.argv[2])))
