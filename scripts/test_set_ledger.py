#!/usr/bin/env python
"""Show, initialise or verify the internal test-split ledger (Data/reports/test_set_ledger.json).

    python scripts/test_set_ledger.py            # status (read-only)
    python scripts/test_set_ledger.py --init     # write the ledger with the historical (pre-ledger) test evaluations; never rewrites entries
    python scripts/test_set_ledger.py --verify   # check the hash chain; exit 1 if an entry was edited or removed
"""
import _bootstrap  # noqa: F401
import argparse
import sys

from dentexmodel.config import get_settings
from dentexmodel.evaluation import test_ledger as TL


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    s = get_settings()
    if a.init:
        led = TL.ensure_ledger(s)
        print(f"ledger: {TL.ledger_path(s)} ({len(led['entries'])} entries, initialised {led['initialised']})")
    st = TL.status(s)
    print(st["statement"])
    for e in st["entries"]:
        print(f"  {e.get('seq', '-')}: {e['kind']:<13} {e.get('version')} ({e.get('task')}) at {e.get('evaluated_at')} "
              f"sha256 {str(e.get('checkpoint_sha256'))[:16]} {'historical' if e.get('historical') else 'authorized by ' + str(e.get('authorized_by'))}")
    if a.verify:
        if not st["ledger_initialised"]:
            print("no ledger file yet (run --init)")
            return 1
        print("chain intact" if not st["chain_problems"] else "CHAIN PROBLEMS: " + "; ".join(st["chain_problems"]))
        return 1 if st["chain_problems"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
