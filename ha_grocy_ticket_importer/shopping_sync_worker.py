"""Scheduled Alexa/Grocy synchronization with safe persisted checkpoints.

Disabled unless SHOPPING_SYNC_ENABLED=1. Run as a single process.
"""
import fcntl
import os
import time
import threading
from shopping_sync_events import listen
from pathlib import Path

from shopping_sync_runtime import load_baseline, reconcile, save_baseline
from shopping_sync import normalize
import hashlib
from shopping_sync_adapters import (
    ha_todo_items, grocy_shopping_names, add_alexa, add_grocy,
    remove_alexa, remove_grocy,
)

ENTITY = os.environ.get("ALEXA_SHOPPING_LIST_ENTITY", "")
# Separate baselines by selected Alexa entity to avoid carrying deletion
# history across list changes. The entity identifier is not logged.
ENTITY_HASH = hashlib.sha256(ENTITY.encode("utf-8")).hexdigest()[:16]
STATE = Path(os.environ.get("SHOPPING_SYNC_STATE", "/data/shopping-sync-" + ENTITY_HASH + ".json"))


def run_once(*, dry_run=True):
    try:
        alexa = ha_todo_items()
    except Exception as exc:
        raise RuntimeError("Alexa read failed: " + (str(exc) if isinstance(exc, RuntimeError) and str(exc).startswith("Home Assistant API token unavailable") else type(exc).__name__ + ((" HTTP " + str(exc.code)) if hasattr(exc, "code") else ""))) from None
    try:
        grocy = grocy_shopping_names()
    except Exception as exc:
        raise RuntimeError("Grocy read failed: " + type(exc).__name__ + ((" HTTP " + str(exc.code)) if hasattr(exc, "code") else "")) from None
    baseline = load_baseline(STATE)
    result = reconcile(
        alexa, grocy, baseline, dry_run=dry_run,
        add_alexa=add_alexa, add_grocy=add_grocy,
        remove_alexa=remove_alexa, remove_grocy=remove_grocy,
    )
    if not dry_run:
        # Re-read both sources before committing the checkpoint.
        # A failed or partial write must never advance the baseline.
        final_alexa = ha_todo_items()
        final_grocy = grocy_shopping_names()
        expected = set(result["next_baseline"])
        if ({normalize(n) for n in final_alexa} != expected or
                {normalize(n) for n in final_grocy} != expected):
            raise RuntimeError("Shopping sync verification failed")
        save_baseline(STATE, result["next_baseline"])
    return result


def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(str(STATE) + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wake = threading.Event()
        threading.Thread(target=listen, args=(wake,), daemon=True).start()
        while True:
            try:
                result = run_once(dry_run=os.environ.get("SHOPPING_SYNC_ENABLED") != "1")
                print("Shopping sync checked: " +
                      ", ".join(key + "=" + str(len(result[key])) for key in (
                          "add_alexa", "add_grocy", "remove_alexa", "remove_grocy")),
                      flush=True)
            except Exception as exc:
                # Do not log exception bodies: remote APIs may include sensitive data.
                print("Shopping sync failed: " + str(exc)[:180], flush=True)
            wake.wait(timeout=max(30, min(3600, int(os.environ.get("SHOPPING_SYNC_INTERVAL_SECONDS", "120")))))
            wake.clear()
            if wake.wait(timeout=1):
                wake.clear()


if __name__ == "__main__":
    main()
