"""Network-free regression tests for identity-aware shopping reconciliation."""
import unittest

from shopping_identity_sync import IdentityConflict, identities, plan_identity


PRODUCTS = [
    {"id": 1, "name": "Arroz redondo", "qu_id_stock": 1},
    {"id": 2, "name": "Arroz basmati", "qu_id_stock": 1},
    {"id": 3, "name": "Leche entera", "qu_id_stock": 1},
]


def entry(pid, entry_id=1, name=None, amount=2):
    return (name or ("Arroz basmati" if pid == 2 else "Leche entera"),
            {"id": entry_id, "product_id": pid, "amount": amount, "note": ""})


class IdentityPlannerTests(unittest.TestCase):
    def test_explicit_choice_matches_product_without_renaming_alexa(self):
        p = plan_identity(["Arroz"], [entry(2)], PRODUCTS, None,
                          {"arroz": {"product_id": 2, "original_name": "Arroz"}})
        self.assertEqual(p["next_baseline"], ["p:2"])
        self.assertTrue(all(not p[action] for action in
                            ("add_alexa", "add_grocy", "remove_alexa", "remove_grocy")))

    def test_choice_adds_canonical_product_not_free_text(self):
        p = plan_identity(["Arroz"], [], PRODUCTS, None,
                          {"arroz": {"product_id": 2}})
        self.assertEqual(p["add_grocy"][0]["product_id"], 2)
        self.assertEqual(p["add_grocy"][0]["name"], "Arroz")

    def test_free_text_is_not_forced_into_catalog(self):
        p = plan_identity(["Platanos verdes"], [], PRODUCTS)
        self.assertEqual(p["add_grocy"][0]["key"], "n:platanos verdes")
        self.assertIsNone(p["add_grocy"][0]["product_id"])

    def test_ambiguous_unapproved_name_remains_note(self):
        p = plan_identity(["Arroz"], [], PRODUCTS)
        self.assertEqual(p["add_grocy"][0]["key"], "n:arroz")

    def test_existing_note_conflict_blocks_conversion(self):
        note = ("Arroz", {"id": 10, "product_id": None,
                          "note": "Arroz", "amount": 3})
        with self.assertRaisesRegex(IdentityConflict, "note conflicts"):
            plan_identity(["Arroz"], [note], PRODUCTS, None,
                          {"arroz": {"product_id": 2}})

    def test_canonical_product_name_note_conflict(self):
        note = ("Arroz basmati", {"id": 10, "product_id": None,
                                  "note": "Arroz basmati", "amount": 3})
        with self.assertRaisesRegex(IdentityConflict, "canonical product"):
            plan_identity(["Arroz"], [note], PRODUCTS, None,
                          {"arroz": {"product_id": 2}})

    def test_duplicate_product_identity_fails_closed(self):
        with self.assertRaisesRegex(IdentityConflict, "same identity"):
            plan_identity(["Arroz", "Arroz basmati"], [], PRODUCTS, None,
                          {"arroz": {"product_id": 2}})

    def test_missing_selected_product_fails_closed(self):
        with self.assertRaisesRegex(IdentityConflict, "no longer"):
            plan_identity(["Arroz"], [], PRODUCTS, None,
                          {"arroz": {"product_id": 999}})

    def test_unrelated_manual_selection_is_rejected(self):
        with self.assertRaisesRegex(IdentityConflict, "valid candidate"):
            plan_identity(["Arroz"], [], PRODUCTS, None,
                          {"arroz": {"product_id": 3}})

    def test_exact_name_cannot_be_overridden_by_manual_choice(self):
        with self.assertRaisesRegex(IdentityConflict, "valid candidate"):
            plan_identity(["Leche entera"], [], PRODUCTS, None,
                          {"leche entera": {"product_id": 2}})

    def test_first_sync_preserves_existing_product_and_quantity(self):
        p = plan_identity([], [entry(2, amount=5)], PRODUCTS)
        self.assertEqual(p["add_alexa"][0]["name"], "Arroz basmati")
        self.assertEqual(p["remove_grocy"], [])
        self.assertEqual(p["next_baseline"], ["p:2"])

    def test_deletion_removes_exact_grocy_entry_id(self):
        p = plan_identity([], [entry(2, entry_id=77, amount=5)], PRODUCTS,
                          baseline=["p:2"])
        self.assertEqual(p["remove_grocy"][0]["entry_id"], 77)
        self.assertEqual(p["remove_grocy"][0]["amount"], 5)
        self.assertEqual(p["next_baseline"], [])

    def test_grocy_deletion_removes_original_alexa_summary(self):
        p = plan_identity(["Arroz"], [], PRODUCTS, baseline=["p:2"],
                          choices={"arroz": {"product_id": 2}})
        self.assertEqual(p["remove_alexa"][0]["name"], "Arroz")

    def test_duplicate_display_name_product_and_note_blocks_sync(self):
        note = ("Arroz basmati", {"id": 20, "product_id": None,
                                  "note": "Arroz basmati", "amount": 1})
        with self.assertRaisesRegex(IdentityConflict, "normalized Grocy"):
            plan_identity([], [entry(2, 1), note], PRODUCTS)

    def test_duplicate_grocy_product_entry_is_not_silently_removed(self):
        with self.assertRaisesRegex(IdentityConflict, "Duplicate Grocy"):
            identities([], [entry(2, 1), entry(2, 2)], PRODUCTS)


if __name__ == "__main__":
    unittest.main()
