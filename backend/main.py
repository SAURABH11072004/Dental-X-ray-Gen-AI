"""DentaMind AI backend. Run:  uvicorn backend.main:app --reload --port 8000"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fastapi import FastAPI  # noqa: E402
from backend.version import APP_VERSION  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.api import active_learning, annotations, experiments, health, predict, reports, reviews, training, upload  # noqa: E402
from backend.api.errors import register_error_handlers  # noqa: E402
from backend.services.context import get_context  # noqa: E402


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ctx = get_context()
    ctx.start_background()  # detects/processes the dataset now and whenever it changes
    yield
    ctx.stop_background()


def create_app() -> FastAPI:
    app = FastAPI(title="DentaMind AI API", version=APP_VERSION, lifespan=lifespan,
                  description="Research software. Outputs are model predictions, not clinical diagnoses.")
    s = get_context().settings
    origins = {s.frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"}
    from backend.security import SecurityMiddleware, load_token
    app.add_middleware(SecurityMiddleware, token=load_token(s.project_root))    # innermost: CORS (added next) answers pre-flights first
    app.add_middleware(CORSMiddleware, allow_origins=sorted(origins), allow_methods=["*"], allow_headers=["*"])
    register_error_handlers(app)
    for r in (health, upload, predict, active_learning, annotations, reviews, training, reports, experiments):
        app.include_router(r.router)
    return app


app = create_app()
