#!/usr/bin/env python
"""Generate kaggle/denta_mind_external_training.ipynb: the external-data experiment of reports/external_data_protocol.md.

    .venv\\Scripts\\python.exe kaggle\\make_external_notebook.py

Reuses the verified cells of make_notebook.py (configuration, GPU check, bundle verification, DENTEX download + SHA-256 checks,
leakage asserts, training-only class weights, crops, isolated resumable training, validation acceptance, test gating, tables and
packaging) and adds: Cluj download + crop building on Kaggle, external training sets (Hanoi cap 1,500), and the external evaluation.
"""
import json
from pathlib import Path

import make_notebook as MN

base = MN.CELLS          # [0] md, [1] config, [2] gpu, [3] bundle, [4] images, [5] checks, [6] weights, [7] crops, [8] train,
                         # [9] validation+acceptance, [10] experiment E, [11] test, [12] tables, [13] package
CELLS = []


def md(s):
    CELLS.append(("markdown", s.strip("\n")))


def code(s):
    CELLS.append(("code", s.strip("\n")))


md(r"""
# DentaMind AI - external panoramic data for the finding classifier (Kaggle GPU)

Pre-registered protocol: `reports/external_data_protocol.md` (in the bundle). Exactly one factor changes per experiment: the training data.

| Run | Training data |
|---|---|
| `BASE` | DENTEX train (same recipe as every earlier BASE: ResNet-50, 224 px tooth crops, inverse-frequency weights capped at 5) |
| `X1_cluj` | + Cluj (Zenodo 10.5281/zenodo.15487430, CC BY 4.0): Impacted, Periapical Lesion, caries of unrecorded depth as a partial label |
| `X2_hanoi` | + Hanoi (Mendeley kx52tk2ddj, CC BY 4.0): Periapical Lesion (PAI 3-5), at most 1,500 crops |
| `X3_both` | + Cluj + Hanoi |

**Amendment 2026-10-24 (before any training):** Cluj failed the protocol's visual label check (section 2; about 30 % of the
Impacted check crops show no impacted tooth because a block of Cluj images uses a different class numbering). As the protocol
requires, Cluj is withdrawn from training: only `BASE` and `X2_hanoi` are run. X1_cluj and X3_both are reported as withdrawn.
Cluj is still downloaded and cropped for the secondary external evaluation only.

Acceptance on the DENTEX validation split (project criteria, unchanged). Secondary: external evaluation on Cluj's `test` folder and
180-image multi-center set (never trained on). The DENTEX test split is read only for BASE and passing candidates.

**Before running:** GPU T4/P100, Internet **On**, Add Input -> the private dataset with `dentamind_kaggle_bundle.zip`
(built with `kaggle/build_kaggle_bundle.py --with-deployed-checkpoint --with-external`).
""")

cfg = base[1][1].replace(
    'RUN = ["BASE", "REF_unweighted", "A1_sqrt_weights", "A2_effnum_weights", "B_sampler", "C_focal", "D_official_val"]',
    'RUN = ["BASE", "X2_hanoi"]                # X1_cluj / X3_both withdrawn: Cluj failed the label check (protocol amendment)').replace(
    "RUN_E = True                          # combination run, only if justified by the acceptance rule",
    "RUN_E = False                         # not part of this protocol").replace(
    'SEEDS, RUN = [42, 43], ["BASE", "B_sampler", "D_official_val"]',
    'SEEDS, RUN = [42, 43], ["BASE", "X2_hanoi"]')
assert 'RUN = ["BASE", "X2_hanoi"]' in cfg
cfg += r"""

HANOI_CAP = 1500                       # protocol section 3 (fixed before any result)
CLUJ = {"url": "https://zenodo.org/records/15487430/files/panoramic_radiography_yolo_dataset_14_classes.zip?download=1",
        "bytes": 1397393531, "md5": "18d5acaea021f4f3b05b76e9a27fbd42"}
SKIP_CLUJ = os.environ.get("DM_SKIP_CLUJ") == "1"     # local smoke test only
if SMOKE:
    RUN_TEST_EVAL = False             # a pipeline check must never touch the test split
"""
code(cfg)
for k in (2, 3, 4, 5, 6, 7):
    src = base[k][1]
    if k == 3:   # local smoke-test copy also needs the external inputs
        src = src.replace('"docs/audit_evidence/ml_improvement/imbalance/results.json"):',
                          '"docs/audit_evidence/ml_improvement/imbalance/results.json", "data/external_crops/hanoi/crops.npz",\n'
                          '                  "data/external_crops/hanoi/manifest.csv", "data/checkpoints/dentex_teeth_detection_v1.pth"):')
    code(src)

code(r"""
# ---- 7a. Cluj: download from Zenodo, verify, build tooth crops with the production detector (protocol section 2) ---------
import hashlib, csv
def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

EXT_OUT = CACHE / "external_crops"
CLUJ_DIR = DATA_ROOT / "cluj"
if not SKIP_CLUJ:
    zp = DATA_ROOT / "_archives/cluj.zip"
    t = time.time()
    DX.download(CLUJ["url"], zp, CLUJ["bytes"], None)
    assert md5_file(zp) == CLUJ["md5"], "Cluj archive MD5 differs from the Zenodo record"
    if not CLUJ_DIR.exists():
        DX.safe_extract(zp, CLUJ_DIR)
    log(f"Cluj archive verified (MD5 {CLUJ['md5']}) and extracted in {time.time() - t:.0f}s")
    os.environ.update(DM_CLUJ_DIR=str(CLUJ_DIR), DM_EXT_OUT=str(EXT_OUT),
                      DM_DET_CKPT=str(CODE / "data/checkpoints/dentex_teeth_detection_v1.pth"))
    import external_crops as EC
    folders = collections.Counter(p.relative_to(CLUJ_DIR).parts[0] if len(p.relative_to(CLUJ_DIR).parts) > 1 else "."
                                  for p in CLUJ_DIR.rglob("*") if p.is_file())
    log("Cluj archive layout (top folders: files):", dict(folders))
    t = time.time()
    EC.build("cluj")
    log(f"Cluj crops built in {time.time() - t:.0f}s")
""")

code(r"""
# ---- 7b. external training sets (Hanoi cap 1,500 by whole radiographs, seed 42) + leakage checks --------------------------
import random
from dsutil import read_csv, dhash, near_duplicate_pairs
def load_ext(folder):
    z = np.load(folder / "crops.npz")
    return z["X"], z["y"], read_csv(folder / "manifest.csv")

Xh, yh, mh = load_ext(CODE / "data/external_crops/hanoi")
groups = sorted({r["radiograph_group"] for r in mh})
random.Random(42).shuffle(groups)
take, n = set(), 0
by_g = collections.Counter(r["radiograph_group"] for r in mh)
for g in groups:
    if n >= HANOI_CAP:
        break
    take.add(g)
    n += by_g[g]
sel_h = np.array([r["radiograph_group"] in take for r in mh])
log(f"Hanoi: {len(mh)} crops available, {sel_h.sum()} selected from {len(take)} radiographs (cap {HANOI_CAP})")

EXT_EVAL = None
if not SKIP_CLUJ:
    Xc, yc, mc = load_ext(EXT_OUT / "cluj")
    roles = np.array([r["role"] for r in mc])
    log("Cluj crops per folder and role:", dict(collections.Counter((r["subset"], r["role"]) for r in mc)))
    assert (roles == "train").any(), "no Cluj training folder recognised (expected train/ or valid/): check the archive layout above"
    # leakage: Cluj vs DENTEX evaluation radiographs, and Cluj train vs Cluj eval (exact + near duplicates)
    ev_imgs = {r["image_path"] for s in ("validation", "calibration", "test") for r in ROWS[s]}
    items = [("dentex:" + p, None, dhash(DATA_ROOT / p), DATA_ROOT / p) for p in sorted(ev_imgs)]
    cl_imgs = sorted({(r["image_path"], r["role"], r["image_sha256"]) for r in mc})
    items += [(f"cluj-{role}:{p}", sha, dhash(CLUJ_DIR / p.split('/', 1)[1]), CLUJ_DIR / p.split('/', 1)[1]) for p, role, sha in cl_imgs]
    near, n_cand, _ = near_duplicate_pairs(items)
    sha_count = collections.Counter(sha for _, _, sha in cl_imgs)
    bad = set()
    for a, b, d, r in near:
        kinds = {a.split(":")[0], b.split(":")[0]}
        if kinds != {"cluj-train"} and kinds != {"cluj-eval"}:          # crosses train/eval or touches DENTEX evaluation
            bad |= {x.split(":", 1)[1] for x in (a, b) if x.startswith("cluj-train")}
    exact_cross = {p for p, role, sha in cl_imgs if role == "train" and any(s == sha and rl == "eval" for _, rl, s in cl_imgs)}
    bad |= exact_cross
    keep_c = np.array([(r["role"] == "train") and (r["image_path"] not in bad) for r in mc])
    EXT_EVAL = {"X": Xc[roles == "eval"], "y": yc[roles == "eval"], "subset": np.array([r["subset"] for r in mc])[roles == "eval"]}
    leak = {"near_candidates": n_cand, "near_confirmed": len(near), "cluj_train_images_removed": len(bad)}
    log("Cluj leakage check:", leak, "| train crops kept:", int(keep_c.sum()), "| eval crops:", len(EXT_EVAL["y"]))
    (ART / "external_leakage_check.json").write_text(json.dumps({**leak, "pairs": near[:50], "removed": sorted(bad)}, indent=1))

def cat(*parts):
    return {"X": np.concatenate([p[0] for p in parts]), "y": np.concatenate([p[1] for p in parts])}
dx = (TRAIN["dentex"]["X"], TRAIN["dentex"]["y"])
hh = (Xh[sel_h], yh[sel_h])
TRAIN["dentex+hanoi"] = cat(dx, hh)
if not SKIP_CLUJ:
    cc = (Xc[keep_c], yc[keep_c])
    TRAIN["dentex+cluj"] = cat(dx, cc)
    TRAIN["dentex+cluj+hanoi"] = cat(dx, cc, hh)
ext_dist = {k: {"counts_full_labels": dict(zip(CLASSES, DK.class_counts(v["y"]).tolist())),
                "partial_caries": int((v["y"] == DK.PARTIAL_CARIES).sum()),
                "class_weights": dict(zip(CLASSES, np.round(DK.class_weights(DK.class_counts(v["y"]), "inverse_cap5"), 4).tolist()))}
            for k, v in TRAIN.items()}
log(json.dumps(ext_dist, indent=1))
(ART / "external_training_sets.json").write_text(json.dumps(ext_dist, indent=1))
RUN = [r for r in RUN if DK.EXPERIMENTS[r].data in TRAIN]
""")

code(base[8][1])     # training (isolated, resumable)
code(base[9][1])     # validation evaluation + acceptance (unchanged rule)
code(r"""
# ---- 9b. external evaluation on Cluj test + multi-center sets (never trained on; secondary, protocol section 5) --------------
def ext_metrics(prob, y):
    pred = prob.argmax(1)
    out = {}
    for name, cls_true, ok in (("Impacted recall", 2, lambda p: p == 2), ("Periapical Lesion recall", 3, lambda p: p == 3),
                               ("caries-any recall", DK.PARTIAL_CARIES, lambda p: (p == 0) | (p == 1))):
        m = y == cls_true
        out[name] = {"n": int(m.sum()), "value": float(ok(pred[m]).mean()) if m.any() else None}
    return out

EXTERNAL = {}
if EXT_EVAL is not None and len(EXT_EVAL["y"]):
    import torch, torchvision as tv
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for name in RUN:
        EXTERNAL[name] = {}
        for sd in SEEDS:
            ck = RUNS / f"{name}_s{sd}" / "best.pth"
            if not ck.is_file():
                continue
            m = DK.new_model(torch, tv, pretrained=False)
            m.load_state_dict(torch.load(ck, map_location="cpu", weights_only=True))
            prob = DK.predict(torch, m.to(dev), EXT_EVAL["X"], dev)
            EXTERNAL[name][sd] = {sub: ext_metrics(prob[EXT_EVAL["subset"] == sub], EXT_EVAL["y"][EXT_EVAL["subset"] == sub])
                                  for sub in sorted(set(EXT_EVAL["subset"]))}
            del m
    for name, res in EXTERNAL.items():
        for sub in sorted(set(EXT_EVAL["subset"])):
            vals = {k: [res[s][sub][k]["value"] for s in res if res[s][sub][k]["value"] is not None] for k in ("Impacted recall", "Periapical Lesion recall", "caries-any recall")}
            log(f"external {name:10s} {sub:10s} " + "  ".join(f"{k} {np.mean(v):.3f}+-{np.std(v, ddof=1) if len(v) > 1 else 0:.3f}" for k, v in vals.items() if v))
(ART / "external_eval.json").write_text(json.dumps({k: {str(s): v for s, v in d.items()} for k, d in EXTERNAL.items()}, indent=1))
E_NOTE = "not part of this protocol"
""")
code(base[11][1])    # test split: BASE + passing candidates only
code(base[12][1])    # tables, plots, selection
pkg = base[13][1].replace('"class_distribution_and_weights.json", "confusion_matrices_validation.png", "minority_class_metrics.png"):',
                          '"class_distribution_and_weights.json", "confusion_matrices_validation.png", "minority_class_metrics.png",\n'
                          '          "external_eval.json", "external_training_sets.json", "external_leakage_check.json"):')
pkg = pkg.replace("dentamind_balanced_training_artifacts.zip", "dentamind_external_data_artifacts.zip")
pkg = pkg.replace('"# DentaMind balanced-training artifacts"', '"# DentaMind external-data artifacts (protocol: reports/external_data_protocol.md)"')
assert "external_eval.json" in pkg
code(pkg)


def build():
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu", "isInternetEnabled": True}},
          "cells": []}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    out = Path(__file__).resolve().parent / "denta_mind_external_training.ipynb"
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(CELLS)} cells)")


if __name__ == "__main__":
    build()
