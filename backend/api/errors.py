from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dentexmodel.errors import DentaMindError

logger = logging.getLogger(__name__)


def error_body(code: str, message: str, hint: str | None = None, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "hint": hint, "details": details or {}}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DentaMindError)
    async def _dm(_req: Request, exc: DentaMindError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.hint, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _val(_req: Request, exc: RequestValidationError):
        msgs = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
        return JSONResponse(status_code=422, content=error_body("validation_error", "; ".join(msgs) or "Invalid request", "Check the highlighted fields."))

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception):
        logger.exception("unhandled error")
        return JSONResponse(status_code=500, content=error_body("internal_error", "Unexpected server error.", "See logs/dentamind.log."))
