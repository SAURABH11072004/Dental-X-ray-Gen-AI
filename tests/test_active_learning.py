import unittest

import numpy as np

import helpers  # noqa: F401
from dentexmodel.active_learning import ALConfig, ActiveLearningConfigError, select_candidates
from dentexmodel.data.splits import assert_not_test
from dentexmodel.errors import LeakageError


def pool(n=30, seed=0, with_emb=True):
    rng = np.random.default_rng(seed)
    return [{"image_id": f"i{k:02d}", "entropy": float(rng.random()), "disagreement": float(rng.random()),
             "mask_instability": float(rng.random()),
             "embedding": rng.normal(size=8).tolist() if with_emb else None} for k in range(n)]


class SelectionTests(unittest.TestCase):
    def test_empty_pool(self):
        r = select_candidates([], ALConfig(strategy="entropy", budget=5))
        self.assertEqual(r.selected, [])
        self.assertTrue(r.notes)

    def test_budget_limits(self):
        c = pool(10)
        self.assertEqual(len(select_candidates(c, ALConfig(strategy="entropy", budget=3)).selected), 3)
        r = select_candidates(c, ALConfig(strategy="entropy", budget=50))
        self.assertEqual(len(r.selected), 10)
        self.assertTrue(any("exceeds pool" in n for n in r.notes))
        self.assertEqual(select_candidates(c, ALConfig(strategy="random", budget=0)).selected, [])

    def test_entropy_ranking_and_reason(self):
        c = pool(20)
        r = select_candidates(c, ALConfig(strategy="entropy", budget=5))
        scores = [s.score for s in r.selected]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(r.selected[0].image_id, max(c, key=lambda x: x["entropy"])["image_id"])
        self.assertIn("entropy=", r.selected[0].reason)

    def test_missing_signals_are_skipped_not_zero(self):
        c = pool(6)
        c[0]["entropy"] = None
        c[1].pop("entropy")
        r = select_candidates(c, ALConfig(strategy="entropy", budget=6))
        self.assertEqual(len(r.selected), 4)
        self.assertEqual({s["image_id"] for s in r.skipped}, {"i00", "i01"})
        none = [{"image_id": "x", "entropy": None}]
        r2 = select_candidates(none, ALConfig(strategy="entropy", budget=1))
        self.assertEqual(r2.selected, [])
        self.assertTrue(r2.notes)

    def test_invalid_config(self):
        for kw in ({"strategy": "bogus"}, {"budget": -1}, {"batch_size": 0}, {"diversity_weight": 1.5},
                   {"weights": {"entropy": -1}}, {"weights": {"entropy": 0, "disagreement": 0, "mask_instability": 0}},
                   {"weights": {"nope": 1}}, {"budget": True}, {"seed": "a"}):
            with self.assertRaises(ActiveLearningConfigError, msg=str(kw)):
                select_candidates(pool(3), ALConfig(**kw))

    def test_duplicates_filtered(self):
        c = pool(5)
        c.append(dict(c[0]))
        r = select_candidates(c, ALConfig(strategy="entropy", budget=10))
        ids = [s.image_id for s in r.selected]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any("duplicate candidate" in s["reason"] for s in r.skipped))

    def test_excluded_ids(self):
        r = select_candidates(pool(5), ALConfig(strategy="random", budget=5), exclude_ids={"i00"})
        self.assertNotIn("i00", [s.image_id for s in r.selected])

    def test_random_deterministic_and_seed_sensitive(self):
        c = pool(40)
        a = [s.image_id for s in select_candidates(c, ALConfig(strategy="random", budget=8, seed=7)).selected]
        b = [s.image_id for s in select_candidates(list(reversed(c)), ALConfig(strategy="random", budget=8, seed=7)).selected]
        d = [s.image_id for s in select_candidates(c, ALConfig(strategy="random", budget=8, seed=8)).selected]
        self.assertEqual(a, b)  # independent of input order
        self.assertNotEqual(a, d)

    def test_combined_uses_available_signals(self):
        c = [{"image_id": "a", "entropy": 0.9}, {"image_id": "b", "entropy": 0.1, "mask_instability": 0.9},
             {"image_id": "c"}]
        r = select_candidates(c, ALConfig(strategy="combined", budget=3, diversity_weight=0))
        self.assertEqual([s.image_id for s in r.selected], ["a", "b"])
        self.assertEqual(r.skipped[0]["image_id"], "c")

    def test_diversity_avoids_near_duplicates(self):
        base = np.array([1.0, 0, 0, 0])
        c = [{"image_id": "a", "entropy": 0.95, "embedding": base.tolist()},
             {"image_id": "b", "entropy": 0.94, "embedding": (base + 1e-4).tolist()},   # near-identical to a
             {"image_id": "c", "entropy": 0.5, "embedding": [0, 1.0, 0, 0]}]
        r = select_candidates(c, ALConfig(strategy="combined", budget=2, diversity_weight=0.6))
        self.assertEqual([s.image_id for s in r.selected], ["a", "c"])
        r3 = select_candidates(c, ALConfig(strategy="combined", budget=3, diversity_weight=0.6))
        self.assertEqual([s.image_id for s in r3.selected], ["a", "c"])
        self.assertTrue(any(s["image_id"] == "b" and "near-duplicate" in s["reason"] for s in r3.skipped))

    def test_no_embeddings_notes_diversity_skipped(self):
        r = select_candidates(pool(5, with_emb=False), ALConfig(strategy="combined", budget=2, diversity_weight=0.5))
        self.assertTrue(any("diversity term skipped" in n for n in r.notes))

    def test_batches(self):
        r = select_candidates(pool(10), ALConfig(strategy="entropy", budget=5, batch_size=2))
        self.assertEqual([len(b) for b in r.batches], [2, 2, 1])

    def test_test_split_is_refused(self):
        c = pool(5)
        with self.assertRaises(LeakageError):
            select_candidates(c, ALConfig(strategy="random", budget=2), test_ids={"i01"})
        with self.assertRaises(LeakageError):
            assert_not_test(["i01", "zz"], {"i01": "test", "zz": "train"})
        assert_not_test(["zz"], {"i01": "test", "zz": "train"})


if __name__ == "__main__":
    unittest.main()
