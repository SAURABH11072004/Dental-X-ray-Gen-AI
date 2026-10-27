#!/usr/bin/env python
"""Download, verify and extract registered dataset sources (scripts/dataset/sources.py: DOWNLOADS). Same code locally and on Kaggle.

    python scripts/dataset/download_external.py --source dentex_hf_validation_labels dentex_hf_test [--root DATA_PARENT]
    python scripts/dataset/download_external.py --dentex-disease-subset --data-root /kaggle/working/data

Rules: only URLs from the registry; resumable (HTTP Range on a .part file); size and SHA-256 must equal the registry before a
file is accepted; ZIPs are CRC-tested and extracted with a path-traversal check into their own folder; original files are kept
unchanged; every image is decoded once to prove it is readable. ``--dentex-disease-subset`` fetches only
training_data/quadrant-enumeration-disease/ from the 10.9 GB DENTEX archive (range requests, CRC-32 per member).
Writes a JSON verification record next to each download (<dest>.verify.json).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import remote_zip_list as RZ  # noqa: E402
from dsutil import sha256_file  # noqa: E402
from sources import DOWNLOADS  # noqa: E402


def download(url, dest: Path, expected_bytes=None, expected_sha=None, retries=5):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and (expected_sha is None or sha256_file(dest) == expected_sha):
        return "already present and verified"
    part = dest.with_name(dest.name + ".part")
    for attempt in range(retries):
        have = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": RZ.UA["User-Agent"]}
        if have:
            headers["Range"] = f"bytes={have}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                if have and r.status != 206:      # server ignored the range: restart cleanly
                    have = 0
                with open(part, "ab" if have else "wb") as fh:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        fh.write(b)
            break
        except OSError as exc:
            print(f"  download interrupted ({exc}); resuming", flush=True)
            time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"download failed after {retries} attempts: {url}")
    size = part.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise ValueError(f"{dest.name}: size {size} != expected {expected_bytes}; .part kept for resume")
    sha = sha256_file(part)
    if expected_sha and sha != expected_sha:
        part.unlink()
        raise ValueError(f"{dest.name}: SHA-256 mismatch ({sha}); file discarded")
    os.replace(part, dest)
    return "downloaded and verified"


def safe_extract(zpath: Path, out: Path):
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"{zpath.name}: CRC error in member {bad}")
        for m in z.infolist():
            p = os.path.normpath(m.filename)
            if p.startswith("..") or os.path.isabs(p):
                raise ValueError(f"unsafe member path {m.filename}")
        z.extractall(out)
        return len([m for m in z.infolist() if not m.is_dir()])


def check_images(folder: Path):
    from PIL import Image
    n, bad = 0, []
    for p in sorted(folder.rglob("*.png")):
        try:
            with Image.open(p) as im:
                im.load()
            n += 1
        except Exception as exc:  # noqa: BLE001 - report every unreadable image
            bad.append((str(p), str(exc)))
    return n, bad


def fetch_source(key, root: Path):
    spec = DOWNLOADS[key]
    if not spec.get("dest"):
        raise SystemExit(f"{key}: not downloadable as a whole by design ({spec.get('note')})")
    dest = root / spec["dest"]
    status = download(spec["url"], dest, spec.get("bytes"), spec.get("sha256"))
    rec = {"source": key, "url": spec["url"], "file": str(dest), "bytes": dest.stat().st_size, "sha256": sha256_file(dest),
           "expected_sha256": spec.get("sha256"), "sha256_origin": spec.get("sha256_origin"), "status": status,
           "verified_at": datetime.now(timezone.utc).isoformat()}
    if dest.suffix == ".zip":
        out = root / spec["extract_to"] if spec.get("extract_to") else dest.parent.parent / dest.stem
        rec["extracted_files"] = safe_extract(dest, out)
        rec["images_readable"], rec["images_unreadable"] = check_images(out)
        rec["extracted_to"] = str(out)
    Path(str(dest) + ".verify.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rec.items() if k != "images_unreadable"}), flush=True)
    return rec


def fetch_dentex_disease_subset(data_root: Path):
    """training_data/quadrant-enumeration-disease/** from the HF archive into <data_root>/training_data/... (resumable)."""
    url = DOWNLOADS["dentex_hf_training"]["url"]
    listing = RZ.list_remote_zip(url)
    if listing["archive_bytes"] != DOWNLOADS["dentex_hf_training"]["bytes"]:
        raise ValueError("training archive size differs from the registry - the upstream file changed; stop and re-verify")
    n = RZ.extract_prefix(url, "training_data/quadrant-enumeration-disease/", str(data_root), listing)
    ok, bad = check_images(data_root / "training_data/quadrant-enumeration-disease")
    print(f"disease subset: {n} files, {ok} readable images, {len(bad)} unreadable", flush=True)
    return {"files": n, "images_readable": ok, "images_unreadable": bad}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", nargs="*", default=[], choices=[k for k, v in DOWNLOADS.items() if v.get("dest")])
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[2]), help="parent of the registry 'dest' paths")
    ap.add_argument("--dentex-disease-subset", action="store_true")
    ap.add_argument("--data-root", default=None, help="for --dentex-disease-subset: folder that will contain training_data/")
    a = ap.parse_args()
    for k in a.source:
        fetch_source(k, Path(a.root))
    if a.dentex_disease_subset:
        fetch_dentex_disease_subset(Path(a.data_root or Path(a.root) / "data"))


if __name__ == "__main__":
    main()
