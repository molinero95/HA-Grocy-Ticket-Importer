"""Regression tests for purchased Alexa aliases and identity reconciliation.

Run with: python -m unittest discover -s tests -p 'test_alexa_purchase_alias_regression.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_grocy_ticket_importer"))

from shopping_identity_sync import plan_identity, IdentityConflict


PRODUCTS = [{"id": 7, "name": "Leche entera"}]
CHOICE = {"leche": {"product_id": 7}}


class AlexaPurchaseAliasRegression(unittest.TestCase):
    def test_purchased_alias_is_removed_from_alexa(self):
        # The shopping row disappeared from Grocy after being marked done.
        plan = plan_identity(["Leche"], [], PRODUCTS, ["p:7"], CHOICE)
        self.assertEqual([r["name"] for r in plan["remove_alexa"]], ["Leche"])
        self.assertEqual(plan["add_grocy"], [])
        self.assertEqual(plan["next_baseline"], [])

    def test_first_sync_does_not_remove_uncheckpointed_alias(self):
        plan = plan_identity(["Leche"], [], PRODUCTS, None, CHOICE)
        self.assertEqual(plan["remove_alexa"], [])
        self.assertEqual(len(plan["add_grocy"]), 1)

    def test_different_alexa_name_does_not_recreate_purchased_product(self):
        plan = plan_identity(["Leche"], [], PRODUCTS, ["p:7"], CHOICE)
        self.assertFalse(plan["add_grocy"])

    def test_ambiguous_alias_without_choice_cannot_delete_another_product(self):
        plan = plan_identity(["Leche"], [], PRODUCTS, ["p:7"])
        self.assertEqual(plan["remove_grocy"], [])
        self.assertEqual(plan["remove_alexa"], [])
        self.assertEqual(len(plan["add_grocy"]), 1)


if __name__ == "__main__":
    unittest.main()
