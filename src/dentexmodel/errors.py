"""Shared exception types. Every error carries a stable ``code`` and an actionable ``hint``
so the API and UI can show useful messages instead of stack traces."""
from __future__ import annotations


class DentaMindError(Exception):
    code = "dentamind_error"
    status_code = 400

    def __init__(self, message: str, hint: str | None = None, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "hint": self.hint, "details": self.details}


class DatasetUnavailableError(DentaMindError):
    code = "dataset_unavailable"
    status_code = 409


class ModelUnavailableError(DentaMindError):
    code = "model_unavailable"
    status_code = 503


class ImageValidationError(DentaMindError):
    code = "invalid_image"
    status_code = 422


class ConfigError(DentaMindError):
    code = "invalid_configuration"
    status_code = 422


class LeakageError(DentaMindError):
    code = "split_leakage"
    status_code = 409


class NotFoundError(DentaMindError):
    code = "not_found"
    status_code = 404


class ConflictError(DentaMindError):
    code = "conflict"
    status_code = 409


class ExternalServiceError(DentaMindError):
    code = "external_service_unavailable"
    status_code = 502
