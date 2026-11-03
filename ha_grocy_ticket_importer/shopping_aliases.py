"""Persistent, entity-scoped Alexa aliases mapped to canonical Grocy product IDs.

An alias belongs to at most one product within a list. A product may own many
aliases. Never rename Alexa items or modify Grocy stock from this module.
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from shopping_sync import normalize


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.execute("""CREATE TABLE IF NOT EXISTS alexa_aliases (
        normalized_name TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        product_id INTEGER NOT NULL CHECK(product_id > 0)
    )""")
    return db


def list_aliases(path):
    with closing(connect(path)) as db:
        return [{"name": name, "key": key, "product_id": pid}
                for key, name, pid in db.execute(
                    "SELECT normalized_name, display_name, product_id "
                    "FROM alexa_aliases ORDER BY display_name, product_id")]


def set_alias(path, name, product_id):
    if not isinstance(name, str) or len(name) > 200 or type(product_id) is not int:
        raise ValueError("Invalid alias")
    key = normalize(name)
    if not key:
        raise ValueError("Alias cannot be empty")
    pid = int(product_id)
    if pid <= 0:
        raise ValueError("Invalid product ID")
    with closing(connect(path)) as db, db:
        db.execute(
            "INSERT INTO alexa_aliases(normalized_name,display_name,product_id) "
            "VALUES (?,?,?) ON CONFLICT(normalized_name) DO UPDATE SET "
            "display_name=excluded.display_name, product_id=excluded.product_id",
            (key, str(name).strip(), pid))


def update_alias(path, key, *, expected_name, expected_product_id, name, product_id):
    """Atomically rename/reassign a reviewed alias; the new association wins collisions."""
    if (not isinstance(name, str) or not name.strip() or len(name) > 200
            or type(product_id) is not int or product_id <= 0
            or not isinstance(expected_name, str) or len(expected_name) > 200
            or type(expected_product_id) is not int or expected_product_id <= 0):
        raise ValueError("Invalid alias")
    key, new_key = normalize(key), normalize(name)
    if not new_key or normalize(expected_name) != key:
        raise ValueError("Invalid alias")
    with closing(connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute(
            "SELECT display_name, product_id FROM alexa_aliases WHERE normalized_name=?", (key,)
        ).fetchone()
        if previous != (expected_name, expected_product_id):
            raise ValueError("Alias changed since it was displayed")
        if new_key != key:
            db.execute("DELETE FROM alexa_aliases WHERE normalized_name=?", (new_key,))
        db.execute("UPDATE alexa_aliases SET normalized_name=?, display_name=?, product_id=? WHERE normalized_name=?",
                   (new_key, name.strip(), product_id, key))
    return {"key": new_key, "name": name.strip(), "product_id": product_id}


def remove_alias(path, name, product_id=None):
    with closing(connect(path)) as db, db:
        row = db.execute("SELECT product_id FROM alexa_aliases WHERE normalized_name=?", (normalize(name),)).fetchone()
        if row and product_id is not None and row[0] != product_id:
            raise ValueError("Alias changed since it was displayed")
        db.execute("DELETE FROM alexa_aliases WHERE normalized_name=?",
                   (normalize(name),))


def choices(path, products, *, names=None):
    """Return validated choices; stale product IDs must not be silently reused."""
    catalog = {int(p["id"]) for p in products}
    result = {}
    present = {normalize(name) for name in names} if names is not None else None
    for alias in list_aliases(path):
        if present is not None and alias["key"] not in present:
            continue
        if alias["product_id"] not in catalog:
            raise ValueError("Alexa alias references a missing product")
        result[alias["key"]] = {"product_id": alias["product_id"]}
    return result
