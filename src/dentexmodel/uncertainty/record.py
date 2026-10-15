"""Unified uncertainty record. A signal that could not be computed is *unavailable* (value None), never 0."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

SIGNALS = ("entropy", "disagreement", "mask_instability", "detection_instability")


@dataclass
class Signal:
    value: float | None = None
    status: str = "unavailable"        # computed | unavailable
    reason: str | None = "not computed"

    @classmethod
    def computed(cls, v: float) -> "Signal":
        return cls(value=float(v), status="computed", reason=None)

    @classmethod
    def unavailable(cls, reason: str) -> "Signal":
        return cls(value=None, status="unavailable", reason=reason)


@dataclass
class UncertaintyRecord:
    image_id: str
    model_version: str | None = None
    entropy: Signal = field(default_factory=Signal)
    disagreement: Signal = field(default_factory=Signal)
    mask_instability: Signal = field(default_factory=Signal)
    detection_instability: Signal = field(default_factory=Signal)
    quality_flags: list = field(default_factory=list)
    quality_metrics: dict = field(default_factory=dict)
    methods: dict = field(default_factory=dict)      # how each signal was computed (shown in the UI next to the value)
    note: str = ""

    def available(self) -> dict:
        return {k: getattr(self, k).value for k in SIGNALS if getattr(self, k).status == "computed"}

    def combined(self, weights: dict | None = None) -> float | None:
        """Weighted mean over the *available* signals (weights renormalised). None if nothing is available."""
        w = {"entropy": 0.4, "disagreement": 0.4, "mask_instability": 0.2}
        w.update(weights or {})
        av = {k: v for k, v in self.available().items() if w.get(k, 0) > 0}
        tot = sum(w[k] for k in av)
        if not av or tot <= 0:
            return None
        return float(sum(w[k] * v for k, v in av.items()) / tot)

    def to_dict(self, weights: dict | None = None) -> dict:
        d = asdict(self)
        d["combined_score"] = self.combined(weights)
        d["image_quality_is_separate_from_uncertainty"] = True
        return d
