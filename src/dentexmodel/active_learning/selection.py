"""Acquisition strategies for uncertainty-guided active learning.

random        - seeded uniform sampling (baseline)
entropy       - highest normalised predictive entropy
disagreement  - highest ensemble disagreement (generalised Jensen-Shannon)
combined      - U(x) = w1*entropy + w2*disagreement + w3*mask_instability  (over available signals), then a
                greedy diversity-aware pass (maximal-marginal-relevance on image embeddings) with near-duplicate
                filtering.

Candidates whose required signal is unavailable are *skipped with a reason*, never scored as 0. Images in the
locked test split are refused (``LeakageError``).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict

import numpy as np

from dentexmodel.errors import ConfigError, LeakageError

STRATEGIES = ("random", "entropy", "disagreement", "combined")
WEIGHT_KEYS = ("entropy", "disagreement", "mask_instability")


class ActiveLearningConfigError(ConfigError):
    code = "invalid_active_learning_config"


@dataclass
class ALConfig:
    strategy: str = "combined"
    budget: int = 20
    batch_size: int = 10
    seed: int = 42
    diversity_weight: float = 0.3
    weights: dict = field(default_factory=lambda: {"entropy": 0.4, "disagreement": 0.4, "mask_instability": 0.2})
    near_duplicate_cosine: float = 0.995

    def validate(self) -> "ALConfig":
        errs = []
        if self.strategy not in STRATEGIES:
            errs.append(f"strategy must be one of {STRATEGIES}")
        if not isinstance(self.budget, int) or isinstance(self.budget, bool) or self.budget < 0:
            errs.append("budget must be a non-negative integer")
        if not isinstance(self.batch_size, int) or isinstance(self.batch_size, bool) or self.batch_size < 1:
            errs.append("batch_size must be an integer >= 1")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            errs.append("seed must be an integer")
        if not isinstance(self.diversity_weight, (int, float)) or not 0.0 <= float(self.diversity_weight) <= 1.0:
            errs.append("diversity_weight must be within [0, 1]")
        if not 0.0 < float(self.near_duplicate_cosine) <= 1.0:
            errs.append("near_duplicate_cosine must be within (0, 1]")
        if not isinstance(self.weights, dict) or set(self.weights) - set(WEIGHT_KEYS):
            errs.append(f"weights keys must be a subset of {WEIGHT_KEYS}")
        else:
            vals = [self.weights.get(k, 0.0) for k in WEIGHT_KEYS]
            if any((not isinstance(v, (int, float))) or v < 0 or not np.isfinite(v) for v in vals):
                errs.append("weights must be finite and non-negative")
            elif sum(vals) <= 0:
                errs.append("at least one weight must be > 0")
        if errs:
            raise ActiveLearningConfigError("; ".join(errs), hint="Fix the highlighted acquisition settings.")
        return self


@dataclass
class SelectedItem:
    image_id: str
    rank: int
    score: float | None
    reason: str
    signals: dict = field(default_factory=dict)
    diversity: float | None = None


@dataclass
class SelectionResult:
    strategy: str
    config: dict
    pool_size: int
    selected: list
    skipped: list
    batches: list
    notes: list
    input_fingerprint: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["selected_ids"] = [s.image_id for s in self.selected]
        return d


def _get(c: dict, key: str):
    v = c.get(key)
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def _embed_matrix(cands: list):
    embs = [c.get("embedding") for c in cands]
    if sum(e is not None for e in embs) < 2:
        return None
    dims = {len(e) for e in embs if e is not None}
    if len(dims) != 1:
        return None
    dim = dims.pop()
    m = np.zeros((len(cands), dim))
    has = np.zeros(len(cands), dtype=bool)
    for i, e in enumerate(embs):
        if e is not None:
            v = np.asarray(e, dtype=np.float64)
            n = np.linalg.norm(v)
            if n > 0:
                m[i], has[i] = v / n, True
    return m, has


def combined_score(c: dict, weights: dict):
    av = {k: _get(c, k) for k in WEIGHT_KEYS}
    av = {k: v for k, v in av.items() if v is not None and weights.get(k, 0) > 0}
    tot = sum(weights[k] for k in av)
    if not av or tot <= 0:
        return None, {}
    return float(sum(weights[k] * v for k, v in av.items()) / tot), av


def select_candidates(candidates: list, cfg: ALConfig, exclude_ids=(), test_ids=()) -> SelectionResult:
    cfg.validate()
    notes: list = []
    skipped: list = []
    test_ids = set(test_ids)
    clash = sorted({c["image_id"] for c in candidates} & test_ids)
    if clash:
        raise LeakageError(f"{len(clash)} candidate(s) belong to the locked test split: {clash[:5]}",
                           hint="Remove test-split images from the unlabeled pool.")
    exclude = set(exclude_ids)
    seen: set = set()
    pool: list = []
    for c in candidates:
        iid = str(c["image_id"])
        if iid in seen:
            skipped.append({"image_id": iid, "reason": "duplicate candidate id"})
            continue
        seen.add(iid)
        if iid in exclude:
            skipped.append({"image_id": iid, "reason": "already labeled / excluded"})
            continue
        pool.append({**c, "image_id": iid})
    pool.sort(key=lambda c: c["image_id"])
    fp = hashlib.sha256(json.dumps([[c["image_id"], c.get("entropy"), c.get("disagreement"), c.get("mask_instability")]
                                    for c in pool], sort_keys=True, default=str).encode()).hexdigest()[:16]
    result = lambda sel: SelectionResult(cfg.strategy, asdict(cfg), len(pool), sel, skipped, _batches(sel, cfg.batch_size),  # noqa: E731
                                         notes, fp)
    if not pool:
        notes.append("Candidate pool is empty - nothing to select.")
        return result([])
    budget = min(cfg.budget, len(pool))
    if cfg.budget > len(pool):
        notes.append(f"Budget {cfg.budget} exceeds pool size {len(pool)}; selecting {len(pool)}.")
    if budget == 0:
        return result([])

    if cfg.strategy == "random":
        rng = np.random.default_rng(cfg.seed)
        order = rng.permutation(len(pool))[:budget]
        sel = [SelectedItem(pool[i]["image_id"], r + 1, None, f"random sample (seed={cfg.seed})") for r, i in enumerate(order)]
        return result(sel)

    if cfg.strategy in ("entropy", "disagreement"):
        key = cfg.strategy
        scored = []
        for c in pool:
            v = _get(c, key)
            if v is None:
                skipped.append({"image_id": c["image_id"], "reason": f"{key} unavailable"})
            else:
                scored.append((v, c))
        if not scored:
            notes.append(f"No candidate has a computed '{key}' signal; run model scoring first.")
            return result([])
        scored.sort(key=lambda t: (-t[0], t[1]["image_id"]))
        sel = [SelectedItem(c["image_id"], r + 1, v, f"{key}={v:.3f} (rank {r + 1}/{len(scored)})", {key: v})
               for r, (v, c) in enumerate(scored[:budget])]
        return result(sel)

    # combined = uncertainty + diversity
    scored = []
    for c in pool:
        u, used = combined_score(c, cfg.weights)
        if u is None:
            skipped.append({"image_id": c["image_id"], "reason": "no uncertainty signal available"})
        else:
            scored.append((u, c, used))
    if not scored:
        notes.append("No candidate has any computed uncertainty signal; run model scoring first.")
        return result([])
    emb = _embed_matrix([c for _, c, _ in scored])
    lam = float(cfg.diversity_weight)
    if emb is None:
        if lam > 0:
            notes.append("Embeddings unavailable: diversity term skipped (uncertainty-only ranking).")
        lam = 0.0
        E = has = None
    else:
        E, has = emb
    remaining = list(range(len(scored)))
    chosen: list = []
    mind = np.full(len(scored), np.inf)
    out: list = []
    while remaining and len(out) < budget:
        best_i, best_val, best_div = None, -np.inf, None
        for i in remaining:
            u = scored[i][0]
            div = None
            if E is not None and has[i] and chosen:
                div = float(mind[i])
            val = u if (div is None or lam == 0) else (1 - lam) * u + lam * div
            if val > best_val + 1e-12 or (abs(val - best_val) <= 1e-12 and best_i is not None
                                          and scored[i][1]["image_id"] < scored[best_i][1]["image_id"]):
                best_i, best_val, best_div = i, val, div
        i = best_i
        remaining.remove(i)
        if E is not None and has[i] and chosen:
            cos = float(np.max(E[chosen][:, :] @ E[i])) if has[i] else 0.0
            if cos >= cfg.near_duplicate_cosine:
                skipped.append({"image_id": scored[i][1]["image_id"], "reason": f"near-duplicate (cosine {cos:.4f})"})
                continue
        u, c, used = scored[i]
        reason = "U=" + f"{u:.3f}" + " from " + ", ".join(f"{k}={v:.3f}" for k, v in used.items())
        if best_div is not None:
            reason += f"; diversity={best_div:.3f} (weight {lam})"
        out.append(SelectedItem(c["image_id"], len(out) + 1, float(u), reason, {k: float(v) for k, v in used.items()}, best_div))
        if E is not None and has[i]:
            chosen.append(i)
            d = (1 - (E @ E[i])) / 2.0
            mind = np.minimum(mind, np.where(has, d, np.inf))
    if len(out) < budget:
        notes.append(f"Selected {len(out)} of requested {budget}: pool exhausted after duplicate/missing-signal filtering.")
    return result(out)


def _batches(sel: list, batch_size: int) -> list:
    ids = [s.image_id for s in sel]
    return [ids[i:i + batch_size] for i in range(0, len(ids), batch_size)]
