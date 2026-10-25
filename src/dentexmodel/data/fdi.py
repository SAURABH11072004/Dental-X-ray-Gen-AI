"""FDI two-digit tooth numbering helpers (quadrant 1-4 / position 1-8; deciduous 5-8 optional)."""
from __future__ import annotations

QUADRANT_NAMES = {1: "upper right", 2: "upper left", 3: "lower left", 4: "lower right"}


def is_valid_fdi(code, allow_deciduous: bool = False) -> bool:
    try:
        n = int(code)
    except (TypeError, ValueError):
        return False
    if str(code).strip() != str(n):  # reject 11.5, '1 1' ...
        return False
    quad, pos = divmod(n, 10)
    if allow_deciduous:
        return (1 <= quad <= 4 and 1 <= pos <= 8) or (5 <= quad <= 8 and 1 <= pos <= 5)
    return 1 <= quad <= 4 and 1 <= pos <= 8


def fdi_from_parts(quadrant, position) -> int | None:
    """Combine a quadrant (1-4) and in-quadrant position (1-8) into an FDI code, or None if invalid."""
    try:
        code = int(quadrant) * 10 + int(position)
    except (TypeError, ValueError):
        return None
    return code if is_valid_fdi(code) else None


def split_fdi(code: int) -> tuple[int, int]:
    return divmod(int(code), 10)


def quadrant_name(code: int) -> str:
    return QUADRANT_NAMES.get(split_fdi(code)[0], "unknown")


def all_permanent_fdi() -> list[int]:
    return [q * 10 + p for q in range(1, 5) for p in range(1, 9)]
