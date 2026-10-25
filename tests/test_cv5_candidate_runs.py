"""Tests for the CV5 candidate-run path: kaggle/cv5_accept.py run_isolated / worker / run_status / manifests and the candidate cells of
kaggle/make_cv5_notebook.py (protocol reports/cv5_acceptance_protocol.md, revision 3, section 9 and 10.3).

The real isolated-process path is exercised with a fake trainer (same signature as DK.train_run) written to a temp directory, so no
model is trained, nothing runs on Kaggle and no data set is read. The BASE notebook generator output is checked to be unchanged."""
import dataclasses
import json
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "kaggle", ROOT / "scripts" / "dataset"):
    sys.path.insert(0, str(p))

import cv5_accept as CA  # noqa: E402
import cv5_lib as CV  # noqa: E402
import dentamind_kaggle as DK  # noqa: E402
import make_cv5_notebook as NB  # noqa: E402

FAKE = textwrap.dedent('''
    """Stand-in for dentamind_kaggle.train_run: behaviour from cfg.extra["fake"]."""
    import dataclasses, hashlib, json, os
    from pathlib import Path

    def _sha(p):
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()

    def train(cfg, seed, train, val, out_dir, log=print):
        mode = cfg.extra.get("fake", "ok")
        out = Path(out_dir) / f"{cfg.name}_s{seed}"
        out.mkdir(parents=True, exist_ok=True)
        calls = out / "fake_calls.txt"
        n = int(calls.read_text()) + 1 if calls.is_file() else 1
        calls.write_text(str(n))
        if mode == "infra_once" and n == 1 or mode == "infra_always":
            raise RuntimeError("CUDA error: an illegal memory access was encountered")
        if mode == "oom_always":
            raise MemoryError("host out of memory")
        if mode == "compute":
            raise ValueError("shape mismatch in loss")
        if mode == "device_assert":
            raise RuntimeError("CUDA error: device-side assert triggered")
        if mode == "lost":
            os._exit(9)                                   # silent exit, not SIGKILL: ambiguous
        if mode == "killed":
            os._exit(137)                                 # SIGKILL convention (OOM killer / session teardown)
        if mode == "ambiguous_cuda":
            raise RuntimeError("CUDA error: invalid argument")
        if mode == "nan_then_crash":
            import torch
            torch.save({"hist": [{"epoch": 1, "train_loss": float("nan")}]}, out / "state.pt")
            raise ValueError("best_state is None")
        hist = [{"epoch": e, "train_loss": (float("inf") if mode == "inf_loss" and e == 2 else 1.0 / e)} for e in (1, 2, 3)]
        conf = [[100, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]] if mode == "collapse" else \\
               [[50, 5, 0, 0], [5, 20, 0, 0], [0, 0, 30, 0], [2, 1, 0, 7]]
        ck = out / "best.pth"
        ck.write_bytes(f"weights of {cfg.name} seed {seed} n {n}".encode())
        sha = _sha(ck)
        res = {"experiment": cfg.name, "seed": seed, "config": dataclasses.asdict(cfg), "best_epoch": 2,
               "val_gt": {"macro_f1": 0.5, "confusion": conf}, "history": hist, "checkpoint": str(ck),
               "checkpoint_sha256": "0" * 64 if mode == "bad_hash" else sha}
        ck.with_suffix(".json").write_text(json.dumps({"version": f"kaggle_{cfg.name}_s{seed}", "checkpoint_sha256_full": sha}))
        (out / "result.json").write_text(json.dumps(res))
        if mode == "kill_after_checkpoint":
            os._exit(137)                                 # interrupted after best.pth + result.json, before the manifest
        return res
''')


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "fake_trainer.py").write_text(FAKE, encoding="utf-8")
    data = tmp_path / "cache"
    data.mkdir()
    fit_npz, inner_npz = data / "fit.npz", data / "inner.npz"
    np.savez(fit_npz, X=np.zeros((4, 2), np.float32), y=np.array([0, 1, 2, 3]))
    np.savez(inner_npz, X=np.zeros((2, 2), np.float32), y=np.array([0, 1]))
    rows = lambda pre, n: [{"sample_id": f"{pre}{i}", "project_image_id": f"{pre}img{i // 2}", "image_sha256": f"{i:064d}",   # noqa: E731
                            "image_path": f"x/{pre}{i}.png", "source_dataset": CV.PRIMARY, "radiograph_group": f"g{pre}{i}"} for i in range(n)]
    rows_json = CA.write_rows(data / "rows.json", rows("f", 4), rows("i", 2))
    runs = tmp_path / "runs"
    runs.mkdir()

    def run(fold=0, seed=42, mode="ok", name=None, **kw):
        cfg = dataclasses.replace(DK.EXPERIMENTS["BASE"], name=name or f"CV5_CAND_f{fold}", extra={"fake": mode})
        r = CA.run_isolated(cfg, seed, fold, fit_npz, inner_npz, rows_json, runs, log=lambda *a: None,
                            trainer="fake_trainer:train", extra_path=[tmp_path], **kw)
        return r, runs / f"{cfg.name}_s{seed}", cfg

    return {"run": run, "runs": runs, "fit": fit_npz, "inner": inner_npz, "rows": rows_json}


def predict(out: Path):
    np.savez(out / "heldout_pred.npz", idx=np.arange(3), gt=np.eye(4)[:3], det=np.eye(4)[:3])


# ---------------------------------------------------------------------------------------------------- manifests
def test_manifest_written_for_the_checkpoint_and_hashes_agree(env):
    r, out, cfg = env["run"]()
    assert r["status"] == "completed" and len(r["attempts"]) == 1
    m = json.loads((out / CA.MANIFEST_NAME).read_text())
    res = json.loads((out / "result.json").read_text())
    sha = CV.sha256_file(out / "best.pth")
    assert m["format"] == "dentamind-training-manifest-v1"
    assert m["checkpoint_sha256"] == sha == res["checkpoint_sha256"] == r["attempts"][0]["checkpoint_sha256"]
    assert m["checkpoint_file"] == "best.pth" and m["checkpoint_bytes"] == (out / "best.pth").stat().st_size
    assert m["cv"] == {**m["cv"], "run": f"{cfg.name}_s42", "fold": 0, "seed": 42, "best_epoch": 2,
                       "fold_file_sha256": CV.FOLD_FILE_SHA256, "fit_arrays_sha256": CV.sha256_file(env["fit"]),
                       "inner_arrays_sha256": CV.sha256_file(env["inner"])}
    assert m["training_config"] == dataclasses.asdict(cfg) and m["seed"] == 42
    assert m["counts"] == {"train": 2, "val": 1}                                  # images, not findings
    ref = r["attempts"][0]["manifest"]
    assert ref["sha256"] == CV.sha256_file(out / CA.MANIFEST_NAME)
    assert json.loads((out / "best.json").read_text())["training_manifest"] == ref    # registry sidecar points at it
    assert CA.verify_run_manifest(out, f"{cfg.name}_s42", 0, 42)["ok"]


def test_manifest_verification_detects_tampering(env):
    r, out, cfg = env["run"]()
    run = f"{cfg.name}_s42"
    mp = out / CA.MANIFEST_NAME
    m = json.loads(mp.read_text())
    m["cv"]["best_epoch"] = 3
    mp.write_text(json.dumps(m))
    v = CA.verify_run_manifest(out, run, 0, 42)
    assert not v["ok"] and any("differs from the one the worker wrote" in p for p in v["problems"])
    predict(out)
    st = CA.run_status(env["runs"], run, 0, 42)
    assert st["class"] == "incomplete" and not st["final_model_eligible"]


def test_checkpoint_replaced_after_manifest_is_detected(env):
    r, out, cfg = env["run"]()
    (out / "best.pth").write_bytes(b"other weights")
    v = CA.verify_run_manifest(out, f"{cfg.name}_s42", 0, 42)
    assert not v["ok"] and any("checkpoint SHA-256 disagrees" in p for p in v["problems"])


def test_manifest_write_failure_is_final_incomplete_and_not_retried(env):
    r, out, cfg = env["run"](mode="bad_hash")
    assert r["status"] == "final_failure" and r["class"] == "incomplete" and "manifest" in r["reason"]
    hist = json.loads((out / CA.ATTEMPTS_FILE).read_text())
    assert [h["status"] for h in hist] == ["manifest_failed"]
    assert not (out / CA.MANIFEST_NAME).exists()
    r2, _, _ = env["run"](mode="ok")                                              # rerun: refused, no new attempt
    assert r2["status"] == "final_failure" and (out / "fake_calls.txt").read_text() == "1"
    st = CA.run_status(env["runs"], f"{cfg.name}_s42", 0, 42)
    assert st["class"] == "incomplete" and not st["final_model_eligible"] and st["resumable"] is False


def test_result_without_recorded_attempt_is_never_given_a_late_manifest(env):
    out = env["runs"] / "CV5_CAND_f0_s42"
    out.mkdir()
    (out / "result.json").write_text("{}")
    r, out, _ = env["run"]()
    assert r["status"] == "final_failure" and r["class"] == "incomplete"
    assert not (out / CA.MANIFEST_NAME).exists() and not (out / "fake_calls.txt").exists()


def test_run_to_manifest_association_across_all_folds_and_seeds(env):
    expected = []
    for k in range(5):
        for sd in CV.SEEDS:
            r, out, cfg = env["run"](fold=k, seed=sd)
            assert r["status"] == "completed"
            predict(out)
            expected.append((k, sd, f"{cfg.name}_s{sd}"))
    shas = set()
    for k, sd, run in expected:
        m = json.loads((env["runs"] / run / CA.MANIFEST_NAME).read_text())
        assert (m["cv"]["run"], m["cv"]["fold"], m["cv"]["seed"]) == (run, k, sd)
        assert m["checkpoint_sha256"] == CV.sha256_file(env["runs"] / run / "best.pth")
        shas.add(m["checkpoint_sha256"])
    assert len(shas) == 25                                                         # one distinct checkpoint per run
    status = CA.collect_status(env["runs"], expected)
    assert status["all_ok"] and set(status["run_classes"].values()) == {"ok"}
    # fake-trainer runs are recorded as pre-flight and are never eligible for the final model
    assert all(v["preflight"] and not v["final_model_eligible"] for v in status["runs"].values())
    m = json.loads((env["runs"] / expected[0][2] / CA.MANIFEST_NAME).read_text())
    assert m["cv"]["trainer"] == "fake_trainer:train"
    # swapping two runs' manifests breaks both
    a, b = env["runs"] / expected[0][2], env["runs"] / expected[7][2]
    ma, mb = (a / CA.MANIFEST_NAME).read_bytes(), (b / CA.MANIFEST_NAME).read_bytes()
    (a / CA.MANIFEST_NAME).write_bytes(mb)
    (b / CA.MANIFEST_NAME).write_bytes(ma)
    status = CA.collect_status(env["runs"], expected)
    assert status["run_classes"][expected[0][2]] == status["run_classes"][expected[7][2]] == "incomplete"
    assert not status["all_ok"]


# ---------------------------------------------------------------------------------------------------- exception origin and retries
def test_exception_origin_classification():
    assert CA.exception_origin(RuntimeError("CUDA error: an illegal memory access was encountered")) == "infrastructure"
    assert CA.exception_origin(RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")) == "infrastructure"
    assert CA.exception_origin(MemoryError()) == "infrastructure"
    assert CA.exception_origin(RuntimeError("cuDNN error: CUDNN_STATUS_ALLOC_FAILED")) == "infrastructure"
    assert CA.exception_origin(RuntimeError("CUDA error: unspecified launch failure")) == "infrastructure"
    # ambiguous: can be caused by the computation itself -> never retried
    assert CA.exception_origin(RuntimeError("cuDNN error: CUDNN_STATUS_INTERNAL_ERROR")) == "computation"
    assert CA.exception_origin(RuntimeError("CUDA error: invalid argument")) == "computation"
    assert CA.exception_origin(RuntimeError("CUDA error: an illegal instruction was encountered")) == "computation"
    assert CA.exception_origin(RuntimeError("out of memory in my own buffer")) == "computation"
    assert CA.exception_origin(OSError("No space left on device")) == "computation"
    assert CA.exception_origin(RuntimeError("CUDA error: device-side assert triggered")) == "computation"
    assert CA.exception_origin(ValueError("shape mismatch")) == "computation"
    assert CA.exception_origin(RuntimeError("mat1 and mat2 shapes cannot be multiplied")) == "computation"
    assert CA.exception_origin(KeyError("x")) == "computation"


def test_infrastructure_failure_is_retried_and_recorded(env):
    r, out, _ = env["run"](mode="infra_once")
    assert r["status"] == "completed"
    assert [(h["status"], h.get("origin")) for h in r["attempts"]] == [("exception", "infrastructure"), ("completed", None)]
    assert r["attempts"][0]["type"] == "RuntimeError"
    predict(out)
    st = CA.run_status(env["runs"], out.name, 0, 42)
    assert st["class"] == "ok" and st["exception_origins"] == ["infrastructure"] and st["attempts"] == 2


def test_infrastructure_exhaustion_after_three_attempts_in_total(env):
    r, out, _ = env["run"](mode="infra_always")
    assert r["status"] == "infrastructure_exhausted" and len(r["attempts"]) == 3
    assert CA.run_status(env["runs"], out.name, 0, 42)["class"] == "infrastructure"
    r2, _, _ = env["run"](mode="infra_always")                                     # a resumed session gets no 4th attempt
    assert r2["status"] == "infrastructure_exhausted" and (out / "fake_calls.txt").read_text() == "3"


def test_host_out_of_memory_is_infrastructure(env):
    r, out, _ = env["run"](mode="oom_always")
    assert r["status"] == "infrastructure_exhausted" and {h["type"] for h in r["attempts"]} == {"MemoryError"}


def test_killed_process_is_infrastructure_and_retried(env):
    r, out, _ = env["run"](mode="killed")
    assert r["status"] == "infrastructure_exhausted" and [a["type"] for a in r["attempts"]] == ["killed"] * 3
    assert all(a["origin"] == "infrastructure" for a in r["attempts"])


def test_silent_exit_and_ambiguous_cuda_errors_are_not_retried(env):
    for mode in ("lost", "ambiguous_cuda"):
        r, out, _ = env["run"](mode=mode, name=f"CV5_{mode.replace('_', '')}_f0")
        assert r["status"] == "final_failure" and r["class"] == "incomplete"
        assert (out / "fake_calls.txt").read_text() == "1"
        assert CA.run_status(env["runs"], out.name, 0, 42)["class"] == "incomplete"
    assert json.loads((env["runs"] / "CV5_lost_f0_s42" / CA.ATTEMPTS_FILE).read_text())[0]["origin"] == "ambiguous"


def test_interruption_after_checkpoint_before_manifest_is_incomplete_without_late_manifest(env):
    r, out, _ = env["run"](mode="kill_after_checkpoint")
    assert (out / "best.pth").is_file() and (out / "result.json").is_file()
    assert not (out / CA.MANIFEST_NAME).exists()
    assert r["status"] == "final_failure" and r["class"] == "incomplete" and "none is written later" in r["reason"]
    assert (out / "fake_calls.txt").read_text() == "1"                            # the retry was refused before launching
    hist = json.loads((out / CA.ATTEMPTS_FILE).read_text())
    assert [(h["type"], h["origin"]) for h in hist] == [("killed", "infrastructure")]
    for _ in range(2):                                                            # later sessions: still refused, still no manifest
        assert env["run"](mode="ok")[0]["status"] == "final_failure"
    assert not (out / CA.MANIFEST_NAME).exists()
    st = CA.run_status(env["runs"], out.name, 0, 42)
    assert st["class"] == "incomplete" and not st["final_model_eligible"] and st["resumable"] is False
    rc = {r_: "ok" for r_ in [f"x{i}" for i in range(24)]} | {out.name: st["class"]}
    ok = {"V1": True, "V2": True, "V3": True, "V5": True, "V6": None}
    assert CA.verdict({"criteria": {}}, confirmatory=True, validity=ok, run_classes=rc)["verdict"] == "NO VERDICT"


def test_worker_refuses_a_late_manifest_even_if_called_directly(env, tmp_path):
    r, out, cfg = env["run"](mode="kill_after_checkpoint", name="CV5_direct_f0")
    spec = {"run": out.name, "fold": 0, "seed": 42, "attempt": 9, "cfg": dataclasses.asdict(cfg), "fit_npz": str(env["fit"]),
            "inner_npz": str(env["inner"]), "rows_json": str(env["rows"]), "out": str(env["runs"]),
            "fold_file_sha256": CV.FOLD_FILE_SHA256, "trainer": "fake_trainer:train"}
    assert CA.worker(spec) == 4
    rec = json.loads((out / "attempt_9.json").read_text())
    assert rec["status"] == "manifest_failed" and rec["type"] == "StaleArtifacts"
    assert not (out / CA.MANIFEST_NAME).exists()


def test_eligibility_requires_the_real_trainer(env):
    r, out, _ = env["run"]()
    predict(out)
    assert not CA.run_status(env["runs"], out.name, 0, 42)["final_model_eligible"]
    hist = json.loads((out / CA.ATTEMPTS_FILE).read_text())
    for h in hist:
        h["preflight"] = False                     # what a real-trainer attempt records
    (out / CA.ATTEMPTS_FILE).write_text(json.dumps(hist))
    assert CA.run_status(env["runs"], out.name, 0, 42)["final_model_eligible"]


def test_computation_exception_is_final_incomplete_without_retry(env):
    for mode in ("compute", "device_assert"):
        r, out, _ = env["run"](mode=mode, name=f"CV5_{mode.replace('_', '')}_f0")
        assert r["status"] == "final_failure" and r["class"] == "incomplete"
        assert len(json.loads((out / CA.ATTEMPTS_FILE).read_text())) == 1 and (out / "fake_calls.txt").read_text() == "1"
        st = CA.run_status(env["runs"], out.name, 0, 42)
        assert st["class"] == "incomplete" and st["exception_origins"] == ["computation"] and st["resumable"] is False


def test_nonfinite_loss_before_a_crash_is_divergence(env):
    pytest.importorskip("torch")
    r, out, _ = env["run"](mode="nan_then_crash")
    assert r["status"] == "final_failure" and r["class"] == "divergence"
    assert CA.run_status(env["runs"], out.name, 0, 42)["class"] == "divergence"


def test_completed_run_with_nonfinite_loss_or_collapse_is_divergence(env):
    for mode in ("inf_loss", "collapse"):
        r, out, _ = env["run"](mode=mode, name=f"CV5_{mode.replace('_', '')}_f0")
        assert r["status"] == "completed"                                          # trained; the class decides
        predict(out)
        st = CA.run_status(env["runs"], out.name, 0, 42)
        assert st["class"] == "divergence" and not st["final_model_eligible"]


def test_prediction_failures(env):
    r, out, _ = env["run"]()
    assert CA.record_prediction_failure(out, RuntimeError("CUDA error: unspecified launch failure"))["status"] == "retry_on_resume"
    st = CA.run_status(env["runs"], out.name, 0, 42)
    assert st["class"] == "incomplete" and st["resumable"]
    assert CA.record_prediction_failure(out, ValueError("bad crop"))["class"] == "incomplete"
    assert CA.run_status(env["runs"], out.name, 0, 42)["resumable"] is False


def test_unstarted_and_unpredicted_runs_are_incomplete(env):
    assert CA.run_status(env["runs"], "CV5_CAND_f3_s44", 3, 44)["class"] == "incomplete"
    r, out, _ = env["run"]()
    st = CA.run_status(env["runs"], out.name, 0, 42)
    assert st["class"] == "incomplete" and st["reason"] == "held-out prediction missing" and st["manifest"]["ok"]


# ---------------------------------------------------------------------------------------------------- verdict compatibility
def test_run_status_feeds_the_approved_verdict_rules(env):
    expected = [(k, sd, f"CV5_CAND_f{k}_s{sd}") for k in range(5) for sd in CV.SEEDS]
    for k, sd, _ in expected[:22]:
        _, out, _ = env["run"](fold=k, seed=sd)
        predict(out)
    _, out, _ = env["run"](fold=4, seed=45, mode="collapse")                         # run 23: divergence
    predict(out)
    env["run"](fold=4, seed=46, mode="infra_always")                                 # run 24: infrastructure exhausted
    # run 25 (fold 4 seed 44) never started
    st = CA.collect_status(env["runs"], expected)
    rc = st["run_classes"]
    assert rc["CV5_CAND_f4_s45"] == "divergence" and rc["CV5_CAND_f4_s46"] == "infrastructure"
    assert rc["CV5_CAND_f4_s44"] == "incomplete" and len(rc) == 25
    ok = {"V1": True, "V2": True, "V3": True, "V5": True, "V6": None}
    passing = {"criteria": {"P-A": {"pass": True}}}
    assert CA.verdict(passing, confirmatory=True, validity=ok, run_classes=rc)["verdict"] == "FAIL"
    rc_no_div = {**rc, "CV5_CAND_f4_s45": "ok"}
    assert CA.verdict(passing, confirmatory=True, validity=ok, run_classes=rc_no_div)["verdict"] == "NO VERDICT"
    assert CA.verdict(passing, confirmatory=True, validity={**ok, "V5": False}, run_classes=rc)["verdict"] == "NO VERDICT"
    all_ok = {r: "ok" for r in rc}
    assert CA.verdict(passing, confirmatory=True, validity=ok, run_classes=all_ok)["verdict"] == "ACCEPT"


# ---------------------------------------------------------------------------------------------------- notebook generator
def test_base_notebook_output_is_unchanged():
    want = (ROOT / "kaggle" / "dentamind_5fold_cv.ipynb").read_text(encoding="utf-8")
    assert json.dumps(NB._notebook(NB.CELLS), indent=1, ensure_ascii=False) + "\n" == want


def candidate_cfg(cid="PAD25"):
    import cv5_interventions as CI
    return dataclasses.asdict(CI.proposed_config(cid))


def test_candidate_cells_compile_and_use_the_manifest_runner():
    cells = NB.candidate_cells("TESTCAND", candidate_cfg())
    code = [src for kind, src in cells if kind == "code"]
    for src in code:
        compile(src, "<cell>", "exec")
    joined = "\n".join(s for s in code if "EMBEDDED_SHA256" not in s)          # embedded file sources excluded
    assert "CA.run_isolated(" in joined and "DK.train_run_isolated(" not in joined
    assert "CA.record_prediction_failure" in joined and "CA.collect_status(RUNS, EXPECTED_RUNS)" in joined
    assert 'RUN_STATUS["all_ok"]' in joined and "CV.run_name(" not in joined and "CV.fold_config(" not in joined
    assert "run_evidence" in joined and "CA.MANIFEST_NAME" in joined
    i_train = next(i for i, (_, s) in enumerate(cells) if "CA.run_isolated(" in s)
    i_ev = next(i for i, (_, s) in enumerate(cells) if "run evidence (always packaged" in s)
    i_agg = next(i for i, (_, s) in enumerate(cells) if 'assert RUN_STATUS["all_ok"]' in s)
    assert i_train < i_ev < i_agg                                                  # evidence is packaged before the gate-4 stop
    embed = next(s for _, s in cells if "EMBEDDED_SHA256" in s)
    assert CV.sha256_file(ROOT / "kaggle" / "cv5_accept.py") in embed and CV.FOLD_FILE_SHA256 in embed
    assert len(cells) == len(NB.CELLS) + 1
    assert "assert not os.environ.get(CA.PREFLIGHT_TRAINER_ENV)" in embed          # real candidates refuse the fake trainer


def test_preflight_switch_guard_is_outside_the_block_the_preflight_reuses():
    import make_cv5_preflight_notebook as PF
    embed = next(s for k, s in NB.candidate_cells("C1", candidate_cfg()) if "EMBEDDED_SHA256" in s)
    guard = embed.index("assert not os.environ.get(CA.PREFLIGHT_TRAINER_ENV)")
    assert guard < embed.index("CANDIDATE_ID = ")
    pf_embed = next(s for k, s in PF.build_cells() if "EMBEDDED_SHA256 = " in s)
    assert "assert not os.environ.get(CA.PREFLIGHT_TRAINER_ENV)" not in pf_embed


def test_candidate_definition_checks(tmp_path):
    with pytest.raises(ValueError):
        NB.candidate_cells("BASE", candidate_cfg())
    with pytest.raises(ValueError):
        NB.candidate_cells("bad-id", candidate_cfg())
    with pytest.raises(ValueError):
        NB.candidate_cells("C1", {k: v for k, v in candidate_cfg().items() if k != "lr"})
    with pytest.raises(ValueError):
        NB.write_candidate_notebook("C1", candidate_cfg(), tmp_path / "no_registration.md", tmp_path / "nb.ipynb")
    assert not (tmp_path / "nb.ipynb").exists()


# ---------------------------------------------------------------------------------------------------- Kaggle pre-flight notebook
def test_preflight_notebook_uses_candidate_cells_verbatim_and_no_data():
    import make_cv5_preflight_notebook as PF
    cells = PF.build_cells()
    import cv5_interventions as CI
    cand = NB.candidate_cells(PF.CANDIDATE_ID, dataclasses.asdict(dataclasses.replace(
        CI.proposed_config("PAD25"), name="PREFLIGHT", note="PREFLIGHT: fake trainer, no training")))
    cand_code = {src for kind, src in cand if kind == "code"}
    code = [src for kind, src in cells if kind == "code"]
    for src in code:
        compile(src, "<cell>", "exec")
    assert sum(src in cand_code for src in code) == 4                             # config, GPU, training, evidence cells
    joined = "\n".join(s for s in code if "EMBEDDED_SHA256 = " not in s)
    for forbidden in ("find_bundle", "load_split", "cv5_folds_v1.csv", "build_crops", "fetch_dentex", "ProductionDetector",
                      "BASE-P2", "write_candidate_notebook"):
        assert forbidden not in joined, forbidden
    embed = next(s for s in code if "EMBEDDED_SHA256 = " in s)
    for rel, p in PF.EMBED.items():
        assert CV.sha256_file(p) in embed, rel
    assert "assert not inputs" in embed and "PREFLIGHT_TRAINER_ENV" in embed
    want = (ROOT / "kaggle" / "dentamind_cv5_preflight.ipynb").read_text(encoding="utf-8")
    assert json.dumps(NB._notebook(cells), indent=1, ensure_ascii=False) + "\n" == want   # written notebook is current
