#!/usr/bin/env python
"""Inspect and partially download a remote ZIP archive with HTTP range requests (no full download).

    python scripts/dataset/remote_zip_list.py URL --json listing.json
    python scripts/dataset/remote_zip_list.py URL --extract PREFIX --out DIR      # e.g. one sub-folder of a 10.9 GB archive

Used to verify what an archive contains (for example whether labels are included) before deciding to download it, and on Kaggle
to fetch only the DENTEX disease subset from the full training archive. Every extracted member is CRC-32 verified. Supports ZIP64.
Standard library only, so it runs unchanged locally and on Kaggle.
"""
import argparse
import json
import os
import struct
import time
import urllib.request
import zlib

UA = {"User-Agent": "dentamind-dataset-audit"}


def _get(url, start, end, retries=5):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}", **UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                return data, r.headers.get("Content-Range")
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def _central_directory(url):
    _, cr = _get(url, 0, 0)
    size = int(cr.split("/")[-1])
    n = min(size, 1 << 17)
    tail, _ = _get(url, size - n, size - 1)
    i = tail.rfind(b"PK\x05\x06")
    if i < 0:
        raise ValueError("end-of-central-directory record not found")
    entries, cd_size, cd_off = struct.unpack("<10xHII", tail[i:i + 20])
    j = tail.rfind(b"PK\x06\x06")                                   # ZIP64 end-of-central-directory record (56 bytes)
    if j >= 0:
        _, entries, cd_size, cd_off = struct.unpack("<24xQQQQ", tail[j:j + 56])
    cd, _ = _get(url, cd_off, cd_off + cd_size - 1)
    return size, entries, cd


def _parse_entries(cd):
    out, p = [], 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        method, = struct.unpack("<H", cd[p + 10:p + 12])
        crc, csize, usize, nl, xl, cl = struct.unpack("<16xIIIHHH", cd[p:p + 34])
        off, = struct.unpack("<I", cd[p + 42:p + 46])
        name = cd[p + 46:p + 46 + nl].decode("utf-8", "replace")
        extra = cd[p + 46 + nl:p + 46 + nl + xl]
        q = 0
        while q + 4 <= len(extra):                                    # ZIP64 extended information extra field
            hid, hl = struct.unpack("<HH", extra[q:q + 4])
            if hid == 1:
                vals = list(struct.unpack("<" + "Q" * (hl // 8), extra[q + 4:q + 4 + (hl // 8) * 8]))
                if usize == 0xFFFFFFFF:
                    usize = vals.pop(0)
                if csize == 0xFFFFFFFF:
                    csize = vals.pop(0)
                if off == 0xFFFFFFFF:
                    off = vals.pop(0)
            q += 4 + hl
        out.append({"name": name, "size": usize, "compressed": csize, "crc32": f"{crc:08x}", "method": method, "offset": off})
        p += 46 + nl + xl + cl
    return out


def list_remote_zip(url):
    size, entries, cd = _central_directory(url)
    return {"url": url, "archive_bytes": size, "entries_declared": entries, "members": _parse_entries(cd)}


def fetch_member(url, member):
    """Bytes of one member (a dict from ``list_remote_zip``), CRC-32 verified. Stored and deflate members only."""
    hdr, _ = _get(url, member["offset"], member["offset"] + 29)
    lnl, lxl = struct.unpack("<HH", hdr[26:30])
    start = member["offset"] + 30 + lnl + lxl
    if member["compressed"] == 0:
        data = b""
    else:
        raw, _ = _get(url, start, start + member["compressed"] - 1)
        if member["method"] == 0:
            data = raw
        elif member["method"] == 8:
            data = zlib.decompress(raw, -15)
        else:
            raise NotImplementedError(f"compression method {member['method']}")
    if f"{zlib.crc32(data) & 0xFFFFFFFF:08x}" != member["crc32"]:
        raise ValueError(f"CRC mismatch for {member['name']}")
    return data


def extract_prefix(url, prefix, out_dir, listing=None, log_every=50):
    """Download every file member whose name starts with ``prefix`` into ``out_dir`` (paths preserved). Resumable: a file that
    already exists with the expected size and CRC is skipped. Returns the number of files present afterwards."""
    listing = listing or list_remote_zip(url)
    todo = [m for m in listing["members"] if m["name"].startswith(prefix) and not m["name"].endswith("/")
            and "/." not in m["name"]]
    n = 0
    for k, m in enumerate(todo):
        rel = os.path.normpath(m["name"])
        if rel.startswith("..") or os.path.isabs(rel):
            raise ValueError(f"unsafe member path {m['name']}")
        dst = os.path.join(out_dir, rel)
        if os.path.isfile(dst) and os.path.getsize(dst) == m["size"]:
            with open(dst, "rb") as fh:
                if f"{zlib.crc32(fh.read()) & 0xFFFFFFFF:08x}" == m["crc32"]:
                    n += 1
                    continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = fetch_member(url, m)
        with open(dst + ".part", "wb") as fh:
            fh.write(data)
        os.replace(dst + ".part", dst)
        n += 1
        if log_every and (k + 1) % log_every == 0:
            print(f"  {k + 1}/{len(todo)} files", flush=True)
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--json", help="write the member listing here")
    ap.add_argument("--extract", help="member-name prefix to download")
    ap.add_argument("--out", help="output directory for --extract")
    a = ap.parse_args()
    res = list_remote_zip(a.url)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(f"{res['archive_bytes']} bytes, {len(res['members'])} members")
    if a.extract:
        print(f"extracted {extract_prefix(a.url, a.extract, a.out, res)} files")
