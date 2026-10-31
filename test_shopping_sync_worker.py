"""Worker integration tests without network access."""
import unittest
from unittest.mock import patch

import shopping_sync_worker as worker


class ShoppingWorkerTests(unittest.TestCase):
    def test_ambiguity_queue_refreshed_before_dry_run_reconcile(self):
        events = []
        products = [{"id": 1, "name": "Arroz basmati"}]
        result = {"add_alexa": [], "add_grocy": [], "remove_alexa": [],
                  "remove_grocy": [], "next_baseline": []}
        def record_queue(path, names, catalog):
            events.append("queue")
            self.assertEqual(names, ["Arroz"])
            self.assertEqual(catalog, products)
        def record_reconcile(*args, **kwargs):
            events.append("reconcile")
            self.assertTrue(kwargs["dry_run"])
            return result
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_shopping_names", return_value=[]), \
             patch.object(worker, "grocy", return_value=products), \
             patch.object(worker, "refresh_matches", side_effect=record_queue), \
             patch.object(worker, "load_baseline", return_value=None), \
             patch.object(worker, "reconcile", side_effect=record_reconcile), \
             patch.object(worker, "save_baseline") as save:
            self.assertEqual(worker.run_once(dry_run=True), result)
        self.assertEqual(events, ["queue", "reconcile"])
        save.assert_not_called()

    def test_failed_catalog_audit_prevents_sync_mutations(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_shopping_names", return_value=[]), \
             patch.object(worker, "grocy", return_value=None), \
             patch.object(worker, "reconcile") as reconcile:
            with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
                worker.run_once(dry_run=False)
        reconcile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
