"""Network-free identity planning tests."""
import unittest

from shopping_sync_identity import IdentityConflict, preview_identity


class IdentityPreviewTests(unittest.TestCase):
    def setUp(self):
        self.products = [
            {"id": 1, "name": "Leche entera"},
            {"id": 2, "name": "Arroz basmati"},
            {"id": 3, "name": "Arroz redondo"},
        ]

    def test_exact_review_and_free_text_are_kept_separate(self):
        result = preview_identity(
            ["Leche entera", "Arroz", "Nota sin catálogo"], self.products)
        self.assertEqual(result["exact"]["leche entera"]["product_id"], 1)
        self.assertIn("arroz", result["pending"])
        self.assertEqual(result["notes"], ["Nota sin catálogo"])

    def test_manual_selection_retains_original_name(self):
        result = preview_identity(["Arroz"], self.products,
                                  {"arroz": {"product_id": 2}})
        self.assertEqual(result["selected"]["arroz"]["canonical_name"], "Arroz basmati")
        self.assertEqual(result["selected"]["arroz"]["original_name"], "Arroz")

    def test_stale_manual_choice_is_rejected(self):
        with self.assertRaises(IdentityConflict):
            preview_identity(["Arroz"], self.products,
                             {"arroz": {"product_id": 999}})

    def test_duplicate_normalized_names_rejected(self):
        with self.assertRaises(IdentityConflict):
            preview_identity(["Arroz", " ARROZ "], self.products)

    def test_two_aliases_cannot_claim_same_product(self):
        with self.assertRaises(IdentityConflict):
            preview_identity(["Arroz", "Arroz basmati"], self.products,
                             {"arroz": {"product_id": 2}})


if __name__ == "__main__":
    unittest.main()
