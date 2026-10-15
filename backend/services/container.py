"""Service container shared by the API routers."""
from __future__ import annotations

from backend.services.active_learning import ActiveLearningService
from backend.services.analysis import AnalysisService
from backend.services.annotations import AnnotationService
from backend.services.context import AppContext, get_context
from backend.services.experiments import ExperimentService
from backend.services.images import ImageService
from backend.services.pipeline import PipelineService
from backend.services.reviews import ReviewService
from backend.services.reports import ReportService
from backend.services.system import SystemService


class Services:
    def __init__(self, ctx: AppContext):
        self.ctx = ctx
        self.images = ImageService(ctx)
        self.analysis = AnalysisService(ctx, self.images)
        self.pipeline = PipelineService(ctx, self.images, self.analysis)
        self.reviews = ReviewService(ctx, self.images)
        self.al = ActiveLearningService(ctx, self.analysis, self.pipeline)
        self.annotations = AnnotationService(ctx)
        self.reports = ReportService(ctx, self.analysis)
        self.experiments = ExperimentService(ctx)
        self.system = SystemService(ctx, self.annotations, self.experiments, self.al)


_services: Services | None = None


def get_services() -> Services:
    global _services
    ctx = get_context()
    if _services is None or _services.ctx is not ctx:
        _services = Services(ctx)
    return _services
