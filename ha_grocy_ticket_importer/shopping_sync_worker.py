"""Scheduled Alexa/Grocy synchronization with safe persisted checkpoints.

Disabled unless SHOPPING_SYNC_ENABLED=1. Run as a single process.
"""
import fcntl
import os
import time
import threading
from shopping_sync_events import listen
from pathlib import Path

from shopping_sync import normalize
from shopping_identity_sync import IdentityConflict
from shopping_identity_runtime import (
    load_identity_state, save_identity_state, reconcile_identity,
    verify_bindings, current_bindings,
)
from shopping_match_queue import (
    DEFAULT_PATH as MATCH_QUEUE, refresh as refresh_matches,
    resolved_choices, pending as pending_matches,
)
from importer import grocy
import hashlib
from shopping_sync_adapters import (
    ha_todo_items, grocy_entries, add_alexa, add_grocy_identity,
    remove_alexa_identity, remove_grocy_identity,
)

ENTITY = os.environ.get("ALEXA_SHOPPING_LIST_ENTITY", "")
# Separate baselines by selected Alexa entity to avoid carrying deletion
# history across list changes. The entity identifier is not logged.
ENTITY_HASH = hashlib.sha256(ENTITY.encode("utf-8")).hexdigest()[:16]
STATE = Path(os.environ.get("SHOPPING_SYNC_STATE", "/data/shopping-sync-" + ENTITY_HASH + ".json"))
# Separate v2 state: the first identity-aware run is an additive union, never
# interprets legacy name-only checkpoints as authority for product deletions.
STATE_V2 = STATE.with_name(STATE.stem + "-identity-v2.json")


def run_once(*, dry_run=True):
    try:
        alexa = ha_todo_items()
    except Exception as exc:
        raise RuntimeError("Alexa read failed: " + type(exc).__name__) from None
    try:
        grocy_rows = grocy_entries()
    except Exception as exc:
        raise RuntimeError("Grocy read failed: " + type(exc).__name__) from None
    products = grocy("GET", "objects/products")
    if not isinstance(products, list):
        raise RuntimeError("Grocy catalog unavailable for Alexa review")
    refresh_matches(MATCH_QUEUE, alexa, products)
    choices = resolved_choices(MATCH_QUEUE, alexa, products)
    # An old manual selection that is no longer a valid candidate must never
    # silently become free text and trigger a deletion via the old checkpoint.
    for row in pending_matches(MATCH_QUEUE):
        if row["selected_product_id"] is not None and row["key"] not in choices:
            raise IdentityConflict("An Alexa selection needs renewed review")
    previous = load_identity_state(STATE_V2)
    result = reconcile_identity(
        alexa, grocy_rows, products, previous, choices, dry_run=dry_run,
        add_alexa=lambda row: add_alexa(row["name"]),
        add_grocy=add_grocy_identity,
        remove_alexa=remove_alexa_identity,
        remove_grocy=remove_grocy_identity,
    )
    if not dry_run:
        # No checkpoint until both remotes converge by canonical identity.
        # Re-reading also catches concurrent edits and changed shopping amounts.
        final_alexa = ha_todo_items()
        final_grocy = grocy_entries()
        final_products = grocy("GET", "objects/products")
        final_a, final_g = verify_bindings(
            final_alexa, final_grocy, final_products, choices, previous)
        expected = set(result["next_baseline"])
        if set(final_a) != expected or set(final_g) != expected:
            raise RuntimeError("Shopping identity sync verification failed")
        save_identity_state(STATE_V2, result["next_baseline"],
                            current_bindings(final_a))
    return result

def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(str(STATE) + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wake = threading.Event()
        threading.Thread(target=listen, args=(wake,), daemon=True).start()
        trigger = "startup"
        while True:
            try:
                result = run_once(dry_run=os.environ.get("SHOPPING_SYNC_ENABLED") != "1")
                print("Shopping sync checked (" + trigger + "): " +
                      ", ".join(key + "=" + str(len(result[key])) for key in (
                          "add_alexa", "add_grocy", "remove_alexa", "remove_grocy")),
                      flush=True)
            except Exception as exc:
                # Only our own fixed conflict messages are safe to print.
                # Remote exception strings can contain tokens or private data.
                reason = str(exc) if isinstance(exc, IdentityConflict) else type(exc).__name__
                print("Shopping sync failed: " + reason, flush=True)
            triggered = wake.wait(timeout=max(30, min(3600, int(os.environ.get("SHOPPING_SYNC_INTERVAL_SECONDS", "120")))))
            wake.clear()
            trigger = "event" if triggered else "polling"


if __name__ == "__main__":
    main()
