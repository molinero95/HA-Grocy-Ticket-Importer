"""Sanitized worker health shared with Flask; no names, credentials or checkpoints."""
import json
import os
import tempfile
import time
from pathlib import Path


def _read(path):
    try:
        data = json.loads(Path(str(path) + ".sync-status.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record(path, *, dry_run, error=None):
    from shopping_identity_sync import IdentityConflict
    reason = None
    if error is not None:
        reason = "note_conflict" if isinstance(error, IdentityConflict) and "note conflicts" in str(error) else (
            "identity_conflict" if isinstance(error, IdentityConflict) else "unavailable")
    now = time.time()
    data = {"state": "error" if error else "ok", "reason": reason,
            "checked_at": now, "last_success_at": _read(path).get("last_success_at"), "dry_run": bool(dry_run)}
    if error is None and not dry_run:
        data["last_success_at"] = now
    # Health reporting must never turn a verified shopping operation into a retry.
    temporary = None
    try:
        target = Path(str(path) + ".sync-status.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".sync-status-", dir=target.parent)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream)
        os.replace(temporary, target)
    except OSError:
        pass
    finally:
        try:
            if temporary and Path(temporary).exists():
                Path(temporary).unlink()
        except OSError:
            pass


def snapshot(path):
    if not os.environ.get("ALEXA_SHOPPING_LIST_ENTITY"):
        return {"state": "unconfigured"}
    if os.environ.get("SHOPPING_SYNC_ENABLED") != "1":
        return {"state": "disabled"}
    data = _read(path)
    if data.get("state") not in ("ok", "error") or data.get("dry_run") is not False:
        return {"state": "unknown"}
    checked = data.get("checked_at")
    if not isinstance(checked, (int, float)) or isinstance(checked, bool):
        return {"state": "unknown"}
    try:
        interval = int(os.environ.get("SHOPPING_SYNC_INTERVAL_SECONDS", "120"))
    except ValueError:
        interval = 120
    if time.time() - checked > max(180, interval * 3):
        return {"state": "stale"}
    reason = data.get("reason")
    return {"state": "error" if data.get("state") == "error" else "ok",
            "reason": reason if reason in ("note_conflict", "identity_conflict", "unavailable") else None,
            "checked_at": checked}
