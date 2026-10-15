#!/usr/bin/env python
"""Report Python/package/GPU/dataset/checkpoint status."""
import _bootstrap  # noqa: F401
import json

from dentexmodel.config import get_settings
from dentexmodel.data.discovery import discover
from dentexmodel.inference.registry import scan_checkpoints
from dentexmodel.inference.system import environment_report

s = get_settings()
env = environment_report()
print(json.dumps({"python": env["python"], "platform": env["platform"], "packages": env["packages"], "gpu": env["gpu"],
                  "settings": s.public_dict(), "dataset": {k: v for k, v in discover(s).to_dict().items() if k != "sources"},
                  "checkpoints": [m.to_dict() for m in scan_checkpoints(s)]}, indent=1))
