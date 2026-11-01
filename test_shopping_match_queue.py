"""Alexa review queue tests: no remote writes or silent catalog selection."""
import tempfile
import unittest
from pathlib import Path

from shopping_match_queue import refresh, pending, choose, resolved_choices, scoped_path


class AlexaMatchQueueTests(unittest.TestCase):
    def test_queue_is_scoped_to_alexa_list(self):
        base = Path("/config/alexa-match-queue.sqlite3")
        first = scoped_path(base, "todo.alexa_shopping")
        second = scoped_path(base, "todo.another_list")
        self.assertNotEqual(first, second)
        self.assertEqual(first, scoped_path(base, "todo.alexa_shopping"))
        self.assertEqual(scoped_path(base, ""), base)

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

    def test_catalog_refresh_discovers_new_product_for_an_unmatched_note(self):
        from shopping_match_queue import refresh_catalog
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'queue.sqlite3'
            refresh_catalog(path, [], ['Crema Nivea'])
            self.assertEqual(pending(path)[0]['candidates'], [])
            refresh_catalog(path, [{'id': 9, 'name': 'Crema Nivea'}], ['Crema Nivea'])
            row = pending(path)[0]
            self.assertEqual([p['id'] for p in row['candidates']], [9])
            self.assertTrue(row['requires_product'])
            self.assertIsNone(row['selected_product_id'])

    def test_catalog_changes_update_candidates_without_replacing_saved_choices(self):
        from shopping_match_queue import refresh_catalog, attach_entry
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'queue.sqlite3'
            original = [{'id': 1, 'name': 'Arroz redondo'}, {'id': 2, 'name': 'Arroz basmati'}]
            refresh(path, ['Arroz'], original)
            choose(path, 'arroz', 2)
            attach_entry(path, 'arroz', 70)
            changed = [{'id': 1, 'name': 'Arroz integral'}, {'id': 3, 'name': 'Arroz largo'}]
            refresh_catalog(path, changed)
            row = pending(path)[0]
            self.assertEqual({p['id'] for p in row['candidates']}, {1, 3})
            self.assertEqual(row['selected_product_id'], 2)
            self.assertEqual(row['shopping_entry_id'], 70)
            self.assertEqual(row['generation'], 1)
            self.assertTrue(row['selection_stale'])
            self.assertTrue(row['dismissed'])
            refresh(path, ['Arroz'], [{'id': 4, 'name': 'Arroz'}])
            self.assertEqual(pending(path)[0]['selected_product_id'], 2)
            self.assertTrue(pending(path)[0]['selection_stale'])
            self.assertEqual(resolved_choices(path, ['Arroz'], [{'id': 4, 'name': 'Arroz'}]), {})
            refresh(path, ['Arroz'], [])
            self.assertEqual(pending(path)[0]['selected_product_id'], 2)

    def test_catalog_refresh_never_reopens_removals_or_keep_original_decisions(self):
        from shopping_match_queue import refresh_catalog, keep_original, stage_removal
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'queue.sqlite3'
            products = [{'id': 1, 'name': 'Arroz redondo'}]
            refresh(path, ['Arroz'], products)
            keep_original(path, 'arroz')
            refresh_catalog(path, products + [{'id': 2, 'name': 'Arroz largo'}])
            self.assertTrue(pending(path)[0]['dismissed'])
            stage_removal(path, 'arroz', {'id': 4, 'note': 'Arroz'})
            before = pending(path)[0]
            refresh_catalog(path, [], ['Arroz'])
            self.assertEqual(pending(path)[0], before)

    def test_exact_catalog_items_skip_review_and_unmatched_alexa_items_allow_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            refresh(path, ["Leche entera", "Jabón desconocido"],
                    [{"id": 1, "name": "Leche entera"}])
            self.assertEqual([row["name"] for row in pending(path)], ["Jabón desconocido"])
            self.assertEqual(pending(path)[0]["candidates"], [])

    def test_changed_candidates_keep_stale_choice_but_never_resolve_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            products = [{"id": 1, "name": "Arroz redondo"},
                        {"id": 2, "name": "Arroz basmati"}]
            refresh(path, ["Arroz"], products)
            choose(path, "arroz", 2)
            refresh(path, ["Arroz"], products[:1])
            self.assertEqual(pending(path)[0]["selected_product_id"], 2)
            self.assertTrue(pending(path)[0]["selection_stale"])
            self.assertEqual(resolved_choices(path, ["Arroz"], products[:1]), {})


if __name__ == "__main__":
    unittest.main()

class KeepOriginalTests(unittest.TestCase):
    def test_keep_original_survives_refresh_without_recreating_suggestion(self):
        from shopping_match_queue import keep_original
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'queue.sqlite3'
            products = [{"id": 1, "name": "Arroz redondo"}, {"id": 2, "name": "Arroz basmati"}]
            refresh(path, ['Arroz'], products)
            keep_original(path, 'arroz')
            refresh(path, ['Arroz'], products)
            row = pending(path)[0]
            self.assertTrue(row['dismissed'])
            self.assertIsNone(row['selected_product_id'])
            self.assertEqual(resolved_choices(path, ['Arroz'], products), {})
            choose(path, 'arroz', 2)
            self.assertFalse(pending(path)[0]['dismissed'])

    def test_additive_queue_migration_preserves_old_choices(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.sqlite3'
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE pending_matches (normalized_name TEXT PRIMARY KEY, original_name TEXT, candidates_json TEXT, selected_product_id INTEGER, active INTEGER)')
                db.execute('INSERT INTO pending_matches VALUES (?,?,?,?,?)', ('arroz', 'Arroz', '[{"id":2,"name":"Arroz basmati"}]', 2, 1))
            row = pending(path)[0]
            self.assertFalse(row['dismissed'])
            self.assertEqual(row['selected_product_id'], 2)
