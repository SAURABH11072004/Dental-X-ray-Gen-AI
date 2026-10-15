#!/usr/bin/env python
"""Active learning vs the random baseline, measured on the real DENTEX finding-classification task.

Protocol (every number is measured; nothing is simulated except that "annotation" means revealing labels that the
dataset already contains):

* Pool   = radiographs of the ``train`` split of the disease sub-set. Their labels are hidden from the learner until selected.
* Eval   = the fixed ``val`` split crops (identical for every strategy, seed and round). The ``test`` split is never touched.
* Round 0 = ``--initial`` radiographs chosen at random with the run's seed (identical for all strategies of that seed).
* Round r = train a fresh classifier on the labeled radiographs, score the validation set, then select ``--step`` more
  radiographs from the unlabeled remainder with the strategy: ``random`` (seeded), ``entropy`` (mean normalised predictive
  entropy over the radiograph's tooth crops under the current model) or ``combined`` (0.5 x that entropy + 0.5 x flip-TTA
  disagreement: Jensen-Shannon divergence between the prediction on a crop and on its horizontal flip, normalised by log 2 -
  the same two image-level signals, equally weighted, that the app's combined score uses when no segmenter is involved).
* Budget  = number of labeled radiographs; all strategies see the same budgets, data and seeds.

Ensemble disagreement needs several independently trained models and mask instability a segmenter; neither is part of this run.

    python scripts/run_al_experiment.py --seeds 0 1 2 --initial 60 --step 60 --rounds 4
"""
import _bootstrap  # noqa: F401
import argparse
import json
import sys
import time
from datetime import datetime, timezone

import numpy as np

from dentexmodel.config import get_settings
from dentexmodel.data.coco import annotation_finding
from dentexmodel.data.dataset import DatasetService
from dentexmodel.data.splits import load_split_file
from dentexmodel.evaluation.metrics import classification_report
from dentexmodel.inference.system import gpu_info
from dentexmodel.storage import Database, jdump, new_id, now
from dentexmodel.training import trainers as T
from dentexmodel.uncertainty.measures import entropy as entropy_fn
from dentexmodel.utils.logging_utils import setup_logging


def load_units(settings, size: int):
    """{split: {image_id: (crops uint8 [n,s,s,3], labels list[str])}} for the disease sub-set."""
    from PIL import Image
    svc = DatasetService(settings)
    assign = load_split_file(settings.splits_dir / "dentex_splits.json").get("assignments", {})
    rows = [r for r in svc.manifest("main") if r.annotation_status == "annotated" and not r.is_test_data
            and r.annotation_level == "quadrant_enumeration_disease" and assign.get(r.image_id) in ("train", "val")]
    items = T._annotations_for(settings, svc, rows)
    out = {"train": {}, "val": {}}
    for row, anns, cats in items:
        img = np.asarray(Image.open(settings.data_root / row.file_path).convert("RGB"))
        X, y = [], []
        for a in anns:
            lab = annotation_finding(a, cats) if "category_id_3" in a else None
            if lab is None or not a.get("bbox"):
                continue
            x, yy, w, h = a["bbox"]
            c = T.crop_region(img, (x, yy, x + w, yy + h), size)
            if c is not None:
                X.append(c)
                y.append(lab)
        if X:
            out[assign[row.image_id]][row.image_id] = (np.stack(X), y)
    return out


def fit(torch, tv, device, units, ids, classes, epochs, lr, seed, arch):
    idx = {c: i for i, c in enumerate(classes)}
    X = torch.from_numpy(np.concatenate([units[i][0] for i in ids]))
    y = torch.tensor([idx[c] for i in ids for c in units[i][1]])
    counts = np.bincount(y.numpy(), minlength=len(classes)).astype(float)
    w = torch.tensor(np.where(counts > 0, counts.sum() / (len(classes) * np.maximum(counts, 1)), 0.0), dtype=torch.float32, device=device)
    torch.manual_seed(seed)
    wt = tv.models.ResNet18_Weights.IMAGENET1K_V1
    model = getattr(tv.models, arch)(weights=wt)
    model.fc = torch.nn.Linear(model.fc.in_features, len(classes))
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    g = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(X), generator=g)
        for i in range(0, len(perm), 32):
            b = perm[i:i + 32]
            xb = X[b]
            flip = torch.rand(len(b), generator=g) < 0.5
            xb = torch.where(flip.view(-1, 1, 1, 1), xb.flip(2), xb)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                loss = torch.nn.functional.cross_entropy(model(T._norm(xb, device, torch)), y[b].to(device), weight=w)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
        sched.step()
    return model.eval()


def predict_probs(torch, model, device, X):
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 128):
            out.append(torch.softmax(model(T._norm(torch.from_numpy(X[i:i + 128]), device, torch)), 1).cpu().numpy())
    return np.concatenate(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--initial", type=int, default=60)
    ap.add_argument("--step", type=int, default=60)
    ap.add_argument("--rounds", type=int, default=4, help="number of selection rounds after the initial one")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--image-size", type=int, default=160)
    ap.add_argument("--arch", default="resnet18")
    ap.add_argument("--strategies", nargs="+", default=["random", "entropy", "combined"], choices=["random", "entropy", "combined"])
    ap.add_argument("--out-dir", default=None, help="where to write active_learning_experiment.json/.md (default Data/reports; use another folder to reproduce without overwriting)")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    ap.add_argument("--no-db", action="store_true", help="do not record the runs in the experiments table")
    a = ap.parse_args()
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    torch, tv = T._require_torch()
    device = torch.device("cuda" if (a.device == "cuda" or (a.device == "auto" and torch.cuda.is_available())) else "cpu")
    units = load_units(s, a.image_size)
    train_ids = sorted(units["train"])
    classes = sorted({c for i in train_ids for c in units["train"][i][1]})
    Xv = np.concatenate([units["val"][i][0] for i in sorted(units["val"])])
    yv = [classes.index(c) for i in sorted(units["val"]) for c in units["val"][i][1] if c in classes]
    print(f"pool={len(train_ids)} radiographs, val={len(units['val'])} radiographs / {len(yv)} crops, classes={classes}, device={device}", flush=True)
    if a.initial + a.rounds * a.step > len(train_ids):
        print("Budget exceeds the pool; lower --initial/--step/--rounds.")
        return 2
    db = None if a.no_db else Database(s.db_path)
    import hashlib
    ds_version = T.dataset_version(s)
    results = []
    t_all = time.time()
    for seed in a.seeds:
        rng0 = np.random.default_rng(seed)
        init = [train_ids[i] for i in rng0.permutation(len(train_ids))[:a.initial]]
        for strat in a.strategies:
            labeled = list(init)
            rng = np.random.default_rng(seed + 1000)
            for rnd in range(a.rounds + 1):
                t0 = time.time()
                model = fit(torch, tv, device, units["train"], labeled, classes, a.epochs, a.lr, seed, a.arch)
                rep = classification_report(yv, predict_probs(torch, model, device, Xv).argmax(1).tolist(), len(classes), classes)
                rec = {"seed": seed, "strategy": strat, "round": rnd, "budget": len(labeled), "n_crops": int(sum(len(units["train"][i][1]) for i in labeled)),
                       "macro_f1": rep["macro_f1"], "accuracy": rep["accuracy"], "seconds": round(time.time() - t0, 1),
                       "labeled_sha": hashlib.sha256(",".join(sorted(labeled)).encode()).hexdigest()[:16]}   # which radiographs were labeled at this round
                results.append(rec)
                if db is not None:
                  db.insert("experiments", {"id": new_id("exp"), "strategy": strat, "dataset_version": jdump(ds_version), "model_version": f"al_{a.arch}_seed{seed}",
                                          "budget": len(labeled), "round": rnd, "seed": seed, "duration_s": rec["seconds"],
                                          "metrics_json": jdump({"classification": {"macro_f1": rep["macro_f1"], "accuracy": rep["accuracy"]}}),
                                          "config_json": jdump({**vars(a), "seed": seed, "pool": len(train_ids), "eval": "val split"}),
                                          "gpu": gpu_info().get("gpu_name"), "checkpoint": None, "status": "completed", "is_test_data": 0, "created": now()})
                print(f"seed={seed} {strat:7s} round={rnd} budget={rec['budget']:3d} macro_f1={rec['macro_f1']:.4f} acc={rec['accuracy']:.4f} ({rec['seconds']}s)", flush=True)
                if rnd == a.rounds:
                    break
                remaining = [i for i in train_ids if i not in set(labeled)]
                if strat == "random":
                    pick = [remaining[i] for i in rng.permutation(len(remaining))[:a.step]]
                else:
                    sc = []
                    for i in remaining:
                        Xi = units["train"][i][0]
                        p = predict_probs(torch, model, device, Xi)
                        e = float(np.mean(entropy_fn(p)))
                        if strat == "combined":
                            q = predict_probs(torch, model, device, np.ascontiguousarray(Xi[:, :, ::-1]))
                            m_ = (p + q) / 2
                            h = lambda a: -(a * np.log(a + 1e-12)).sum(-1)
                            js = float(np.mean(np.maximum(h(m_) - (h(p) + h(q)) / 2, 0) / np.log(2)))
                            e = 0.5 * e + 0.5 * js
                        sc.append(e)
                    pick = [remaining[j] for j in np.argsort(-np.asarray(sc), kind="stable")[:a.step]]
                assert not set(pick) & set(labeled)
                rec["selected_next"] = list(pick)      # selection manifest: the radiographs this strategy chose after this round
                labeled += pick
    summary = {}
    for strat in a.strategies:
        for b in sorted({r["budget"] for r in results}):
            v = [r["macro_f1"] for r in results if r["strategy"] == strat and r["budget"] == b]
            summary.setdefault(strat, {})[b] = {"mean": float(np.mean(v)), "std": float(np.std(v)), "n_seeds": len(v)}
    out = {"generated": datetime.now(timezone.utc).isoformat(), "protocol": __doc__, "config": vars(a), "dataset_version": ds_version,
           "pool_radiographs": len(train_ids), "val_crops": len(yv), "classes": classes, "device": str(device),
           "total_seconds": round(time.time() - t_all, 1), "runs": results, "macro_f1_by_budget": summary}
    from pathlib import Path
    rep_dir = Path(a.out_dir) if a.out_dir else s.data_root / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)
    (rep_dir / "active_learning_experiment.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    lines = ["# Active learning vs random baseline (finding classification)", "", f"Generated {out['generated']}. Seeds: {a.seeds}. Pool: {len(train_ids)} radiographs; "
             f"evaluation: validation split ({len(yv)} crops). Macro-F1, mean ± std over seeds.", "", "| Budget (radiographs) | " + " | ".join(a.strategies) + " |",
             "|---:|" + "---:|" * len(a.strategies)]
    for b in sorted({r["budget"] for r in results}):
        lines.append(f"| {b} | " + " | ".join(f"{summary[st][b]['mean']:.4f} ± {summary[st][b]['std']:.4f}" for st in a.strategies) + " |")
    (rep_dir / "active_learning_experiment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
