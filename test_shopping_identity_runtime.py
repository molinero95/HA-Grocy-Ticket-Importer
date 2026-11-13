"""Identity checkpoint and remote-write safety tests (network-free)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shopping_identity_sync import IdentityConflict
from shopping_identity_runtime import (
    load_identity_state, save_identity_state, verify_bindings, reconcile_identity,
)
from shopping_sync_adapters import (
    add_grocy_identity, remove_grocy_identity, remove_alexa_identity,
    grocy_entries,
)

PRODUCTS = [{"id": 2, "name": "Arroz basmati", "qu_id_stock": 1}]


class IdentityRuntimeTests(unittest.TestCase):
    def test_atomic_v2_checkpoint_and_invalid_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "v2.json"
            self.assertIsNone(load_identity_state(path))
            save_identity_state(path, ["p:2", "p:2"], {"arroz": 2})
            self.assertEqual(load_identity_state(path),
                             {"keys": ["p:2"], "bindings": {"arroz": 2}})
            with self.assertRaises(IdentityConflict):
                save_identity_state(path, ["p:2"], {"Arroz": 2})
            self.assertEqual(load_identity_state(path)["bindings"], {"arroz": 2})
            path.write_text(json.dumps({"version": 1, "names": ["arroz"]}))
            with self.assertRaises(IdentityConflict):
                load_identity_state(path)

    def test_changed_product_binding_fails_closed(self):
        previous = {"keys": ["p:2"], "bindings": {"arroz": 2}}
        with self.assertRaisesRegex(IdentityConflict, "changed its product"):
            verify_bindings(["Arroz"], [], PRODUCTS, {}, previous)
        # Deleting the Alexa entry is not a rename or rebind.
        verify_bindings([], [("Arroz basmati", {"id": 7, "product_id": 2})],
                        PRODUCTS, {}, previous)

    def test_all_synonyms_are_checkpointed_and_rebinding_any_one_is_rejected(self):
        from shopping_identity_runtime import current_bindings
        choices = {"arroz": {"product_id": 2}}
        a, _ = verify_bindings(["Arroz", "Arroz basmati"], [], PRODUCTS, choices, None)
        self.assertEqual(current_bindings(a), {"arroz": 2, "arroz basmati": 2})
        previous = {"keys": ["p:2"], "bindings": current_bindings(a)}
        products = [*PRODUCTS, {"id": 3, "name": "Arroz integral"}]
        with self.assertRaisesRegex(IdentityConflict, "changed its product"):
            verify_bindings(["Arroz basmati", "Arroz"], [], products,
                            {"arroz": {"product_id": 3, "trusted_manual": True}}, previous)

    def test_full_24_item_snapshot_is_imported_before_failed_alexa_write(self):
        names = [f"Unmatched item {i}" for i in range(24)]
        rows = [("Arroz basmati", {"id": 99, "product_id": 2, "amount": 5})]
        imported = []
        def fail(row):
            self.assertEqual(len(imported), 24)
            raise RuntimeError("Amazon unavailable")
        with self.assertRaisesRegex(RuntimeError, "Amazon unavailable"):
            reconcile_identity(names, rows, PRODUCTS, None, {}, dry_run=False,
                               add_grocy=imported.append, add_alexa=fail)
        self.assertEqual({row["name"] for row in imported}, set(names))
        materialized = rows + [(row["name"], {"id": i+100, "product_id": None,
                                  "note": row["name"], "amount": 1}) for i, row in enumerate(imported)]
        retry = reconcile_identity(names, materialized, PRODUCTS, None, {}, dry_run=True)
        self.assertEqual(retry["add_grocy"], [])
        self.assertEqual(len(retry["add_alexa"]), 1)

    def test_missing_callback_aborts_before_any_write(self):
        with self.assertRaisesRegex(IdentityConflict, "Missing callback"):
            reconcile_identity(["Arroz"], [], PRODUCTS, None,
                               {"arroz": {"product_id": 2}}, dry_run=False)

    def test_no_checkpoint_after_partial_write_and_retry_is_idempotent(self):
        calls = []
        with self.assertRaisesRegex(RuntimeError, "network"):
            reconcile_identity(["Arroz"], [], PRODUCTS, None,
                               {"arroz": {"product_id": 2}}, dry_run=False,
                               add_grocy=lambda row: (calls.append(row), (_ for _ in ()).throw(RuntimeError("network"))))
        self.assertEqual(len(calls), 1)
        # A retry sees the already-added product and does not add it again.
        result = reconcile_identity(
            ["Arroz"], [("Arroz basmati", {"id": 10, "product_id": 2, "amount": 1})],
            PRODUCTS, None, {"arroz": {"product_id": 2}}, dry_run=True)
        self.assertEqual(result["add_grocy"], [])
        self.assertEqual(result["next_baseline"], ["p:2"])


class IdentityAdapterTests(unittest.TestCase):
    def test_alexa_snapshot_filters_all_completed_and_retains_all_24_pending(self):
        from shopping_sync_adapters import alexa_items
        items = [{'summary': f'Item {i}', 'status': 'needs_action', 'uid': str(i)} for i in range(24)]
        completed = [{'summary': 'Historical', 'status': 'completed', 'uid': 'old'}] * 76
        with patch('shopping_sync_adapters.ALEXA_LIST', 'todo.test'), \
             patch('shopping_sync_adapters.ha_service', return_value={'service_response': {'todo.test': {'items': items + completed}}}) as service:
            self.assertEqual(alexa_items(), items)
            service.assert_called_once_with('get_items', {'entity_id': 'todo.test'})

    def test_native_completed_cleanup_targets_configured_list_and_verifies(self):
        from shopping_sync_adapters import clear_completed_alexa
        with patch('shopping_sync_adapters.ALEXA_LIST', 'todo.test'), \
             patch('shopping_sync_adapters.ha_service', return_value={'todo.test': {'items': [{'summary': 'Keep', 'status': 'needs_action'}]}}) as service:
            self.assertEqual(clear_completed_alexa(), {'ok': True})
            self.assertEqual([c.args for c in service.call_args_list], [
                ('remove_completed_items', {'entity_id': 'todo.test'}), ('get_items', {'entity_id': 'todo.test'})])
        with patch('shopping_sync_adapters.ALEXA_LIST', 'todo.test'), \
             patch('shopping_sync_adapters.ha_service', return_value={'todo.test': {'items': [{'summary': 'Old', 'status': 'completed'}]}}):
            with self.assertRaisesRegex(RuntimeError, 'could not be verified'):
                clear_completed_alexa()

    def test_grocy_active_entries_include_string_zero_completion(self):
        entries = [
            {"id": 11, "product_id": 2, "shopping_list_id": 1, "done": "0"},
            {"id": 12, "product_id": 2, "shopping_list_id": 1, "done": False},
            {"id": 13, "product_id": 2, "shopping_list_id": 1, "done": "false"},
            {"id": 14, "product_id": 2, "shopping_list_id": 1, "done": "1"},
            {"id": 15, "product_id": 2, "shopping_list_id": 1, "done": True},
            {"id": 16, "product_id": 2, "shopping_list_id": 2, "done": "0"},
        ]
        with patch("shopping_sync_adapters.grocy", side_effect=[PRODUCTS, entries]) as remote:
            active = grocy_entries()
        self.assertEqual([row[1]["id"] for row in active], [11, 12, 13])
        self.assertEqual(remote.call_count, 2)

    def test_invalid_grocy_completion_flag_fails_closed(self):
        entries = [{"id": 11, "product_id": 2, "done": "unknown"}]
        with patch("shopping_sync_adapters.grocy", side_effect=[PRODUCTS, entries]) as remote:
            with self.assertRaisesRegex(ValueError, "completion flag"):
                grocy_entries()
        self.assertEqual(remote.call_count, 2)

    def test_add_selected_product_uses_id_not_alexa_text(self):
        with patch("shopping_sync_adapters.grocy_entries", return_value=[]), \
             patch("shopping_sync_adapters.grocy", side_effect=[
                 PRODUCTS, {"ok": True}]) as grocy:
            add_grocy_identity({"name": "Arroz", "product_id": 2})
        self.assertEqual(grocy.call_args_list[-1].args[1],
                         "stock/shoppinglist/add-product")
        self.assertEqual(grocy.call_args_list[-1].args[2]["product_id"], 2)

    def test_concurrent_note_blocks_selected_product_add(self):
        note = ("Arroz", {"id": 8, "product_id": None, "note": "Arroz", "amount": 1})
        with patch("shopping_sync_adapters.grocy_entries", return_value=[note]), \
             patch("shopping_sync_adapters.grocy", return_value=PRODUCTS) as grocy:
            with self.assertRaises(IdentityConflict):
                add_grocy_identity({"name": "Arroz", "product_id": 2})
        grocy.assert_called_once_with("GET", "objects/products")

    def test_concurrent_canonical_name_note_blocks_product_add(self):
        note = ("Arroz basmati", {"id": 8, "product_id": None,
                                  "note": "Arroz basmati", "amount": 1})
        with patch("shopping_sync_adapters.grocy_entries", return_value=[note]), \
             patch("shopping_sync_adapters.grocy", return_value=PRODUCTS) as grocy:
            with self.assertRaises(IdentityConflict):
                add_grocy_identity({"name": "Arroz", "product_id": 2})
        grocy.assert_called_once_with("GET", "objects/products")

    def test_new_catalog_match_blocks_free_text_note_creation(self):
        with patch("shopping_sync_adapters.grocy_entries", return_value=[]), \
             patch("shopping_sync_adapters.grocy", return_value=PRODUCTS) as grocy:
            with self.assertRaisesRegex(IdentityConflict, "catalog changed"):
                add_grocy_identity({"name": "Arroz basmati", "product_id": None})
        grocy.assert_called_once_with("GET", "objects/products")

    def test_changed_quantity_prevents_deletion(self):
        item = ("Arroz basmati", {"id": 9, "product_id": 2, "note": "", "amount": 3})
        with patch("shopping_sync_adapters.grocy_entries", return_value=[item]), \
             patch("shopping_sync_adapters.grocy") as grocy:
            with self.assertRaisesRegex(IdentityConflict, "changed since planning"):
                remove_grocy_identity({"entry_id": 9, "product_id": 2,
                                       "note": "", "amount": 2})
        grocy.assert_not_called()

    def test_exact_entry_id_removed_when_unchanged(self):
        item = ("Arroz basmati", {"id": 9, "product_id": 2, "note": "", "amount": 3})
        with patch("shopping_sync_adapters.grocy_entries", return_value=[item]), \
             patch("shopping_sync_adapters.grocy") as grocy:
            remove_grocy_identity({"entry_id": 9, "product_id": 2,
                                   "note": "", "amount": 3})
        grocy.assert_called_once_with("DELETE", "objects/shopping_list/9")

    def test_duplicate_alexa_names_never_removed(self):
        items = [{"summary": "Arroz", "uid": "1"},
                 {"summary": "ARROZ", "uid": "2"}]
        with patch("shopping_sync_adapters.alexa_items", return_value=items), \
             patch("shopping_sync_adapters.ha_service") as service:
            with self.assertRaisesRegex(IdentityConflict, "Duplicate Alexa"):
                remove_alexa_identity({"name": "Arroz"})
        service.assert_not_called()


if __name__ == "__main__":
    unittest.main()
