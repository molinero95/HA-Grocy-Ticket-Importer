#!/bin/sh
set -eu
CONFIG_DIR="/config"
if [ ! -f "$CONFIG_DIR/.env" ]; then
    echo "Missing $CONFIG_DIR/.env — retain the existing local credentials file."
    exit 1
fi
if [ ! -f "$CONFIG_DIR/grocy_imports.sqlite3" ]; then
    echo "Missing import history database. Migrate the existing grocy_imports.sqlite3 before first start to prevent duplicate imports."
    exit 1
fi
export GROCY_ENV_FILE="$CONFIG_DIR/.env"
mkdir -p /data/receipts
if [ ! -s /data/session_secret ]; then
    /venv/bin/python -c 'import secrets;open("/data/session_secret","w").write(secrets.token_urlsafe(48))'
    chmod 600 /data/session_secret
fi
export WEB_SESSION_SECRET="$(cat /data/session_secret)"
export HA_INGRESS_MODE="1"
export RECEIPT_DATA_DIR="/data/receipts"
export GROCY_IMPORT_DB="$CONFIG_DIR/grocy_imports.sqlite3"
nginx
exec /venv/bin/gunicorn --workers 1 --threads 4 --timeout 210 --bind 127.0.0.1:8765 web:app
