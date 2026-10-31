"""Regression tests for safe generic variants; no live Grocy calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import variant_catalog


class VariantCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path_patch = patch.object(variant_catalog, "CATALOG_DB", Path(self.temp.name) / "variants.sqlite3")
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    @staticmethod
    def grocy_fixture(rows):
        def request(method, endpoint, payload=None):
            if method != "GET":
                raise AssertionError("No Grocy writes permitted in catalog audit")
            if endpoint == "objects/products/42":
                return {"id": 42, "name": "Leche entera"}
            if endpoint == "objects/product_barcodes":
                return rows
            raise AssertionError(endpoint)
        return request

    def test_two_variants_share_canonical_product_without_stock_writes(self):
        rows = [{"product_id": 42, "barcode": "8480000000001"},
                {"product_id": 42, "barcode": "8480000000002"}]
        with patch.object(variant_catalog, "grocy", side_effect=self.grocy_fixture(rows)), \
             patch.object(variant_catalog.barcode_stock, "associate_product_barcode") as associate:
            variant_catalog.save_variant(42, "8480000000001", "Leche Hacendado",
                                         supermarket="Mercadona", brand="Hacendado")
            variant_catalog.save_variant(42, "8480000000002", "Leche Carrefour",
                                         supermarket="Carrefour")
        associate.assert_not_called()
        variants = variant_catalog.variants_for_product(42)
        self.assertEqual(len(variants), 2)
        self.assertEqual({v["supermarket"] for v in variants}, {"Mercadona", "Carrefour"})

    def test_foreign_grocy_owner_rejected_without_local_write(self):
        rows = [{"product_id": 77, "barcode": "8480000000001"}]
        with patch.object(variant_catalog, "grocy", side_effect=self.grocy_fixture(rows)), \
             patch.object(variant_catalog.barcode_stock, "associate_product_barcode") as associate:
            with self.assertRaisesRegex(ValueError, "otro producto"):
                variant_catalog.save_variant(42, "8480000000001", "Leche")
        associate.assert_not_called()
        self.assertEqual(variant_catalog.variants_for_product(42), [])

    def test_new_barcode_attached_to_canonical_and_verified(self):
        rows = []
        def associate(pid, barcode):
            self.assertEqual(pid, 42)
            rows.append({"product_id": pid, "barcode": barcode})
        with patch.object(variant_catalog, "grocy", side_effect=self.grocy_fixture(rows)), \
             patch.object(variant_catalog.barcode_stock, "associate_product_barcode", side_effect=associate):
            variant_catalog.save_variant(42, "8480000000001", "Leche Hacendado")
        self.assertEqual(variant_catalog.variants_for_product(42)[0]["barcode"], "8480000000001")

    def test_no_local_metadata_if_grocy_cannot_verify_association(self):
        rows = []
        with patch.object(variant_catalog, "grocy", side_effect=self.grocy_fixture(rows)), \
             patch.object(variant_catalog.barcode_stock, "associate_product_barcode"):
            with self.assertRaisesRegex(ValueError, "verificar"):
                variant_catalog.save_variant(42, "8480000000001", "Leche Hacendado")
        self.assertEqual(variant_catalog.variants_for_product(42), [])

    def test_invalid_factor_rejected_before_grocy_call(self):
        with patch.object(variant_catalog, "grocy") as remote:
            for invalid in ("NaN", "Infinity", "0", "-1", "no"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    variant_catalog.save_variant(42, "8480000000001", "Leche", units_per_purchase=invalid)
        remote.assert_not_called()


if __name__ == "__main__":
    unittest.main()
