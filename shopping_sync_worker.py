"""Scheduled Alexa/Grocy synchronization with safe persisted checkpoints.

Disabled unless SHOPPING_SYNC_ENABLED=1. Run as a single process.
"""
import fcntl
import os
import time
from pathlib import Path

from shopping_sync_runtime import load_baseline, reconcile, save_baseline
from shopping_sync import normalize
from shopping_sync_adapters import (
    ha_todo_items, grocy_shopping_names, add_alexa, add_grocy,
    remove_alexa, remove_grocy,
)

STATE = Path(os.environ.get("SHOPPING_SYNC_STATE", "/data/shopping-sync.json"))


def run_once(*, dry_run=True):
    alexa = ha_todo_items()
    grocy = grocy_shopping_names()
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
        while True:
            try:
                result = run_once(dry_run=os.environ.get("SHOPPING_SYNC_ENABLED") != "1")
                print("Shopping sync checked: " +
                      ", ".join(key + "=" + str(len(result[key])) for key in (
                          "add_alexa", "add_grocy", "remove_alexa", "remove_grocy")),
                      flush=True)
            except Exception as exc:
                # Do not log exception bodies: remote APIs may include sensitive data.
                print("Shopping sync failed (" + type(exc).__name__ + ")", flush=True)
            time.sleep(120)


if __name__ == "__main__":
    main()
