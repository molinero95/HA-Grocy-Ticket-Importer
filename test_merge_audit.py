"""Contract tests for fail-closed, read-only merge auditing."""
import unittest
from unittest.mock import Mock

from merge_audit import audit_merge, COLLECTIONS


class MergeAuditTests(unittest.TestCase):
    def setUp(self):
        self.source = {"id": 1, "unit_id": 1, "purchase_unit_id": 1, "pack_size": 1, "stock_amount": "0"}
        self.target = {"id": 2, "unit_id": 1, "purchase_unit_id": 1, "pack_size": 1, "stock_amount": "0"}

    def test_audits_only_reads_and_identifies_reference_fields(self):
        def fetch(method, path):
            self.assertEqual(method, "GET")
            if path == "objects/shopping_list":
                return [{"id": 3, "product_id": 1}, {"id": 4, "product_id2": 2}]
            return []
        result = audit_merge(Mock(side_effect=fetch), self.source, self.target)
        self.assertFalse(result["can_merge"])
        shopping = next(x for x in result["collections"] if x["collection"] == "shopping_list")
        self.assertEqual(shopping["count"], 2)
        self.assertEqual(shopping["references"][1]["product_id"], 2)
        self.assertEqual(shopping["references"][1]["field"], "product_id2")

    def test_unavailable_collection_blocks_merge(self):
        def fetch(method, path):
            if path == "objects/recipes_pos":
                raise RuntimeError("missing")
            return []
        result = audit_merge(fetch, self.source, self.target)
        self.assertTrue(any("Ingredientes de recetas" in b for b in result["blockers"]))

    def test_nonzero_stock_blocks_merge(self):
        source = {**self.source, "stock_amount": "2"}
        result = audit_merge(lambda *_: [], source, self.target)
        self.assertTrue(any("stock" in b for b in result["blockers"]))

    def test_all_collections_checked(self):
        requests = []
        def fetch(method, path):
            requests.append((method, path))
            return []
        audit_merge(fetch, self.source, self.target)
        self.assertEqual(requests, [("GET", "objects/" + name) for name, _ in COLLECTIONS])


if __name__ == "__main__":
    unittest.main()
