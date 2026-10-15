#!/usr/bin/env python
"""Poll DATA_ROOT and (re)process the dataset whenever the real data appears or changes."""
import _bootstrap  # noqa: F401
import time

from dentexmodel.config import get_settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.utils.logging_utils import setup_logging

s = get_settings()
setup_logging(s.logs_dir, s.log_level)
svc = DatasetService(s)
print(f"Watching {s.data_root} every {s.auto_process_interval_s}s (Ctrl+C to stop)")
last = None
while True:
    st = svc.status()
    if st.fingerprint != last:
        last = st.fingerprint
        res = svc.process()
        print(time.strftime("%H:%M:%S"), res["state"], res["messages"][:1])
    time.sleep(s.auto_process_interval_s)
