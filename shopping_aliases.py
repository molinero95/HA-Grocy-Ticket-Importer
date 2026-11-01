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
    key = normalize(name)
    if not key:
        raise ValueError("Alias cannot be empty")
    pid = int(product_id)
    if pid <= 0:
        raise ValueError("Invalid product ID")
    with closing(connect(path)) as db, db:
        previous = db.execute(
            "SELECT product_id FROM alexa_aliases WHERE normalized_name=?", (key,)
        ).fetchone()
        if previous and previous[0] != pid:
            raise ValueError("Alias already belongs to another product")
        db.execute(
            "INSERT INTO alexa_aliases(normalized_name,display_name,product_id) "
            "VALUES (?,?,?) ON CONFLICT(normalized_name) DO UPDATE SET "
            "display_name=excluded.display_name",
            (key, str(name).strip(), pid))


def remove_alias(path, name):
    with closing(connect(path)) as db, db:
        db.execute("DELETE FROM alexa_aliases WHERE normalized_name=?",
                   (normalize(name),))


def choices(path, products):
    """Return validated choices; stale product IDs must not be silently reused."""
    catalog = {int(p["id"]) for p in products}
    result = {}
    for alias in list_aliases(path):
        if alias["product_id"] not in catalog:
            raise ValueError("Alexa alias references a missing product")
        result[alias["key"]] = {"product_id": alias["product_id"]}
    return result
