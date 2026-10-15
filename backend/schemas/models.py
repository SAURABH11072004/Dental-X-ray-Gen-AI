"""Pydantic request/response schemas (inputs are validated before reaching the services)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=128)
    model_version: Optional[str] = None
    with_classification: bool = True


class PredictBatchRequest(BaseModel):
    image_ids: list[str] = Field(min_length=1, max_length=25)
    with_classification: bool = True


class EvaluateRequest(BaseModel):
    split: Literal["val", "calibration"] = "val"      # the locked test split can only be evaluated from the CLI (--final-test)
    max_images: Optional[int] = Field(default=None, ge=1, le=100000)


class FullAnalysisRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=128)
    segmentation: bool = True
    uncertainty: bool = True


class ExplainRequest(BaseModel):
    image_id: str = Field(min_length=1, max_length=128)
    box: list[float] = Field(min_length=4, max_length=4)


class UncertaintyRequest(BaseModel):
    image_id: Optional[str] = Field(default=None, max_length=128)
    model_version: Optional[str] = None
    probabilities: Optional[list] = None
    member_probabilities: Optional[list] = None
    mask_runs: Optional[list] = None
    weights: Optional[dict[str, float]] = None


class SelectRequest(BaseModel):
    strategy: Literal["random", "entropy", "disagreement", "combined"] = "combined"
    budget: int = Field(default=20, ge=0, le=100000)
    batch_size: int = Field(default=10, ge=1, le=10000)
    seed: int = 42
    diversity_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    weights: dict[str, float] = Field(default_factory=lambda: {"entropy": 0.4, "disagreement": 0.4, "mask_instability": 0.2})
    model_version: Optional[str] = None


class TrainRequest(BaseModel):
    task: Literal["classification", "detection", "segmentation", "numbering"]
    architecture: str
    experiment_name: str = Field(min_length=1, max_length=64)
    dataset_version: str = "current"
    epochs: int = Field(ge=1, le=1000)
    batch_size: int = Field(ge=1, le=512)
    learning_rate: float = Field(gt=0, le=1)
    image_size: int = Field(ge=32, le=4096)
    device: Literal["auto", "cpu", "cuda"] = "auto"
    seed: int = 42
    resume_checkpoint: Optional[str] = None
    use_approved_annotations: bool = False
    pretrained: bool = True
    label_mode: Literal["tooth", "fdi"] = "tooth"
    max_train_images: Optional[int] = Field(default=None, ge=1, le=100000)   # SMOKE TEST ONLY
    max_val_images: Optional[int] = Field(default=None, ge=1, le=100000)     # SMOKE TEST ONLY
    dry_run: bool = False                                                    # validate everything, start nothing


class ReportRequest(BaseModel):
    analysis_id: Optional[str] = None
    image_id: Optional[str] = None
    model_version: Optional[str] = None
    findings: Optional[list[dict[str, Any]]] = None
    mode: Literal["auto", "template", "llm"] = "auto"


class ReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=80)


class ImportRequest(BaseModel):
    tasks: list[dict[str, Any]]


class PullRequest(BaseModel):
    project_id: int


class ApproveRequest(BaseModel):
    image_ids: list[str] = Field(min_length=1)
    reviewer: str = Field(min_length=1, max_length=80)


class ExportRequest(BaseModel):
    round_id: str
    push_to_label_studio: bool = False
    title: Optional[str] = None


class ModelSelectRequest(BaseModel):
    model_id: str
    task: Literal["detection", "segmentation", "classification", "numbering"]
    approved_by: Optional[str] = None
    confirm: bool = False
    justification: Optional[str] = Field(default=None, max_length=2000)


class RollbackRequest(BaseModel):
    task: Literal["detection", "segmentation", "classification", "numbering"]
    approved_by: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2000)
