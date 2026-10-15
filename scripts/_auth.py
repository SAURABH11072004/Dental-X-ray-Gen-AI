"""Shared by the audit scripts: the API token (env DENTAMIND_API_TOKEN or runtime/api_token.txt) as request headers."""
import os
from pathlib import Path


def token() -> str:
    t = os.environ.get("DENTAMIND_API_TOKEN", "").strip()
    if t:
        return t
    p = Path(__file__).resolve().parents[1] / "runtime" / "api_token.txt"
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def auth_headers() -> dict:
    t = token()
    return {"Authorization": f"Bearer {t}"} if t else {}


def install() -> None:
    """Make every urllib request of this process carry the token (the scripts only talk to the local API)."""
    import urllib.request
    h = auth_headers()
    if h:
        op = urllib.request.build_opener()
        op.addheaders = list(h.items())
        urllib.request.install_opener(op)
