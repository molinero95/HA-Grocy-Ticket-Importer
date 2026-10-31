"""Local variant metadata for Grocy products; Grocy owns aggregate stock.

This module never changes Grocy stock, product IDs, or shopping entries.
Schema is additive and safe to initialize on an existing add-on data volume.
"""
import sqlite3
from pathlib import Path


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS generic_products (
        id INTEGER PRIMARY KEY,
        grocy_product_id INTEGER NOT NULL UNIQUE CHECK (grocy_product_id > 0),
        display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0)
    );
    CREATE TABLE IF NOT EXISTS product_variants (
        id INTEGER PRIMARY KEY,
        generic_id INTEGER NOT NULL REFERENCES generic_products(id) ON DELETE RESTRICT,
        display_name TEXT NOT NULL CHECK (length(trim(display_name)) > 0),
        supermarket TEXT NOT NULL DEFAULT '',
        brand TEXT NOT NULL DEFAULT '',
        barcode TEXT NOT NULL UNIQUE CHECK (length(barcode) BETWEEN 8 AND 14
          AND barcode NOT GLOB '*[^0-9]*'),
        units_per_purchase REAL NOT NULL DEFAULT 1 CHECK (units_per_purchase > 0)
    );
    CREATE INDEX IF NOT EXISTS idx_variants_generic ON product_variants(generic_id);
    """)
    db.commit()
    return db


def register_generic(db, grocy_product_id, name):
    if int(grocy_product_id) <= 0 or not str(name).strip():
        raise ValueError("Invalid generic product")
    with db:
        db.execute(
            "INSERT INTO generic_products(grocy_product_id, display_name) VALUES (?, ?) "
            "ON CONFLICT(grocy_product_id) DO UPDATE SET display_name=excluded.display_name",
            (int(grocy_product_id), str(name).strip()))
    return db.execute("SELECT id FROM generic_products WHERE grocy_product_id=?",
                      (int(grocy_product_id),)).fetchone()[0]


def register_variant(db, generic_id, barcode, name, *, supermarket="", brand="", units_per_purchase=1, grocy_barcode_owners=None):
    barcode = str(barcode).strip()
    if not barcode.isascii() or not barcode.isdigit() or not 8 <= len(barcode) <= 14:
        raise ValueError("Invalid barcode")
    if not str(name).strip() or not 0 < float(units_per_purchase) < 1000000:
        raise ValueError("Invalid variant")
    # Barcode ownership must be checked against a fresh Grocy snapshot by the caller.\n    if grocy_barcode_owners is None:\n        raise ValueError("Grocy barcode ownership audit required")\n    canonical = db.execute(\n        "SELECT grocy_product_id FROM generic_products WHERE id=?",\n        (int(generic_id),)).fetchone()\n    if canonical is None:\n        raise ValueError("Unknown generic product")\n    if {int(owner) for owner in grocy_barcode_owners} - {canonical[0]}:\n        raise ValueError("Barcode belongs to another Grocy product")\n    # A barcode already linked to another generic must never be reassigned.
    existing = db.execute(
        "SELECT generic_id FROM product_variants WHERE barcode=?", (barcode,)).fetchone()
    if existing and existing[0] != int(generic_id):
        raise ValueError("Barcode already assigned to another generic")
    with db:
        db.execute(
            "INSERT INTO product_variants(generic_id, barcode, display_name, supermarket, brand, units_per_purchase) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(barcode) DO UPDATE SET "
            "display_name=excluded.display_name, supermarket=excluded.supermarket, "
            "brand=excluded.brand, units_per_purchase=excluded.units_per_purchase",
            (int(generic_id), barcode, str(name).strip(), str(supermarket).strip(),
             str(brand).strip(), float(units_per_purchase)))


def resolve_barcode(db, barcode):
    row = db.execute(
        "SELECT g.grocy_product_id, g.display_name, v.display_name, v.supermarket, "
        "v.brand, v.units_per_purchase FROM product_variants v "
        "JOIN generic_products g ON g.id=v.generic_id WHERE v.barcode=?",
        (str(barcode).strip(),)).fetchone()
    if row is None:
        return None
    return dict(zip(("grocy_product_id", "generic_name", "variant_name",
                     "supermarket", "brand", "units_per_purchase"), row))
