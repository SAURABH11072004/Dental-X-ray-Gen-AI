"""Review service: queue of regions awaiting human review + submit / approve / export, on top of ReviewStore."""
from __future__ import annotations

from dentexmodel.annotation.reviews import ACTIONS, QUAL, ReviewStore
from dentexmodel.reporting.final_result import final_result, top_class
from dentexmodel.storage import jload


class ReviewService:
    def __init__(self, ctx, images):
        self.ctx, self.images = ctx, images
        self.store = ReviewStore(ctx.db)

    def queue(self, limit: int = 50) -> dict:
        """Regions that need a human look, most informative image first (image-level combined uncertainty, then number of flags).

        Only images that have a stored full analysis appear; a region disappears from the queue once it has a current review."""
        reviewed = {(r["image_id"], r["region_id"]) for r in self.store.list(current_only=True, limit=100000) if r["region_id"]}
        latest: dict = {}
        for row in self.ctx.db.list("analyses", where="kind='full'", limit=5000):      # newest first
            latest.setdefault(row["image_id"], row)
        items = []
        for iid, row in latest.items():
            a = jload(row["result_json"])
            comb = (a.get("uncertainty") or {}).get("combined_score")
            regs = [r for r in a.get("regions", []) if r["review_required"] and (iid, r["region_id"]) not in reviewed]
            if regs:
                items.append({"image_id": iid, "analysis_id": row["id"], "combined_score": comb, "n_regions_to_review": len(regs),
                              "n_regions": len(a.get("regions", [])), "created": row["created"],
                              "final_result": final_result(a) or a.get("final_result"),
                              "regions": [{"region_id": r["region_id"], "region_no": r["region_no"], "fdi": r["fdi"], "flags": r["flags"],
                                           "candidate": (top_class(r["candidate_class"]) or {}).get("label"), "status": (r["candidate_class"] or {}).get("status")} for r in regs]})
        items.sort(key=lambda x: (-(x["combined_score"] if x["combined_score"] is not None else -1), -x["n_regions_to_review"]))
        return {"items": items[:limit], "total": len(items),
                "ordering": "image-level combined uncertainty (descending; images without a computed score last), then number of flagged regions",
                "note": "Only images with a stored full analysis are listed. Reviewer identity is self-declared."}

    def meta(self) -> dict:
        return {"actions": list(ACTIONS), "reviewer_qualification": QUAL}
