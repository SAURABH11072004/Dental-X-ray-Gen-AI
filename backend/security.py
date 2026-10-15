"""Request security for the local DentaMind API: token authentication, loopback-only access and rate limiting.

* Token: ``DENTAMIND_API_TOKEN`` (environment) or the auto-generated ``runtime/api_token.txt`` (git-ignored, created on first start).
  Every ``/api`` route except ``GET /api/health`` needs ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``.
  The Vite dev proxy adds the header on the server side, so the token never appears in browser code or the page.
* ``DENTAMIND_AUTH=off`` disables the token check (development only); loopback-only access still applies.
* Clients that are not on the loopback interface are refused unless ``DENTAMIND_ALLOW_REMOTE=1``.
* Rate limits are per client and per bucket (sliding one-minute window); failed authentications are throttled separately.
  ``DENTAMIND_RATE_LIMIT=off`` disables limiting (tests only).
The token is never logged or returned by any endpoint.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

log = logging.getLogger("dentamind.security")

LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
EXEMPT = {("GET", "/api/health")}

# bucket -> (limit per minute)
LIMITS = {"upload": 60, "heavy": 120, "control": 20, "mutate": 300, "read": 1500, "auth_fail": 20}
HEAVY = ("/api/predict", "/api/analyze/full", "/api/segment", "/api/explain", "/api/uncertainty/image", "/api/active-learning/score-pool", "/api/active-learning/select")
CONTROL = ("/api/training/", "/api/models/", "/api/dataset/process", "/api/active-learning/export", "/api/annotations/import", "/api/annotations/approve", "/api/annotations/reject")


def load_token(project_root: Path) -> str | None:
    """Environment variable first, then runtime/api_token.txt (created with a random value if missing). None when auth is switched off."""
    if os.environ.get("DENTAMIND_AUTH", "on").lower() in ("off", "0", "false"):
        return None
    env = os.environ.get("DENTAMIND_API_TOKEN", "").strip()
    if env:
        return env
    p = Path(project_root) / "runtime" / "api_token.txt"
    try:
        if p.is_file():
            t = p.read_text(encoding="utf-8").strip()
            if t:
                return t
        p.parent.mkdir(parents=True, exist_ok=True)
        t = secrets.token_urlsafe(32)
        p.write_text(t, encoding="utf-8")
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass
        log.warning("Generated a new API token in runtime/api_token.txt (never commit it).")
        return t
    except OSError as exc:  # cannot persist: fall back to a per-process token rather than running open
        log.error("Cannot write runtime/api_token.txt (%s); using a per-process token", exc.__class__.__name__)
        return secrets.token_urlsafe(32)


class RateLimiter:
    def __init__(self, limits: dict | None = None, clock=time.monotonic):
        self.limits = dict(limits or LIMITS)
        self.clock = clock
        self._hits: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, client: str, bucket: str, cost: int = 1) -> int:
        """0 if allowed (and counted), otherwise the number of seconds to wait."""
        limit = self.limits[bucket]
        now = self.clock()
        with self._lock:
            q = self._hits[(client, bucket)]
            while q and now - q[0] >= 60:
                q.popleft()
            if len(q) + cost > limit:
                return max(1, int(60 - (now - q[0])) + 1)
            for _ in range(cost):
                q.append(now)
            return 0

    def count(self, client: str, bucket: str) -> int:
        with self._lock:
            return len(self._hits[(client, bucket)])


def bucket_for(method: str, path: str) -> str:
    if method in ("GET", "HEAD"):
        return "read"
    if path == "/api/images/upload":
        return "upload"
    if path.startswith(CONTROL) or path.endswith("/evaluate"):
        return "control"
    if path in HEAVY:
        return "heavy"
    return "mutate"


async def _json(send, status: int, code: str, message: str, hint: str | None = None, extra: list | None = None):
    body = json.dumps({"error": {"code": code, "message": message, "hint": hint, "details": {}}}).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), (b"cache-control", b"no-store")] + (extra or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class SecurityMiddleware:
    def __init__(self, app, token: str | None, limiter: RateLimiter | None = None, allow_remote: bool | None = None, rate_limit: bool | None = None):
        self.app, self.token = app, token
        self.limiter = limiter or RateLimiter()
        self.allow_remote = os.environ.get("DENTAMIND_ALLOW_REMOTE", "") == "1" if allow_remote is None else allow_remote
        self.rate_limit = (os.environ.get("DENTAMIND_RATE_LIMIT", "on").lower() not in ("off", "0", "false")) if rate_limit is None else rate_limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        if method == "OPTIONS" or not (path.startswith("/api") or path in ("/docs", "/redoc", "/openapi.json")):
            return await self.app(scope, receive, send)
        client = (scope.get("client") or ("unknown", 0))[0]
        if not self.allow_remote and client not in LOOPBACK:
            return await _json(send, 403, "forbidden_client", "This API only accepts connections from the local machine.",
                               "Set DENTAMIND_ALLOW_REMOTE=1 only behind a trusted network and keep the API token secret.")
        if (method, path) not in EXEMPT and self.token is not None:
            hdrs = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            supplied = hdrs.get("x-api-key", "")
            auth = hdrs.get("authorization", "")
            if auth.lower().startswith("bearer "):
                supplied = auth[7:].strip()
            if not supplied or not hmac.compare_digest(supplied.encode(), self.token.encode()):
                if self.rate_limit:
                    wait = self.limiter.check(client, "auth_fail")
                    if wait:
                        return await _json(send, 429, "too_many_auth_failures", "Too many failed authentication attempts.", f"Retry in {wait} s.", [(b"retry-after", str(wait).encode())])
                return await _json(send, 401, "unauthorized", "A valid API token is required.", "Send 'Authorization: Bearer <token>' (token in runtime/api_token.txt or DENTAMIND_API_TOKEN).",
                                   [(b"www-authenticate", b"Bearer")])
        if self.rate_limit and (method, path) not in EXEMPT:
            bucket = bucket_for(method, path)
            wait = self.limiter.check(client, bucket)
            if wait:
                return await _json(send, 429, "rate_limited", f"Too many {bucket} requests.", f"Retry in {wait} s.", [(b"retry-after", str(wait).encode())])
        return await self.app(scope, receive, send)
