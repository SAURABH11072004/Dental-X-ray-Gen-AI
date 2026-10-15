"""Authentication, loopback restriction, rate limiting, and training-API safety (dry run, conflicts, resume-path confinement). No models are trained."""
import asyncio
import json
import os
import time
import unittest
from unittest import mock

import helpers
from backend.security import LIMITS, RateLimiter, SecurityMiddleware, bucket_for, load_token
from dentexmodel.errors import ConflictError, DentaMindError
from dentexmodel.storage import Database, now
from dentexmodel.training.config import TrainConfig, check_prerequisites
from dentexmodel.training.jobs import JobManager

TOKEN = "unit-test-token-0123456789"


async def _app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
    await send({"type": "http.response.body", "body": b'{"ok": true}'})


def call(mw, method, path, headers=None, client="127.0.0.1"):
    """Drive the ASGI middleware directly; returns (status, headers dict, body bytes)."""
    out = {}

    async def send(msg):
        if msg["type"] == "http.response.start":
            out["status"], out["headers"] = msg["status"], {k.decode(): v.decode() for k, v in msg["headers"]}
        else:
            out["body"] = msg.get("body", b"")

    async def receive():
        return {"type": "http.request", "body": b""}
    scope = {"type": "http", "method": method, "path": path, "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()], "client": (client, 5000)}
    asyncio.run(mw(scope, receive, send))
    return out["status"], out["headers"], out["body"]


def make(**kw):
    return SecurityMiddleware(_app, token=kw.pop("token", TOKEN), limiter=kw.pop("limiter", RateLimiter()), **kw)


class AuthTests(unittest.TestCase):
    def test_missing_wrong_and_valid_tokens(self):
        mw = make()
        self.assertEqual(call(mw, "GET", "/api/models")[0], 401)
        self.assertEqual(call(mw, "GET", "/api/models", {"Authorization": "Bearer nope"})[0], 401)
        self.assertEqual(call(mw, "GET", "/api/models", {"Authorization": "Basic " + TOKEN})[0], 401)
        self.assertEqual(call(mw, "GET", "/api/models", {"Authorization": f"Bearer {TOKEN}"})[0], 200)
        self.assertEqual(call(mw, "GET", "/api/models", {"X-API-Key": TOKEN})[0], 200)

    def test_denied_response_has_envelope_and_never_contains_the_token(self):
        st, h, body = call(make(), "POST", "/api/training/start", {"Authorization": "Bearer wrong"})
        self.assertEqual(st, 401)
        j = json.loads(body)
        self.assertEqual(j["error"]["code"], "unauthorized")
        self.assertNotIn(TOKEN, body.decode())
        self.assertEqual(h.get("www-authenticate"), "Bearer")

    def test_health_and_non_api_paths_and_preflight_are_open(self):
        mw = make()
        self.assertEqual(call(mw, "GET", "/api/health")[0], 200)
        self.assertEqual(call(mw, "OPTIONS", "/api/images/upload")[0], 200)
        self.assertEqual(call(mw, "GET", "/assets/app.js")[0], 200)
        self.assertEqual(call(mw, "POST", "/api/health")[0], 401)        # only GET health is exempt

    def test_protected_groups_need_the_token(self):
        mw = make()
        for method, path in (("POST", "/api/images/upload"), ("POST", "/api/training/start"), ("POST", "/api/training/stop/x"), ("POST", "/api/models/select"),
                             ("POST", "/api/models/promote"), ("POST", "/api/models/m/evaluate"), ("POST", "/api/reports/generate"), ("POST", "/api/reports/r/review"),
                             ("POST", "/api/reviews"), ("POST", "/api/dataset/process"), ("GET", "/api/images/x/file"), ("GET", "/docs"), ("GET", "/openapi.json")):
            self.assertEqual(call(mw, method, path)[0], 401, (method, path))

    def test_non_loopback_clients_are_refused_even_with_a_valid_token(self):
        st, _, body = call(make(), "GET", "/api/models", {"Authorization": f"Bearer {TOKEN}"}, client="192.168.1.20")
        self.assertEqual(st, 403)
        self.assertEqual(call(make(allow_remote=True), "GET", "/api/models", {"Authorization": f"Bearer {TOKEN}"}, client="192.168.1.20")[0], 200)

    def test_auth_switched_off_still_keeps_loopback_only(self):
        mw = make(token=None)
        self.assertEqual(call(mw, "GET", "/api/models")[0], 200)
        self.assertEqual(call(mw, "GET", "/api/models", client="10.0.0.5")[0], 403)

    def test_repeated_failed_authentication_is_throttled(self):
        mw = make()
        codes = [call(mw, "GET", "/api/models", {"Authorization": "Bearer bad"})[0] for _ in range(LIMITS["auth_fail"] + 3)]
        self.assertEqual(codes[:LIMITS["auth_fail"]], [401] * LIMITS["auth_fail"])
        self.assertEqual(codes[-1], 429)
        # a correct token is still accepted: the throttle counts failures only
        self.assertEqual(call(mw, "GET", "/api/models", {"Authorization": f"Bearer {TOKEN}"})[0], 200)


class TokenSourceTests(helpers.TmpCase):
    def test_file_token_is_generated_once_and_reused_and_env_wins(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DENTAMIND_API_TOKEN", None)
            os.environ.pop("DENTAMIND_AUTH", None)
            t1 = load_token(self.tmp)
            self.assertGreaterEqual(len(t1), 32)
            self.assertEqual(t1, load_token(self.tmp))
            self.assertEqual((self.tmp / "runtime" / "api_token.txt").read_text(encoding="utf-8"), t1)
            os.environ["DENTAMIND_API_TOKEN"] = "from-env"
            self.assertEqual(load_token(self.tmp), "from-env")
            os.environ["DENTAMIND_AUTH"] = "off"
            self.assertIsNone(load_token(self.tmp))


class RateLimitTests(unittest.TestCase):
    def test_window_blocks_then_recovers(self):
        now_ = [0.0]
        rl = RateLimiter({"control": 3, "read": 5, "auth_fail": 3, "upload": 1, "heavy": 1, "mutate": 1}, clock=lambda: now_[0])
        self.assertEqual([rl.check("c", "control") for _ in range(3)], [0, 0, 0])
        wait = rl.check("c", "control")
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 61)
        self.assertEqual(rl.check("other-client", "control"), 0)       # per client
        self.assertEqual(rl.check("c", "read"), 0)                      # per bucket
        now_[0] = 61.0
        self.assertEqual(rl.check("c", "control"), 0)                   # window slid

    def test_buckets(self):
        self.assertEqual(bucket_for("GET", "/api/models"), "read")
        self.assertEqual(bucket_for("POST", "/api/images/upload"), "upload")
        self.assertEqual(bucket_for("POST", "/api/analyze/full"), "heavy")
        self.assertEqual(bucket_for("POST", "/api/training/start"), "control")
        self.assertEqual(bucket_for("POST", "/api/models/x.pth/evaluate"), "control")
        self.assertEqual(bucket_for("POST", "/api/reports/generate"), "mutate")

    def test_middleware_returns_429_with_retry_after(self):
        mw = make(limiter=RateLimiter({**LIMITS, "control": 2}))
        h = {"Authorization": f"Bearer {TOKEN}"}
        self.assertEqual([call(mw, "POST", "/api/training/stop/x", h)[0] for _ in range(2)], [200, 200])
        st, hd, _ = call(mw, "POST", "/api/training/stop/x", h)
        self.assertEqual(st, 429)
        self.assertIn("retry-after", hd)
        self.assertEqual(call(mw, "GET", "/api/models", h)[0], 200)      # other buckets unaffected

    def test_rate_limit_can_be_switched_off_for_tests(self):
        mw = make(limiter=RateLimiter({**LIMITS, "control": 1}), rate_limit=False)
        h = {"Authorization": f"Bearer {TOKEN}"}
        self.assertEqual([call(mw, "POST", "/api/training/stop/x", h)[0] for _ in range(4)], [200] * 4)


class TrainingSafetyTests(helpers.TmpCase):
    def _mgr(self):
        return JobManager(self.s, Database(self.s.db_path), trainer=lambda c, x: {})

    READY = {"ready": True, "unmet": []}

    def test_dry_run_validates_but_creates_nothing(self):
        m = self._mgr()
        with mock.patch("dentexmodel.training.jobs.check_prerequisites", return_value=self.READY):
            r = m.start(TrainConfig(experiment_name="dry_check", epochs=1), dry_run=True)
        self.assertTrue(r["dry_run"])
        self.assertEqual(r["would_write_checkpoint"], "dry_check_classification_v1.pth")
        self.assertEqual(m.db.list("jobs"), [])
        self.assertFalse(self.s.checkpoint_dir.exists() and any(self.s.checkpoint_dir.iterdir()))

    def test_dry_run_reports_the_next_free_version_without_overwriting(self):
        self.s.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (self.s.checkpoint_dir / "keep_classification_v1.pth").write_bytes(b"x")
        with mock.patch("dentexmodel.training.jobs.check_prerequisites", return_value=self.READY):
            r = self._mgr().start(TrainConfig(experiment_name="keep"), dry_run=True)
        self.assertEqual(r["would_write_checkpoint"], "keep_classification_v2.pth")
        self.assertEqual((self.s.checkpoint_dir / "keep_classification_v1.pth").read_bytes(), b"x")

    def test_second_start_is_refused_while_a_job_runs_and_dry_run_is_refused_too(self):
        m = self._mgr()
        m.db.insert("jobs", {"id": "job-busy", "kind": "evaluate", "status": "running", "config_json": "{}", "created": now(), "started": now(), "pid": os.getpid()})
        with mock.patch("dentexmodel.training.jobs.check_prerequisites", return_value=self.READY):
            for dry in (False, True):
                with self.assertRaises(ConflictError) as cm:
                    m.start(TrainConfig(), dry_run=dry)
                self.assertEqual(cm.exception.code, "job_already_running")
                self.assertEqual(cm.exception.status_code, 409)
        self.assertEqual(len(m.db.list("jobs")), 1)

    def test_job_of_a_dead_process_does_not_block(self):
        m = self._mgr()
        m.db.insert("jobs", {"id": "job-dead", "kind": "train_x", "status": "running", "config_json": "{}", "created": now(), "pid": 2147483000})
        self.assertEqual(m.running_jobs(), [])

    def test_invalid_configurations_are_rejected_before_anything_else(self):
        for bad in (dict(task="bogus"), dict(architecture="resnet1000"), dict(experiment_name="../evil"), dict(experiment_name="a b"), dict(epochs=0), dict(batch_size=0),
                    dict(learning_rate=0), dict(image_size=8), dict(device="tpu"), dict(label_mode="x")):
            with self.assertRaises(DentaMindError) as cm:
                self._mgr().start(TrainConfig(**bad), dry_run=True)
            self.assertEqual(cm.exception.code, "invalid_configuration", bad)

    def test_resume_checkpoint_cannot_escape_the_checkpoint_folder_or_use_unverified_files(self):
        (self.tmp / "secret.txt").write_text("not a checkpoint")
        self.s.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (self.s.checkpoint_dir / "loose.pth").write_bytes(b"x")             # no sidecar: unverified
        for ref in ("../secret.txt", "..\\secret.txt", "loose.pth", "does_not_exist.pth"):
            pre = check_prerequisites(self.s, TrainConfig(resume_checkpoint=ref))
            codes = {u["code"] for u in pre["unmet"]}
            self.assertTrue(codes & {"checkpoint_missing", "checkpoint_incompatible"}, (ref, codes))

    def test_resume_from_a_verified_checkpoint_of_another_task_is_incompatible(self):
        self.s.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (self.s.checkpoint_dir / "det_v1.pth").write_bytes(b"x")
        (self.s.checkpoint_dir / "det_v1.json").write_text(json.dumps({"task": "detection", "architecture": "fasterrcnn_resnet50_fpn", "version": "det_v1", "dental_specific": True,
                                                                         "class_names": ["tooth"], "num_classes": 2}), encoding="utf-8")
        pre = check_prerequisites(self.s, TrainConfig(task="classification", resume_checkpoint="det_v1.pth"))
        self.assertIn("checkpoint_incompatible", {u["code"] for u in pre["unmet"]})


if __name__ == "__main__":
    unittest.main()
