"""Alexa review queue tests: no remote writes or silent catalog selection."""
import tempfile
import unittest
from pathlib import Path

from shopping_match_queue import refresh, pending, choose, resolved_choices


class AlexaMatchQueueTests(unittest.TestCase):
    def test_ambiguous_item_retains_original_and_requires_manual_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            products = [{"id": 1, "name": "Arroz redondo"},
                        {"id": 2, "name": "Arroz basmati"}]
            refresh(path, ["  ARROZ  "], products)
            rows = pending(path)
            self.assertEqual(rows[0]["name"], "ARROZ")
            self.assertIsNone(rows[0]["selected_product_id"])
            self.assertEqual(len(rows[0]["candidates"]), 2)
            with self.assertRaises(ValueError):
                choose(path, "arroz", 99)
            choose(path, "Arroz", 2)
            self.assertEqual(pending(path)[0]["selected_product_id"], 2)
            refresh(path, ["Arroz"], products)
            self.assertEqual(pending(path)[0]["selected_product_id"], 2)
            refresh(path, [], products)
            self.assertEqual(pending(path), [])

    def test_resolved_choices_are_read_only_and_require_live_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            products = [{"id": 1, "name": "Arroz redondo"},
                        {"id": 2, "name": "Arroz basmati"}]
            refresh(path, ["Arroz"], products)
            choose(path, "arroz", 2)
            expected = {"arroz": {"product_id": 2, "product_name": "Arroz basmati",
                                  "original_name": "Arroz"}}
            self.assertEqual(resolved_choices(path, ["Arroz"], products), expected)
            self.assertEqual(resolved_choices(path, [], products), {})
            self.assertEqual(resolved_choices(path, ["Arroz"], products[:1]), {})
            self.assertEqual(pending(path)[0]["selected_product_id"], 2)

    def test_exact_and_unmatched_items_are_not_queued(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            refresh(path, ["Leche entera", "Jabón desconocido"],
                    [{"id": 1, "name": "Leche entera"}])
            self.assertEqual(pending(path), [])

    def test_changed_candidates_keep_stale_choice_but_never_resolve_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            products = [{"id": 1, "name": "Arroz redondo"},
                        {"id": 2, "name": "Arroz basmati"}]
            refresh(path, ["Arroz"], products)
            choose(path, "arroz", 1)
            refresh(path, ["Arroz"], products[:1])
            self.assertEqual(pending(path)[0]["selected_product_id"], 1)
            self.assertEqual(resolved_choices(path, ["Arroz"], products[:1]), {})


if __name__ == "__main__":
    unittest.main()
