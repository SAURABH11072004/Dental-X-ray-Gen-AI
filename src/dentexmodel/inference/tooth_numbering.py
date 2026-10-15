"""Consistency checks for FDI tooth numbering of detected teeth. Never forces a number onto a region."""
from __future__ import annotations

from collections import defaultdict

from dentexmodel.data.fdi import is_valid_fdi, split_fdi


def check_numbering(teeth: list, image_width: float, image_height: float, min_conf: float = 0.5) -> dict:
    """``teeth``: dicts with ``fdi`` (int|None), ``fdi_confidence`` (float|None), ``box`` [x1,y1,x2,y2].

    Panoramic convention: image-left = patient-right, so quadrants 1 (upper right) / 4 (lower right) lie in the
    left image half and 2 / 3 in the right half; upper quadrants (1, 2) lie above lower quadrants (3, 4).
    Returns per-tooth status ('assigned' | 'unassigned' | 'needs_review') and a list of issues."""
    issues: list = []
    out: list = []
    by_code: dict = defaultdict(list)
    for i, t in enumerate(teeth):
        code = t.get("fdi")
        if code is not None and is_valid_fdi(code):
            by_code[int(code)].append(i)
    for i, t in enumerate(teeth):
        code, conf = t.get("fdi"), t.get("fdi_confidence")
        status, why = "assigned", []
        if code is None:
            status, why = "unassigned", ["no tooth number predicted"]
        elif not is_valid_fdi(code):
            status, why = "needs_review", [f"impossible FDI code {code}"]
        else:
            if len(by_code[int(code)]) > 1:
                status = "needs_review"
                why.append("duplicate tooth number")
            if conf is not None and conf < min_conf:
                status = "needs_review"
                why.append(f"low numbering confidence ({conf:.2f})")
            x1, y1, x2, y2 = t["box"]
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            q, _ = split_fdi(int(code))
            left_half = cx < image_width / 2
            if (q in (1, 4)) != left_half:
                status = "needs_review"
                why.append("horizontal position inconsistent with quadrant")
            upper = cy < image_height / 2
            if (q in (1, 2)) != upper:
                status = "needs_review"
                why.append("vertical position inconsistent with quadrant")
        if why:
            issues.append({"index": i, "fdi": code, "problems": why})
        out.append({"index": i, "fdi": code, "status": status, "problems": why})
    return {"teeth": out, "issues": issues, "n_needs_review": sum(1 for o in out if o["status"] == "needs_review"),
            "n_unassigned": sum(1 for o in out if o["status"] == "unassigned")}
