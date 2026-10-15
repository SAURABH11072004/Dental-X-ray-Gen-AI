"""Training configuration validation and prerequisite checks (no fake progress, no fake metrics)."""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass, asdict

from dentexmodel.annotation.labelstudio import AnnotationStore
from dentexmodel.config import Settings
from dentexmodel.data.dataset import DatasetService
from dentexmodel.errors import ConfigError

TASKS = ("classification", "detection", "segmentation", "numbering")
ARCHITECTURES = {"classification": ["resnet50", "resnet18"], "detection": ["fasterrcnn_resnet50_fpn"],
                 "segmentation": ["maskrcnn_resnet50_fpn"], "numbering": ["fasterrcnn_resnet50_fpn"]}
# minimum annotation level required in the manifest for each task
REQUIRED_LEVEL = {"classification": "quadrant_enumeration_disease", "detection": "quadrant_enumeration", "segmentation": "quadrant_enumeration", "numbering": "quadrant_enumeration"}


@dataclass
class TrainConfig:
    task: str = "classification"
    architecture: str = "resnet50"
    experiment_name: str = "experiment"
    dataset_version: str = "current"
    epochs: int = 20
    batch_size: int = 8
    learning_rate: float = 1e-4
    image_size: int = 224
    device: str = "auto"
    seed: int = 42
    resume_checkpoint: str | None = None
    use_approved_annotations: bool = False
    pretrained: bool = True            # ImageNet (classifier) / COCO (detector) weights from the official torchvision URLs
    label_mode: str = "tooth"          # detection/segmentation: "tooth" (one class) or "fdi" (32 tooth numbers)
    num_workers: int = 0               # DataLoader workers (0 = in-process; safest on Windows)
    max_train_images: int | None = None   # cap for smoke tests; never set for a real experiment
    max_val_images: int | None = None
    min_free_gpu_mb: int | None = None  # override the built-in GPU memory pre-check

    def validate(self) -> list:
        e = []
        if self.task not in TASKS:
            e.append(f"task must be one of {TASKS}")
        elif self.architecture not in ARCHITECTURES[self.task]:
            e.append(f"architecture for {self.task} must be one of {ARCHITECTURES[self.task]}")
        if not isinstance(self.experiment_name, str) or not self.experiment_name.strip() or len(self.experiment_name) > 64 \
                or not all(c.isalnum() or c in "-_." for c in self.experiment_name):
            e.append("experiment_name must be 1-64 characters: letters, digits, '-', '_' or '.'")
        if not isinstance(self.epochs, int) or not 1 <= self.epochs <= 1000:
            e.append("epochs must be an integer between 1 and 1000")
        if not isinstance(self.batch_size, int) or not 1 <= self.batch_size <= 512:
            e.append("batch_size must be an integer between 1 and 512")
        if not isinstance(self.learning_rate, (int, float)) or not 0 < self.learning_rate <= 1:
            e.append("learning_rate must be in (0, 1]")
        if not isinstance(self.image_size, int) or not 32 <= self.image_size <= 4096:
            e.append("image_size must be an integer between 32 and 4096")
        if self.label_mode not in ("tooth", "fdi"):
            e.append("label_mode must be 'tooth' or 'fdi'")
        if self.num_workers < 0 or self.num_workers > 16:
            e.append("num_workers must be between 0 and 16")
        if self.device not in ("auto", "cpu", "cuda"):
            e.append("device must be auto, cpu or cuda")
        return e

    def assert_valid(self) -> "TrainConfig":
        errs = self.validate()
        if errs:
            raise ConfigError("; ".join(errs), hint="Correct the training configuration.")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def check_prerequisites(settings: Settings, cfg: TrainConfig) -> dict:
    """Return ``{"ready": bool, "unmet": [{"code","message","fix"}]}`` - why training can or cannot start."""
    unmet = []
    ds = DatasetService(settings).status()
    if not ds.main_available:
        unmet.append({"code": "main_dataset_missing", "message": "Main dataset is not available.",
                      "fix": "Place the dataset in data/<expected-file-name>: " + ds.expected_location})
    else:
        manifest = DatasetService(settings).manifest("main")
        need = REQUIRED_LEVEL.get(cfg.task)
        order = ("none", "detection", "quadrant", "quadrant_enumeration", "quadrant_enumeration_disease")
        have = [r for r in manifest if r.annotation_status == "annotated" and r.split == "train"
                and need in order and order.index(r.annotation_level) >= order.index(need)]
        if not have:
            unmet.append({"code": "no_training_labels", "message": f"No training images with '{need}' annotations for {cfg.task}.",
                          "fix": "Check the annotation JSON; run 'python scripts/validate_dataset.py'."})
        if cfg.task == "segmentation" and not any(r.has_masks for r in have):
            unmet.append({"code": "no_masks", "message": "No ground-truth instance masks in the training split.",
                          "fix": "Segmentation requires polygon masks (DENTEX provides them for a subset) or annotate masks in Label Studio."})
    from dentexmodel.annotation.reviews import ReviewStore
    from dentexmodel.storage import Database
    n_reviews = len(ReviewStore(Database(settings.db_path)).training_items(settings)[0]) if cfg.use_approved_annotations else 0
    if cfg.use_approved_annotations and not (AnnotationStore(settings.annotations_dir).approved_records() or n_reviews):
        unmet.append({"code": "no_approved_annotations", "message": "No approved annotations to train on.",
                      "fix": "Import, validate and approve annotations on the Annotation Studio page."})
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("torchvision") is None:
        unmet.append({"code": "torch_missing", "message": "PyTorch/torchvision are not installed.",
                      "fix": "pip install -r requirements-ml.txt (choose the CUDA build matching your driver)."})
    if cfg.resume_checkpoint:
        # only a registered, verified dental checkpoint of the same task inside the checkpoint folder may be resumed (no arbitrary paths)
        from dentexmodel.inference.registry import scan_checkpoints
        rid = str(cfg.resume_checkpoint).replace("\\", "/")
        match = next((m for m in scan_checkpoints(settings) if m.model_id == rid), None) if ".." not in rid.split("/") else None
        if match is None:
            unmet.append({"code": "checkpoint_missing", "message": f"Resume checkpoint '{cfg.resume_checkpoint}' is not a registered checkpoint.",
                          "fix": "Choose an existing checkpoint from the Model Registry."})
        elif not match.dental_specific or match.task != cfg.task:
            unmet.append({"code": "checkpoint_incompatible", "message": f"'{cfg.resume_checkpoint}' is not a verified {cfg.task} checkpoint.",
                          "fix": "Resume only from a verified checkpoint of the same task."})
    return {"ready": not unmet, "unmet": unmet, "main_dataset_available": ds.main_available}
