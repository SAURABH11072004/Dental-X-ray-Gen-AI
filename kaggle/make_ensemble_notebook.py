#!/usr/bin/env python
"""Generate kaggle/denta_mind_ensemble_eval.ipynb: runs kaggle/ensemble_eval.py unchanged in the Kaggle environment that produced the
BASE numbers (protocol reports/ensemble_protocol.md; the local re-evaluation failed the section-4 reproduction gate).

Inputs to attach on Kaggle: the private bundle dataset (dentamind_kaggle_bundle) and the OUTPUT of the notebook
"DentaMind external data training" (holds runs/BASE_s4x/best.pth and validation_eval.json). Internet on (DENTEX images).
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "ensemble_eval.py").read_text(encoding="utf-8")
SRC_SHA = hashlib.sha256(SRC.encode("utf-8")).hexdigest()

CELLS = [("markdown", """# DentaMind AI - 5-seed BASE ensemble, validation only (Kaggle GPU)

Protocol: `reports/ensemble_protocol.md`. Mean of the five BASE members' softmax probabilities; no tuning. The DENTEX **test split is
never loaded**. This runs the same script as locally (`kaggle/ensemble_eval.py`, embedded below and hash-checked) in the Kaggle
environment that produced the BASE numbers, because the local re-evaluation failed the reproduction gate (software differences).

**Before running:** GPU T4, Internet On, Add Input -> (1) the private bundle dataset, (2) Notebook output "DentaMind external data
training"."""),
         ("code", f"""# ---- 1. inputs: bundle code + previous run's checkpoints; write the ensemble script ----------------------------------
import glob, hashlib, json, sys, time
from pathlib import Path

def one(pattern):
    hits = sorted(glob.glob("/kaggle/input/**/" + pattern, recursive=True))
    assert hits, f"input not found: {{pattern}} - attach the bundle dataset and the output of 'DentaMind external data training'"
    return Path(hits[0])

BUNDLE = one("kaggle/dentamind_kaggle.py").parent.parent
want = json.loads((BUNDLE / "BUNDLE_MANIFEST.json").read_text())["files"]
for f in ("kaggle/dentamind_kaggle.py", "scripts/dataset/dsutil.py", "scripts/dataset/download_external.py", "scripts/dataset/remote_zip_list.py",
          "data/splits/combined_validation.csv", "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json"):
    assert hashlib.sha256((BUNDLE / f).read_bytes()).hexdigest() == want[f], f"bundle file changed: {{f}}"
print("bundle:", BUNDLE, "- files used verified against BUNDLE_MANIFEST.json")

RUNS = one("dentamind_artifacts/runs/BASE_s42/best.pth").parent.parent
ART = RUNS.parent
print("previous run artifacts:", ART)

CODE = Path("/kaggle/working/code")
CODE.mkdir(parents=True, exist_ok=True)
SRC = {json.dumps(SRC)}
assert hashlib.sha256(SRC.encode("utf-8")).hexdigest() == "{SRC_SHA}", "embedded script differs from kaggle/ensemble_eval.py"
(CODE / "ensemble_eval.py").write_text(SRC, encoding="utf-8")
for p in (CODE, BUNDLE / "kaggle", BUNDLE / "scripts/dataset"):
    sys.path.insert(0, str(p))
import dentamind_kaggle as DK
import download_external as DX
import ensemble_eval as EV
print("ensemble_eval.py sha256 {SRC_SHA}")"""),
         ("code", """# ---- 2. DENTEX validation images (official archive, verified per image by SHA-256) -----------------------------------
DATA_ROOT = Path("/tmp/dentamind_data")
rows = DK.load_split(BUNDLE / "data/splits", "validation")
if DK.verify_images(rows, DATA_ROOT)[1]:
    t = time.time()
    DX.fetch_dentex_disease_subset(DATA_ROOT)
    print(f"fetched DENTEX disease subset in {time.time() - t:.0f}s")
n_ok, problems = DK.verify_images(rows, DATA_ROOT)
print(f"validation radiographs verified: {n_ok}, problems: {problems}")
assert not problems"""),
         ("code", """# ---- 3. run the registered evaluation (reproduction gate first, then ensemble vs members) ------------------------------
cfg = {"ck_paths": {s: RUNS / f"BASE_s{s}" / "best.pth" for s in EV.MEMBERS},
       "class_meta": RUNS / "BASE_s43" / "best.json",
       "run_records": {s: RUNS / f"BASE_s{s}" / "result.json" for s in EV.MEMBERS},
       "kaggle_eval": ART / "validation_eval.json",
       "data_root": DATA_ROOT, "split_dir": BUNDLE / "data/splits",
       "det_cache": BUNDLE / "docs/audit_evidence/ml_improvement/crop_robustness/val_detector_boxes.json",
       "out_dir": Path("/kaggle/working/ensemble"), "environment": "kaggle"}
try:
    EV.main(cfg)
except SystemExit as e:
    print("STOPPED:", e)
out = Path("/kaggle/working/ensemble/ensemble_evaluation_kaggle.json")
print(out, out.stat().st_size if out.is_file() else "missing")""")]


def main():
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}, "kaggle": {"accelerator": "gpu", "isInternetEnabled": True}},
          "cells": []}
    for i, (kind, src) in enumerate(CELLS):
        cell = {"cell_type": kind, "id": f"cell-{i:02d}", "metadata": {}, "source": src.splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        nb["cells"].append(cell)
    out = HERE / "denta_mind_ensemble_eval.ipynb"
    out.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(CELLS)} cells), embedded ensemble_eval.py sha256 {SRC_SHA}")


if __name__ == "__main__":
    main()
