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
             patch("shopping_sync_adapters.grocy") as grocy:
            with self.assertRaises(IdentityConflict):
                add_grocy_identity({"name": "Arroz", "product_id": 2})
        grocy.assert_not_called()

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
