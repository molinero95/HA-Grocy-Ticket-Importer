"""Worker integration tests without network access."""
import unittest
from unittest.mock import patch

import shopping_sync_worker as worker
from shopping_identity_sync import IdentityConflict


class ShoppingWorkerTests(unittest.TestCase):
    def test_ambiguity_queue_precedes_identity_dry_run(self):
        events = []
        products = [{"id": 1, "name": "Arroz basmati"}]
        result = {"add_alexa": [], "add_grocy": [], "remove_alexa": [],
                  "remove_grocy": [], "next_baseline": [], "next_bindings": {}}
        def record_queue(path, names, catalog):
            events.append("queue")
            self.assertEqual(names, ["Arroz"])
            self.assertEqual(catalog, products)
        def record_reconcile(*args, **kwargs):
            events.append("reconcile")
            self.assertTrue(kwargs["dry_run"])
            return result
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=products), \
             patch.object(worker, "refresh_matches", side_effect=record_queue), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", side_effect=record_reconcile), \
             patch.object(worker, "save_identity_state") as save:
            self.assertEqual(worker.run_once(dry_run=True), result)
        self.assertEqual(events, ["queue", "reconcile"])
        save.assert_not_called()

    def test_failed_catalog_audit_prevents_sync_mutations(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=None), \
             patch.object(worker, "reconcile_identity") as reconcile:
            with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
                worker.run_once(dry_run=False)
        reconcile.assert_not_called()

    def test_stale_manual_selection_blocks_all_writes(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=[{"id": 1, "name": "Arroz basmati"}]), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[
                 {"key": "arroz", "selected_product_id": 2}]), \
             patch.object(worker, "reconcile_identity") as reconcile:
            with self.assertRaisesRegex(IdentityConflict, "renewed review"):
                worker.run_once(dry_run=False)
        reconcile.assert_not_called()

    def test_verified_run_saves_v2_checkpoint(self):
        products = [{"id": 2, "name": "Arroz basmati"}]
        grocy_rows = [("Arroz basmati", {"id": 7, "product_id": 2, "amount": 1})]
        result = {"add_alexa": [], "add_grocy": [], "remove_alexa": [],
                  "remove_grocy": [], "next_baseline": ["p:2"], "next_bindings": {"arroz": 2}}
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=grocy_rows), \
             patch.object(worker, "grocy", return_value=products), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={"arroz": {"product_id": 2}}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", return_value=result), \
             patch.object(worker, "save_identity_state") as save:
            self.assertEqual(worker.run_once(dry_run=False), result)
        save.assert_called_once_with(worker.STATE_V2, ["p:2"], {"arroz": 2})

    def test_partial_failure_never_advances_checkpoint(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=[{"id": 2, "name": "Arroz basmati"}]), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", side_effect=RuntimeError("write failed")), \
             patch.object(worker, "save_identity_state") as save:
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                worker.run_once(dry_run=False)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
