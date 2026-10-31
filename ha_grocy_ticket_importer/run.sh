#!/bin/sh
set -eu
# Config is supplied by Home Assistant in /data/options.json.
# App state (receipt import ledger) stays in the app's private persistent /config.
export GROCY_IMPORT_DB="/config/grocy_imports.sqlite3"
export RECEIPT_DATA_DIR="/data/receipts"
export HA_INGRESS_MODE="1"
mkdir -p /config /data/receipts
if [ ! -s /data/session_secret ]; then
    /venv/bin/python -c 'import secrets;open("/data/session_secret","w").write(secrets.token_urlsafe(48))'
    chmod 600 /data/session_secret
fi
export WEB_SESSION_SECRET="$(cat /data/session_secret)"
exec /venv/bin/python /app/addon_bootstrap.py
