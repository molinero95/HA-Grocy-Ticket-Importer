"""Durable identity-based shopping sync checkpoint and guarded write executor."""
import json
import os
import tempfile
from pathlib import Path

from shopping_identity_sync import IdentityConflict, identities, plan_identity
from shopping_sync import normalize


def load_identity_state(path):
    path = Path(path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 2:
        raise IdentityConflict("Unsupported identity sync checkpoint")
    keys, bindings = data.get("keys"), data.get("bindings")
    if not isinstance(keys, list) or not isinstance(bindings, dict):
        raise IdentityConflict("Invalid identity sync checkpoint")
    if len(keys) != len(set(keys)) or any(
            not isinstance(key, str) or not key.startswith(("p:", "n:"))
            for key in keys):
        raise IdentityConflict("Invalid identity keys")
    for name, pid in bindings.items():
        if not name or normalize(name) != name or type(pid) is not int or pid <= 0:
            raise IdentityConflict("Invalid Alexa identity binding")
    return {"keys": keys, "bindings": bindings}


def save_identity_state(path, keys, bindings):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 2, "keys": sorted(set(keys)),
               "bindings": dict(sorted(bindings.items()))}
    # Validate before replacing a known-good checkpoint.
    fd, temporary = tempfile.mkstemp(prefix=".identity-sync-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False))
            stream.flush()
            os.fsync(stream.fileno())
        if load_identity_state(temporary) is None:
            raise IdentityConflict("Invalid temporary checkpoint")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_bindings(alexa_names, grocy_rows, products, choices, previous):
    """Refuse silent identity changes for Alexa items that still exist."""
    a, g = identities(alexa_names, grocy_rows, products, choices)
    if previous is not None:
        current = {row["normalized"]: row["product_id"] for row in a.values()}
        for normalized, pid in previous["bindings"].items():
            if normalized in current and current[normalized] != pid:
                raise IdentityConflict("An Alexa item changed its product identity")
    return a, g


def current_bindings(alexa_snapshot):
    return {row["normalized"]: row["product_id"]
            for row in alexa_snapshot.values() if row["product_id"]}


def reconcile_identity(alexa_names, grocy_rows, products, previous, choices,
                       *, dry_run=True, add_alexa=None, add_grocy=None,
                       remove_alexa=None, remove_grocy=None):
    a, _ = verify_bindings(alexa_names, grocy_rows, products, choices, previous)
    result = plan_identity(alexa_names, grocy_rows, products,
                           previous["keys"] if previous is not None else None,
                           choices)
    result["next_bindings"] = current_bindings(a)
    if dry_run:
        return result
    callbacks = {"add_alexa": add_alexa, "add_grocy": add_grocy,
                 "remove_alexa": remove_alexa, "remove_grocy": remove_grocy}
    for action, callback in callbacks.items():
        if result[action] and not callable(callback):
            raise IdentityConflict("Missing callback for " + action)
    for action in ("remove_alexa", "remove_grocy", "add_alexa", "add_grocy"):
        for row in result[action]:
            callbacks[action](row)
    return result
