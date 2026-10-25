"""Candidate interventions for CV5 candidates (reports/cv5_amendment_01_candidate_registration.md, DRAFT; not registered).

Each intervention is selected only through ``ExpConfig.extra`` and is off by default, so the BASE recipe (``extra == {}``) is the
unchanged DK code path:

  crop_size  (F1)  GT and detector crops resized to this many pixels instead of dsutil.CROP_SIZE (224); C1 proposes 384
  crop_pad   (F1)  context padding as a fraction of box width / height instead of dsutil.CROP_PAD (0.10); C2 proposes 0.25
  backbone   (F2)  "resnet50" (BASE) or "convnext_tiny" (torchvision ConvNeXt-Tiny, IMAGENET1K_V1); C3 proposes convnext_tiny

kaggle/dentamind_kaggle.py and scripts/dataset/dsutil.py are NOT modified (they are in the hashed Kaggle bundle and define BASE).
Crops reuse dsutil.crop_region, which already takes size and pad as arguments; the DK crop builders and DK.train_run read module
constants and DK.new_model, so the candidate path calls them with those names temporarily rebound inside crop_rule() / model_rule().
Training runs in its own worker process (cv5_accept.run_isolated), so the rebinding there never touches another run.
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
from pathlib import Path

import dentamind_kaggle as DK
import dsutil

TRAINER = "cv5_interventions:train_run"
BASE_NEW_MODEL = DK.new_model           # bound once at import: model_rule() rebinds DK.new_model, BASE construction never recurses
DEFAULTS = {"crop_size": dsutil.CROP_SIZE, "crop_pad": dsutil.CROP_PAD, "backbone": "resnet50"}
FAMILY = {"crop_size": "F1", "crop_pad": "F1", "backbone": "F2"}
BACKBONES = ("resnet50", "convnext_tiny")
PROPOSED = {"CROP384": {"crop_size": 384}, "PAD25": {"crop_pad": 0.25}, "CNXTT": {"backbone": "convnext_tiny"}}
BASE_FIELDS_COMPARED = [f.name for f in dataclasses.fields(DK.ExpConfig) if f.name not in ("name", "note", "extra")]


class InterventionError(ValueError):
    pass


def resolve(extra: dict | None) -> dict:
    """Validated intervention settings: DEFAULTS overridden by the keys present in extra; unknown keys or values refuse."""
    extra = dict(extra or {})
    unknown = sorted(set(extra) - set(DEFAULTS))
    if unknown:
        raise InterventionError(f"unknown intervention key(s) {unknown}; allowed {sorted(DEFAULTS)}")
    out = {**DEFAULTS, **extra}
    if not (isinstance(out["crop_size"], int) and not isinstance(out["crop_size"], bool) and 32 <= out["crop_size"] <= 1024):
        raise InterventionError(f"crop_size must be an int in 32..1024, got {out['crop_size']!r}")
    if not (isinstance(out["crop_pad"], (int, float)) and not isinstance(out["crop_pad"], bool) and 0 <= out["crop_pad"] <= 1):
        raise InterventionError(f"crop_pad must be a number in 0..1, got {out['crop_pad']!r}")
    if out["backbone"] not in BACKBONES:
        raise InterventionError(f"backbone must be one of {BACKBONES}, got {out['backbone']!r}")
    return out


def config_diff(cfg) -> dict:
    """Differences from EXPERIMENTS["BASE"]: ExpConfig fields (name / note excluded) plus intervention keys that differ from DEFAULTS."""
    base = DK.EXPERIMENTS["BASE"]
    d = {f: (getattr(base, f), getattr(cfg, f)) for f in BASE_FIELDS_COMPARED if getattr(cfg, f) != getattr(base, f)}
    r = resolve(cfg.extra)
    d.update({f"extra.{k}": (DEFAULTS[k], r[k]) for k in DEFAULTS if r[k] != DEFAULTS[k]})
    return d


def check_single_intervention(cfg) -> dict:
    """V3 config-diff gate (protocol section 5.3): exactly one intervention key, nothing else changed. Returns {key, family, value}."""
    d = config_diff(cfg)
    if len(d) != 1 or not next(iter(d)).startswith("extra."):
        raise InterventionError(f"a candidate must differ from BASE in exactly one intervention key; differences: {d}")
    key = next(iter(d))[len("extra."):]
    return {"key": key, "family": FAMILY[key], "value": d[f"extra.{key}"][1]}


def proposed_config(cid: str, data: str = "dentex"):
    """ExpConfig of a proposed candidate (BASE recipe + its one intervention key). data: the BASE-P2 data option once registered."""
    if cid not in PROPOSED:
        raise InterventionError(f"unknown proposed candidate {cid!r}; proposed: {sorted(PROPOSED)}")
    return dataclasses.replace(DK.EXPERIMENTS["BASE"], name=cid, data=data, extra=dict(PROPOSED[cid]),
                               note=f"CV5 candidate {cid} (DRAFT Amendment 01): BASE + {PROPOSED[cid]}")


def crop_tag(extra) -> str:
    r = resolve(extra)
    return f"s{r['crop_size']}_p{r['crop_pad']:.2f}"


@contextlib.contextmanager
def crop_rule(extra):
    """Rebind DK.CROP_SIZE / DK.CROP_PAD for the duration of a DK crop-builder call (restored on exit, also on error)."""
    r = resolve(extra)
    old = DK.CROP_SIZE, DK.CROP_PAD
    DK.CROP_SIZE, DK.CROP_PAD = r["crop_size"], r["crop_pad"]
    try:
        yield r
    finally:
        DK.CROP_SIZE, DK.CROP_PAD = old


def build_crops(rows, data_root, cache_file, extra):
    """DK.build_crops with the candidate's crop rule. The cache file name must carry crop_tag(extra) (DK's cache checks ids only)."""
    if cache_file and crop_tag(extra) not in Path(cache_file).name:
        raise InterventionError(f"cache file {cache_file} does not carry the crop tag {crop_tag(extra)}")
    with crop_rule(extra):
        return DK.build_crops(rows, data_root, cache_file)


def build_detector_crops(rows, data_root, det_cache_path, image_id_of, extra):
    with crop_rule(extra):
        return DK.build_detector_crops(rows, data_root, det_cache_path, image_id_of)


def new_model(torch, tv, extra, pretrained=True):
    """BASE: exactly DK.new_model. convnext_tiny: torchvision ConvNeXt-Tiny with its last classifier layer replaced by a
    len(CLASSES)-way linear layer (same class order as BASE)."""
    r = resolve(extra)
    if r["backbone"] == "resnet50":
        return BASE_NEW_MODEL(torch, tv, pretrained=pretrained)
    m = tv.models.convnext_tiny(weights=tv.models.ConvNeXt_Tiny_Weights.IMAGENET1K_V1 if pretrained else None)
    m.classifier[2] = torch.nn.Linear(m.classifier[2].in_features, len(DK.CLASSES))
    return m


@contextlib.contextmanager
def model_rule(extra):
    """Rebind DK.new_model so DK.train_run builds the candidate's backbone (restored on exit)."""
    old = DK.new_model
    DK.new_model = lambda torch, tv, pretrained=True: new_model(torch, tv, extra, pretrained=pretrained)  # noqa: E731
    try:
        yield
    finally:
        DK.new_model = old


def train_run(cfg, seed, train, val, out_dir, log=print):
    """Trainer for candidate runs (selected by cv5_accept for configs with intervention keys). BASE config -> DK.train_run unchanged.
    The sidecar DK writes says resnet50 / 224 / 0.10; it is corrected to the run's actual architecture and crop rule."""
    r = resolve(cfg.extra)
    if r == DEFAULTS:
        return DK.train_run(cfg, seed, train, val, out_dir, log=log)
    if train["X"].shape[1:3] != (r["crop_size"], r["crop_size"]) or val["X"].shape[1:3] != (r["crop_size"], r["crop_size"]):
        raise InterventionError(f"crop arrays {train['X'].shape[1:3]} / {val['X'].shape[1:3]} do not match crop_size {r['crop_size']}")
    with crop_rule(cfg.extra), model_rule(cfg.extra):
        res = DK.train_run(cfg, seed, train, val, out_dir, log=log)
    side = Path(res["checkpoint"]).with_suffix(".json")
    meta = json.loads(side.read_text(encoding="utf-8"))
    meta.update({"architecture": r["backbone"], "image_size": r["crop_size"], "crop_pad": r["crop_pad"],
                 "pretrained": "torchvision IMAGENET1K_V1 (ConvNeXt-Tiny)" if r["backbone"] == "convnext_tiny" else meta.get("pretrained"),
                 "intervention": {k: r[k] for k in DEFAULTS if r[k] != DEFAULTS[k]},
                 "trained_by": "kaggle/cv5_interventions.py train_run (CV5 candidate path)"})
    side.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return res
