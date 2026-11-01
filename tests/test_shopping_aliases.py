"""Regression coverage for persistent many-to-one Alexa aliases."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ha_grocy_ticket_importer"))
from shopping_aliases import set_alias, remove_alias, list_aliases, choices


class AlexaAliasRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "aliases.sqlite3"

    def tearDown(self):
        self.tmp.cleanup()

    def test_multiple_aliases_for_same_product(self):
        set_alias(self.path, "Leche", 42)
        set_alias(self.path, "Leche normal", 42)
        self.assertEqual({a["product_id"] for a in list_aliases(self.path)}, {42})
        self.assertEqual(len(list_aliases(self.path)), 2)

    def test_alias_cannot_point_to_two_products(self):
        set_alias(self.path, "Leche", 42)
        with self.assertRaises(ValueError):
            set_alias(self.path, " LECHE ", 43)
        self.assertEqual(len(list_aliases(self.path)), 1)

    def test_remove_one_alias_preserves_other_aliases(self):
        set_alias(self.path, "Leche", 42)
        set_alias(self.path, "Leche normal", 42)
        remove_alias(self.path, "Leche")
        self.assertEqual([a["name"] for a in list_aliases(self.path)], ["Leche normal"])

    def test_persistence_across_connections(self):
        set_alias(self.path, "Leche", 42)
        self.assertEqual(choices(self.path, [{"id": 42}])["leche"]["product_id"], 42)

    def test_missing_catalog_product_is_rejected(self):
        set_alias(self.path, "Leche", 42)
        with self.assertRaises(ValueError):
            choices(self.path, [{"id": 43}])


if __name__ == "__main__":
    unittest.main()
