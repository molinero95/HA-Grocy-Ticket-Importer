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



class AlexaCatalogSuggestionTests(unittest.TestCase):
    def test_exact_match_is_safe(self):
        from shopping_sync import suggest_catalog_matches
        decision, matches = suggest_catalog_matches("LECHE ENTERA", [{"id": 1, "name": "Leche entera"}])
        self.assertEqual(decision, "exact")
        self.assertEqual(matches[0]["id"], 1)

    def test_variant_mismatch_never_auto_matches(self):
        from shopping_sync import suggest_catalog_matches
        decision, matches = suggest_catalog_matches("leche entera", [{"id": 1, "name": "leche desnatada"}])
        self.assertEqual(decision, "unmatched")
        self.assertEqual(matches, [])

    def test_ambiguous_matches_require_review(self):
        from shopping_sync import suggest_catalog_matches
        decision, matches = suggest_catalog_matches("arroz", [
            {"id": 1, "name": "Arroz redondo"},
            {"id": 2, "name": "Arroz basmati"}])
        self.assertEqual(decision, "review")
        self.assertEqual(len(matches), 2)

    def test_unrelated_products_are_not_suggested(self):
        from shopping_sync import suggest_catalog_matches
        self.assertEqual(suggest_catalog_matches("leche", [{"id": 1, "name": "detergente"}]), ("unmatched", []))



class AlexaRiceCandidateTests(unittest.TestCase):
    def test_generic_rice_offers_all_rice_varieties(self):
        from shopping_sync import suggest_catalog_matches
        products = [{"id": 1, "name": "Arroz basmati"}, {"id": 2, "name": "Arroz integral"}]
        decision, candidates = suggest_catalog_matches("arroz", products)
        self.assertEqual(decision, "review")
        self.assertEqual({p["id"] for p in candidates}, {1, 2})

    def test_exact_generic_rice_still_requires_review_when_varieties_exist(self):
        from shopping_sync import suggest_catalog_matches
        products = [{"id": 1, "name": "Arroz"}, {"id": 2, "name": "Arroz integral"}]
        decision, candidates = suggest_catalog_matches("arroz", products)
        self.assertEqual(decision, "review")
        self.assertEqual({p["id"] for p in candidates}, {1, 2})
if __name__ == "__main__":
    unittest.main()
