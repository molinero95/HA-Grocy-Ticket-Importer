"""Durable, non-destructive review queue for ambiguous Alexa shopping names.

Queue entries are advisory. No code here modifies Alexa, Grocy, stock,
shopping notes, or sync checkpoints. Manual selection is stored separately.
"""
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from shopping_sync import normalize, suggest_catalog_matches

BASE_PATH = Path(os.environ.get("ALEXA_MATCH_QUEUE_DB", "/config/alexa-match-queue.sqlite3"
    if os.environ.get("HA_INGRESS_MODE") == "1" else str(Path(__file__).resolve().parent / "runtime" / "alexa-match-queue.sqlite3")))


def scoped_path(base_path, entity):
    """Keep manual choices isolated to the configured Alexa list entity.

    The legacy unscoped database is deliberately left untouched: migrating
    choices without knowing their originating list could cross-link products.
    """
    path = Path(base_path)
    if not entity:
        return path
    digest = hashlib.sha256(entity.strip().encode("utf-8")).hexdigest()[:16]
    return path.with_name(path.stem + "-" + digest + path.suffix)


DEFAULT_PATH = scoped_path(BASE_PATH, os.environ.get("ALEXA_SHOPPING_LIST_ENTITY", ""))

def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.executescript("""
    CREATE TABLE IF NOT EXISTS pending_matches (
        normalized_name TEXT PRIMARY KEY,
        original_name TEXT NOT NULL,
        candidates_json TEXT NOT NULL,
        selected_product_id INTEGER,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
    );
    """)
    # Additive migration: retain all existing choices and scoped databases.
    db.execute("BEGIN IMMEDIATE")
    columns = {row[1] for row in db.execute("PRAGMA table_info(pending_matches)")}
    if "dismissed" not in columns:
        db.execute("ALTER TABLE pending_matches ADD COLUMN dismissed INTEGER NOT NULL DEFAULT 0")
    db.commit()
    return db


def refresh(path, alexa_names, products):
    """Refresh advisory suggestions, preserving original names and selections.

    Only ambiguous matches are queued. Exact matches are not reclassified.
    Disappearing Alexa entries become inactive rather than being deleted.
    Stale selections remain for explicit conflict detection; they cannot be
    silently reset while a verified checkpoint may still reference them.
    """
    pending = {}
    for name in alexa_names:
        key = normalize(name)
        if not key:
            continue
        decision, candidates = suggest_catalog_matches(name, products)
        if decision == "review":
            if key in pending:
                raise ValueError("Duplicate normalized Alexa item")
            pending[key] = (str(name).strip(), json.dumps(candidates, ensure_ascii=False))
    with closing(connect(path)) as db, db:
        db.execute("UPDATE pending_matches SET active=0")
        for key, (original, candidates) in pending.items():
            db.execute(
                "INSERT INTO pending_matches(normalized_name,original_name,candidates_json,active) "
                "VALUES (?,?,?,1) ON CONFLICT(normalized_name) DO UPDATE SET "
                "original_name=excluded.original_name, active=1, "
                "candidates_json=excluded.candidates_json",
                (key, original, candidates))


def pending(path):
    with closing(connect(path)) as db:
        rows = db.execute(
            "SELECT normalized_name, original_name, candidates_json, selected_product_id, dismissed "
            "FROM pending_matches WHERE active=1 ORDER BY original_name").fetchall()
    result = []
    for key, original, candidates, selected, dismissed in rows:
        options = json.loads(candidates)
        candidate_ids = {int(option["id"]) for option in options}
        result.append({"key": key, "name": original, "candidates": options,
                       "selected_product_id": selected, "dismissed": bool(dismissed),
                       "selection_stale": selected is not None and selected not in candidate_ids})
    return result


def choose(path, key, product_id):
    """Record an explicit candidate choice; never convert shopping notes."""
    key = normalize(key)
    pid = int(product_id)
    with closing(connect(path)) as db, db:
        row = db.execute(
            "SELECT candidates_json FROM pending_matches WHERE normalized_name=? AND active=1",
            (key,)).fetchone()
        if not row or pid not in {int(item["id"]) for item in json.loads(row[0])}:
            raise ValueError("La coincidencia ya no está disponible; actualiza la lista")
        db.execute("UPDATE pending_matches SET selected_product_id=?, dismissed=0 WHERE normalized_name=?",
                   (pid, key))


def keep_original(path, key):
    """Explicitly clear a previously selected candidate, retaining Alexa's original item.

    Refuse stale or inactive entries so a delayed UI action cannot affect another sync.
    """
    key = normalize(key)
    with closing(connect(path)) as db, db:
        row = db.execute(
            "SELECT 1 FROM pending_matches WHERE normalized_name=? AND active=1",
            (key,)).fetchone()
        if row is None:
            raise ValueError("La propuesta ya no está disponible; actualiza la lista")
        db.execute(
            "UPDATE pending_matches SET selected_product_id=NULL, dismissed=1 WHERE normalized_name=? AND active=1",
            (key,))


def resolved_choices(path, alexa_names, products):
    """Read-only, validated identity mapping for the next sync stage.

    Never changes remote shopping entries or local checkpoints. An explicit
    selection is valid only while the original Alexa item is present and the
    chosen product remains a current candidate in the Grocy catalog.
    """
    present = {normalize(name) for name in alexa_names}
    catalog = {int(product["id"]): product for product in products}
    result = {}
    for entry in pending(path):
        key = entry["key"]
        selected = entry["selected_product_id"]
        if key not in present or selected is None:
            continue
        candidate_ids = {int(candidate["id"]) for candidate in entry["candidates"]}
        if selected not in candidate_ids or selected not in catalog:
            continue
        decision, current = suggest_catalog_matches(entry["name"], products)
        if decision != "review" or selected not in {int(item["id"]) for item in current}:
            continue
        result[key] = {"product_id": selected, "product_name": catalog[selected]["name"],
                       "original_name": entry["name"]}
    return result


def acknowledge_choices(path, choices):
    """Hide verified choices from UI without discarding identity bindings."""
    with closing(connect(path)) as db, db:
        for key, choice in choices.items():
            db.execute("UPDATE pending_matches SET dismissed=1 WHERE normalized_name=? AND selected_product_id=?",
                       (key, int(choice["product_id"])))
