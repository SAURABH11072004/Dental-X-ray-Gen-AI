"""PRE-FLIGHT ONLY: stand-in for dentamind_kaggle.train_run used by kaggle/dentamind_cv5_preflight.ipynb.

It trains nothing. Each call saves a *randomly initialised* (untrained) ResNet-50 state dict as best.pth - so the candidate notebook's
real held-out prediction code can load it - and writes a result.json / sidecar with the fields DK.train_run writes. The behaviour of
each run comes from the JSON plan named by $DENTAMIND_PREFLIGHT_PLAN ({run: mode}); it scripts the section-9 cases:

  ok                     completed run
  infra_once             first attempt: CUDA out-of-memory (infrastructure, retried), then ok
  killed                 every attempt killed by SIGKILL (infrastructure, exhausted after 3 attempts)
  compute                ValueError (computation: final, not retried)
  ambiguous_cuda         "CUDA error: invalid argument" (ambiguous: final, not retried)
  inf_loss               completes with an infinite training loss (divergence)
  collapse               completes with every inner-validation prediction in one class (divergence)
  kill_after_checkpoint  saves best.pth and result.json, then is killed before the worker writes the manifest

Run with cv5_accept.run_isolated; cv5_accept records the trainer name, and such runs are never eligible for final-model selection.
"""
import dataclasses
import hashlib
import json
import os
import signal
from pathlib import Path


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _kill():
    if hasattr(signal, "SIGKILL"):
        os.kill(os.getpid(), signal.SIGKILL)
    os._exit(137)                                  # Windows: same return-code convention


def train(cfg, seed, train, val, out_dir, log=print):
    import torch
    import torchvision as tv
    import dentamind_kaggle as DK
    run = f"{cfg.name}_s{seed}"
    plan = json.loads(Path(os.environ["DENTAMIND_PREFLIGHT_PLAN"]).read_text(encoding="utf-8"))
    mode = plan.get(run, "ok")
    out = Path(out_dir) / run
    out.mkdir(parents=True, exist_ok=True)
    calls = out / "preflight_calls.txt"
    n = int(calls.read_text()) + 1 if calls.is_file() else 1
    calls.write_text(str(n))
    print(f"  [{run}] PREFLIGHT fake trainer, mode {mode}, call {n} (no training)", flush=True)
    if mode == "infra_once" and n == 1:
        raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB (PREFLIGHT simulated)")
    if mode == "killed":
        _kill()
    if mode == "compute":
        raise ValueError("PREFLIGHT simulated computation error: shape mismatch in loss")
    if mode == "ambiguous_cuda":
        raise RuntimeError("CUDA error: invalid argument (PREFLIGHT simulated)")
    torch.manual_seed(1000 * seed + int(cfg.name.rsplit("_f", 1)[1]))
    model = DK.new_model(torch, tv, pretrained=False)               # random initialisation, never trained
    ck = out / "best.pth"
    torch.save(model.state_dict(), ck)
    sha = _sha(ck)
    hist = [{"epoch": e, "train_loss": (float("inf") if mode == "inf_loss" and e == 2 else 1.0 / e)} for e in (1, 2, 3)]
    y = [int(t) for t in val["y"].tolist()]
    pred = [0 if mode == "collapse" else (t if i % 3 else (t + 1) % len(DK.CLASSES)) for i, t in enumerate(y)]   # scripted, not a model
    res = {"experiment": cfg.name, "seed": seed, "config": dataclasses.asdict(cfg), "best_epoch": 2,
           "val_gt": DK.report(y, pred), "history": hist, "checkpoint": str(ck),
           "checkpoint_sha256": sha, "preflight": "random initialisation, not trained; metrics are not results",
           "split_note": "PREFLIGHT synthetic arrays only"}
    ck.with_suffix(".json").write_text(json.dumps({"version": f"preflight_{run}", "checkpoint_sha256_full": sha, "candidate": True,
                                                    "promoted": False, "trained_by": "kaggle/cv5_preflight_trainer.py (NOT TRAINED)"}))
    (out / "result.json").write_text(json.dumps(res))
    if mode == "kill_after_checkpoint":
        _kill()
    return res
