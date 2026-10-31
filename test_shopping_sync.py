import unittest

from shopping_sync import normalize, plan, snapshot


class ShoppingSyncTests(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(normalize("  CAFÉ   con  Leche "), "cafe con leche")

    def test_first_run_merges_without_deleting(self):
        p = plan(["Leche"], ["Pan"])
        self.assertEqual(p["add_alexa"], ["Pan"])
        self.assertEqual(p["add_grocy"], ["Leche"])
        self.assertEqual(p["remove_alexa"], [])
        self.assertEqual(p["remove_grocy"], [])

    def test_no_loop_after_success(self):
        p = plan(["Pan"], ["pan"], ["pan"])
        self.assertFalse(any(p[k] for k in ("add_alexa", "add_grocy", "remove_alexa", "remove_grocy")))

    def test_deletion_from_alexa(self):
        p = plan([], ["Pan"], ["pan"])
        self.assertEqual(p["remove_grocy"], ["Pan"])
        self.assertEqual(p["next_baseline"], [])

    def test_deletion_from_grocy(self):
        p = plan(["Pan"], [], ["pan"])
        self.assertEqual(p["remove_alexa"], ["Pan"])

    def test_new_item_not_deleted(self):
        p = plan(["Leche"], [], [])
        self.assertEqual(p["add_grocy"], ["Leche"])

    def test_reject_ambiguous_duplicate(self):
        with self.assertRaises(ValueError):
            snapshot(["Café", "cafe"])


if __name__ == "__main__":
    unittest.main()
