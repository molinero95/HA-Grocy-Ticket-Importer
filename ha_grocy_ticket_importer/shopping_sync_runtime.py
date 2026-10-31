"""Safe one-shot sync engine; no writes without an explicit configured bridge.

Persist the baseline atomically *after* all remote operations succeed.
Incomplete runs are retried from fresh snapshots; additions are idempotent.
The caller must supply live snapshots and callbacks for each remote API.
"""
import json
import os
import tempfile
from pathlib import Path

from shopping_sync import normalize, plan


class SyncConflict(RuntimeError):
    pass


def load_baseline(path):
    path = Path(path)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("names"), list):
        raise SyncConflict("Unsupported sync baseline")
    names = payload["names"]
    if any(not isinstance(x, str) or normalize(x) != x for x in names):
        raise SyncConflict("Invalid sync baseline")
    return names


def save_baseline(path, names):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({"version": 1, "names": sorted(set(names))})
    fd, temp = tempfile.mkstemp(prefix=".shopping-sync-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def reconcile(alexa_names, grocy_names, baseline, *, dry_run=True,
              add_alexa=None, add_grocy=None, remove_alexa=None, remove_grocy=None):
    changes = plan(alexa_names, grocy_names, baseline)
    if dry_run:
        return changes
    callbacks = {
        "add_alexa": add_alexa, "add_grocy": add_grocy,
        "remove_alexa": remove_alexa, "remove_grocy": remove_grocy,
    }
    for action, callback in callbacks.items():
        if changes[action] and not callable(callback):
            raise SyncConflict("Missing callback for " + action)
    # Deletions first: do not resurrect items removed by the user.
    for action in ("remove_alexa", "remove_grocy", "add_alexa", "add_grocy"):
        for name in changes[action]:
            callbacks[action](name)
    return changes
