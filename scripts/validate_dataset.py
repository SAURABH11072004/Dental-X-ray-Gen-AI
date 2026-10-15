#!/usr/bin/env python
"""Detect and validate the dataset in DATA_ROOT. Exit code 2 when the main dataset is missing, 1 on validation errors."""
import _bootstrap  # noqa: F401
import argparse
import json
import sys

from dentexmodel.config import get_settings
from dentexmodel.data.dataset import DatasetService


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    svc = DatasetService(s)
    res = svc.process(force=True, deep_validation=not a.quick)
    if a.json:
        print(json.dumps(res, indent=1))
    else:
        print(f"State: {res['state']}  (data root: {s.data_root})")
        for m in res["messages"]:
            print(" -", m)
        for key in ("main", "test_data"):
            if key in res:
                r = res[key]
                print(f" {key}: {r['n_images']} images, validation_ok={r['validation_ok']}, issues={r['issue_counts']}, splits={r['split_counts']}")
    if not res["main_available"]:
        return 2
    return 0 if res["main"]["validation_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
