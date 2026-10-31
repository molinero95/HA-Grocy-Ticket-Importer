"""Read-only audit regression tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import catalog_audit
import variant_catalog


class CatalogAuditTests(unittest.TestCase):
    def test_exports_stock_units_barcodes_shopping_without_writes(self):
        fixtures = {
            "objects/products": [{"id": 42, "name": "Leche entera", "qu_id_stock": 2,
                                   "qu_id_purchase": 3, "qu_factor_purchase_to_stock": 6}],
            "objects/product_barcodes": [{"product_id": 42, "barcode": "8480000000001"}],
            "stock": [{"product_id": 42, "amount": 12}],
            "objects/shopping_list": [{"id": 9, "product_id": 42, "shopping_list_id": 1},
                                      {"id": 10, "product_id": 0, "note": "Pan"}],
            "objects/quantity_units": [{"id": 2, "name": "Piece"}, {"id": 3, "name": "Pack"}],
        }
        calls = []
        def read(method, path):
            calls.append((method, path))
            self.assertEqual(method, "GET")
            return fixtures[path]
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(variant_catalog, "CATALOG_DB", Path(tmp) / "catalog.sqlite3"), \
             patch.object(catalog_audit, "CATALOG_DB", Path(tmp) / "catalog.sqlite3"), \
             patch.object(catalog_audit, "grocy", side_effect=read):
            result = catalog_audit.build_snapshot()
        self.assertEqual(len(calls), 5)
        self.assertEqual(result["products"][0]["stock_amount"], "12")
        self.assertEqual(result["products"][0]["purchase_to_stock_factor"], 6)
        self.assertEqual(result["products"][0]["shopping_entry_ids"], [9])
        self.assertEqual(result["shopping_notes"], [{"id": 10, "note": "Pan"}])
        self.assertTrue(result["requires_explicit_approval_for_merges"])

    def test_rejects_incomplete_remote_response(self):
        with patch.object(catalog_audit, "grocy", return_value=None):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                catalog_audit.build_snapshot()


if __name__ == "__main__":
    unittest.main()
