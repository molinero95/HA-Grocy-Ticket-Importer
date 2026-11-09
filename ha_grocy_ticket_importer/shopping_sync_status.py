"""Sanitized worker health shared with Flask; no names, credentials or checkpoints."""
import json
import math
import os
import tempfile
import time
from pathlib import Path



DETAILS = {
    'Multiple Alexa items resolve to the same identity': 'duplicate_alexa_identity',
    'Shopping entry references a missing Grocy product': 'missing_product',
    'Duplicate normalized Grocy shopping name': 'duplicate_shopping_name',
    'Duplicate Grocy shopping identity': 'duplicate_shopping_identity',
    'An Alexa item changed its product identity': 'changed_identity',
    'An Alexa selection needs renewed review': 'stale_selection',
    'Selected product is no longer in Grocy': 'stale_selection',
    'Selected product is no longer a valid candidate': 'stale_selection',
    'Alexa alias conflicts with a pending manual choice': 'alias_selection_conflict',
    'A Grocy note conflicts with a canonical product': 'note_conflict',
    'A Grocy note conflicts with a selected product': 'note_conflict',
}

def _read(path):
    try:
        data = json.loads(Path(str(path) + ".sync-status.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def poll_interval():
    try:
        return max(30, min(3600, int(os.environ.get("SHOPPING_SYNC_INTERVAL_SECONDS", "120"))))
    except ValueError:
        return 120


def retry_delay(failures):
    # 2, 4, 8, 16, then 30 minutes. Never shorten a longer configured interval.
    return max(poll_interval(), min(1800, 120 * 2 ** min(max(0, failures - 1), 4)))


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def retry_state(path):
    data = _read(path)
    count = data.get("consecutive_failures")
    checked, retry = data.get("checked_at"), data.get("next_retry_at")
    if (data.get("state") != "error" or type(count) is not int or not 1 <= count <= 31
            or not _finite(checked) or not _finite(retry)
            or not checked <= retry <= checked + 3600 or retry > time.time() + 3600):
        return {"consecutive_failures": 0, "next_retry_at": 0}
    return {"consecutive_failures": count, "next_retry_at": retry}


def record(path, *, dry_run, error=None, failure_count=None):
    from shopping_identity_sync import IdentityConflict
    reason = None
    if error is not None:
        reason = "note_conflict" if isinstance(error, IdentityConflict) and "note conflicts" in str(error) else (
            "identity_conflict" if isinstance(error, IdentityConflict) else "unavailable")
    now = time.time()
    previous = _read(path)
    failures = 0
    if error:
        failures = (failure_count if type(failure_count) is int and 1 <= failure_count <= 31
                    else min(31, retry_state(path)["consecutive_failures"] + 1))
    data = {"state": "error" if error else "ok", "reason": reason,
            "detail_code": DETAILS.get(str(error)) if isinstance(error, IdentityConflict) else None,
            "affected_product_ids": list(error.product_ids)[:20] if isinstance(error, IdentityConflict) else [],
            "consecutive_failures": failures, "next_retry_at": now + retry_delay(failures) if error else None,
            "checked_at": now, "last_success_at": previous.get("last_success_at"), "dry_run": bool(dry_run)}
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
    if not _finite(checked):
        return {"state": "unknown"}
    retry = retry_state(path)
    now = time.time()
    # A sleeping worker is healthy until its scheduled retry plus the usual grace.
    if now - max(checked, retry["next_retry_at"]) > max(180, poll_interval() * 3):
        return {"state": "stale", "checked_at": checked}
    reason = data.get("reason")
    return {"state": "error" if data.get("state") == "error" else "ok",
            "paused": retry["next_retry_at"] > now,
            "next_retry_at": retry["next_retry_at"] or None,
            "retry_after_seconds": max(0, math.ceil(retry["next_retry_at"] - now)),
            "consecutive_failures": retry["consecutive_failures"],
            "reason": reason if reason in ("note_conflict", "identity_conflict", "unavailable") else None,
            "checked_at": checked,
            "affected_product_ids": [pid for pid in data.get('affected_product_ids', []) if type(pid) is int and pid > 0][:20] if isinstance(data.get('affected_product_ids', []), list) else [],
            "last_success_at": data.get("last_success_at") if _finite(data.get("last_success_at")) else None,
            "detail_code": data.get("detail_code") if data.get("detail_code") in DETAILS.values() else None}
