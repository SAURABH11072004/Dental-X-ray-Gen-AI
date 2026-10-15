"""Cross-platform, traversal-safe path helpers."""
from __future__ import annotations

from pathlib import Path, PurePosixPath

from dentexmodel.errors import DentaMindError


def safe_join(base: Path, *parts: str) -> Path:
    """Join ``parts`` below ``base`` and refuse anything that escapes it (``..``, absolute paths, symlinks)."""
    base_r = Path(base).resolve()
    candidate = base_r.joinpath(*[str(p) for p in parts]).resolve()
    try:
        candidate.relative_to(base_r)
    except ValueError:
        raise DentaMindError("Path escapes the allowed directory.", code="path_traversal", hint="Use a relative path inside the data directory.")
    return candidate


def to_posix_rel(path: Path, base: Path) -> str:
    """Relative POSIX-style string (stable across Windows/Linux) used in manifests."""
    return PurePosixPath(Path(path).resolve().relative_to(Path(base).resolve())).as_posix()


def ensure_dir(path: Path) -> Path:
    Path(path).mkdir(parents=True, exist_ok=True)
    return Path(path)
