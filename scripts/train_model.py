#!/usr/bin/env python
"""Start a training job (blocking in CLI). Refuses to run - with an explanation - when prerequisites are unmet."""
import _bootstrap  # noqa: F401
import argparse
import sys
import time

from dentexmodel.config import get_settings
from dentexmodel.errors import DentaMindError
from dentexmodel.storage import Database
from dentexmodel.training import JobManager, TrainConfig
from dentexmodel.utils.logging_utils import setup_logging


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="classification", choices=["classification", "detection", "segmentation", "numbering"])
    ap.add_argument("--architecture", default=None)
    ap.add_argument("--name", default="experiment")
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-pretrained", action="store_true", help="train from random initialisation")
    ap.add_argument("--label-mode", default="tooth", choices=["tooth", "fdi"], help="detection/segmentation classes")
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--max-train-images", type=int, default=None, help="SMOKE TEST ONLY: cap training images")
    ap.add_argument("--max-val-images", type=int, default=None, help="SMOKE TEST ONLY: cap validation images")
    a = ap.parse_args()
    default_arch = {"classification": "resnet50", "detection": "fasterrcnn_resnet50_fpn", "segmentation": "maskrcnn_resnet50_fpn", "numbering": "fasterrcnn_resnet50_fpn"}[a.task]
    cfg = TrainConfig(task=a.task, architecture=a.architecture or default_arch, experiment_name=a.name, epochs=a.epochs,
                      batch_size=a.batch_size, learning_rate=a.lr, image_size=a.image_size, device=a.device, seed=a.seed,
                      pretrained=not a.no_pretrained, label_mode=a.label_mode, num_workers=a.num_workers,
                      max_train_images=a.max_train_images, max_val_images=a.max_val_images)
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    s.ensure_dirs()
    jm = JobManager(s, Database(s.db_path))
    try:
        job = jm.start(cfg)
    except DentaMindError as exc:
        print("Cannot start training:", exc.message)
        for u in (exc.details or {}).get("unmet", []):
            print(f" - {u['message']}  ->  {u['fix']}")
        return 2
    while True:
        job = jm.get(job["id"])
        print(job["status"], job["progress"])
        if job["status"] not in ("queued", "running"):
            break
        time.sleep(5)
    print("Final:", job["status"], job.get("error") or job.get("checkpoint"))
    return 0 if job["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())
