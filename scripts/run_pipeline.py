#!/usr/bin/env python
"""Run the full data pipeline against whatever is in DATA_ROOT (main dataset, test data, or nothing)."""
import _bootstrap  # noqa: F401
import argparse
import json
import sys

from dentexmodel.config import get_settings
from dentexmodel.pipeline import Pipeline
from dentexmodel.utils.logging_utils import setup_logging


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-images", type=int, default=None, help="limit images for quick runs")
    ap.add_argument("--quick", action="store_true", help="skip deep (full-decode) image validation")
    ap.add_argument("--force", action="store_true", help="reprocess even if the dataset fingerprint is unchanged")
    a = ap.parse_args()
    s = get_settings()
    setup_logging(s.logs_dir, s.log_level)
    rep = Pipeline(s).run(max_images=a.max_images, deep_validation=not a.quick, force=a.force)
    print(f"\nMode: {rep['mode']}   data root: {s.data_root}")
    if rep.get("notice"):
        print("NOTICE:", rep["notice"])
    for st in rep["steps"]:
        print(f"  [{st['status']:<7}] {st['step']:<24} {st['seconds']:>6.1f}s  {st['message'][:110]}")
    print("Report written to", s.results_dir / "pipeline_report.json")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
