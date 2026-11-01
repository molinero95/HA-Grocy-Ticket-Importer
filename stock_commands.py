"""Durable at-most-once stock command dispatch, isolated from Grocy's ledger.

A started command is deliberately never retried after a crash: Grocy may already
have applied the write. Completed commands replay their recorded response.
"""
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path


class CommandConflict(ValueError):
    pass


def execute_once(operation_id, payload, operation):
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9-]{36}", operation_id):
        raise CommandConflict("Identificador de operación no válido")
    directory = Path(os.environ.get("GROCY_IMPORT_DB", str(Path(__file__).parent / "runtime" / "grocy_imports.sqlite3"))).parent
    path = Path(os.environ.get("STOCK_COMMAND_DB", str(directory / "stock-commands.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("CREATE TABLE IF NOT EXISTS stock_commands (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT)")
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT digest, result FROM stock_commands WHERE id=?", (operation_id,)).fetchone()
        if row:
            if row[0] != digest:
                raise CommandConflict("El identificador ya pertenece a otra operación")
            if row[1] is None:
                raise CommandConflict("Resultado incierto. Comprueba el stock de Grocy antes de otra operación")
            return json.loads(row[1])
        db.execute("INSERT INTO stock_commands(id,digest) VALUES (?,?)", (operation_id, digest))
        db.commit()  # Write-ahead marker must survive before the remote write.
        result = operation()
        db.execute("UPDATE stock_commands SET result=? WHERE id=?", (json.dumps(result), operation_id))
        db.commit()
        return result
