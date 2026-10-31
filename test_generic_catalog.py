import tempfile
import unittest
from pathlib import Path

from generic_catalog import connect, register_generic, register_variant, resolve_barcode


class GenericCatalogTests(unittest.TestCase):
    def test_variants_share_one_grocy_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = connect(Path(tmp) / "catalog.db")
            gid = register_generic(db, 42, "Leche entera")
            register_variant(db, gid, "8480000000001", "Leche Hacendado", supermarket="Mercadona")
            register_variant(db, gid, "8480000000002", "Leche Carrefour", supermarket="Carrefour")
            self.assertEqual(resolve_barcode(db, "8480000000001")["grocy_product_id"], 42)
            self.assertEqual(resolve_barcode(db, "8480000000002")["grocy_product_id"], 42)
            self.assertEqual(db.execute("SELECT count(*) FROM generic_products").fetchone()[0], 1)
            db.close()

    def test_barcode_cannot_move_between_generics(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = connect(Path(tmp) / "catalog.db")
            a = register_generic(db, 1, "Leche")
            b = register_generic(db, 2, "Agua")
            register_variant(db, a, "8480000000001", "Leche")
            with self.assertRaises(ValueError):
                register_variant(db, b, "8480000000001", "Agua")
            self.assertEqual(resolve_barcode(db, "8480000000001")["grocy_product_id"], 1)
            db.close()

    def test_idempotent_schema_and_unmatched_barcode(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalog.db"
            connect(path).close()
            db = connect(path)
            self.assertIsNone(resolve_barcode(db, "8480000000000"))
            db.close()


if __name__ == "__main__":
    unittest.main()
