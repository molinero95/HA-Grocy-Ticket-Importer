#!/usr/bin/env python3
"""Start the HA add-on with Supervisor configuration; never log secrets."""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

OPTIONS = Path("/data/options.json")
LEDGER = Path(os.environ.get("GROCY_IMPORT_DB", "/config/grocy_imports.sqlite3"))


def load_config(path=OPTIONS):
    options = json.loads(path.read_text(encoding="utf-8"))
    required = ("grocy_url", "grocy_api_key", "openai_api_key")
    for key in required:
        if not isinstance(options.get(key), str) or not options[key].strip():
            raise ValueError(f"Configura {key} en Home Assistant antes de iniciar Despensa")
    location = int(options.get("grocy_location_id", 2))
    if location <= 0:
        raise ValueError("grocy_location_id debe ser positivo")
    if not options["grocy_url"].startswith(("http://", "https://")):
        raise ValueError("grocy_url debe ser una URL HTTP o HTTPS")
    alexa_entity = str(options.get("alexa_shopping_list_entity") or "").strip()
    if alexa_entity and (not alexa_entity.startswith("todo.") or
                         not all(c.islower() or c.isdigit() or c in "._" for c in alexa_entity)):
        raise ValueError("alexa_shopping_list_entity debe ser una entidad todo.* válida")
    if options.get("shopping_sync_enabled") is True and not alexa_entity:
        raise ValueError("Configura alexa_shopping_list_entity antes de activar la sincronización")
    return {
        "ALEXA_SHOPPING_LIST_ENTITY": alexa_entity,
        "GROCY_URL": options["grocy_url"].rstrip("/"),
        "GROCY_API_KEY": options["grocy_api_key"],
        "OPENAI_API_KEY": options["openai_api_key"],
        "GROCY_LOCATION_ID": str(location),
        "SHOPPING_SYNC_ENABLED": "1" if options.get("shopping_sync_enabled") is True else "0",
    }


def ensure_ledger(path=LEDGER):
    """Existing ledgers are never rewritten; new installs start with an empty table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS receipt_items "
            "(receipt_hash TEXT, line INTEGER, product_id INTEGER, "
            "state TEXT NOT NULL, detail TEXT, PRIMARY KEY(receipt_hash,line))"
        )
    os.chmod(path, 0o600)


def main():
    try:
        config = load_config()
        ensure_ledger()
    except (OSError, ValueError, TypeError, json.JSONDecodeError, sqlite3.Error) as exc:
        # Never print entire configuration or an exception that may include a credential.
        print("No se pudo iniciar Despensa. Revisa las opciones en Home Assistant y el historial.", file=sys.stderr)
        return 1
    os.environ.update(config)
    metadata = Path("/app/addon_config.yaml").read_text(encoding="utf-8")
    version_lines = [line for line in metadata.splitlines() if line.startswith("version:")]
    os.environ["DESPENSA_VERSION"] = (
        version_lines[0].split(":", 1)[1].strip().strip(chr(34)).strip(chr(39))
        if version_lines else "dev"
    )
    os.environ["DESPENSA_DISTRIBUTION"] = "Repositorio comunitario de GitHub"
    subprocess.run(["nginx"], check=True)
    if os.environ.get("SHOPPING_SYNC_ENABLED") == "1":
        subprocess.Popen(["/venv/bin/python", "/app/shopping_sync_worker.py"], env=os.environ,
                         stdout=sys.stdout, stderr=sys.stderr)
    os.execvpe(
        "/venv/bin/gunicorn",
        ["/venv/bin/gunicorn", "--workers", "1", "--threads", "4", "--timeout", "210",
         "--bind", "127.0.0.1:8765", "web:app"],
        os.environ,
    )


if __name__ == "__main__":
    raise SystemExit(main())
