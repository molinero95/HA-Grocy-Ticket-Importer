"""Scheduled Alexa/Grocy synchronization with safe persisted checkpoints.

Disabled unless SHOPPING_SYNC_ENABLED=1. Run as a single process.
"""
import fcntl
import os
import time
import threading
from shopping_sync_events import listen, listen_local
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


def run_once(*, dry_run=True, failure_count=None, blocking=True):
    from shopping_match_queue import mutation_lock
    from shopping_sync_status import record
    with mutation_lock(MATCH_QUEUE, blocking=blocking):
        try:
            result = _run_once(dry_run=dry_run)
        except Exception as exc:
            record(MATCH_QUEUE, dry_run=dry_run, error=exc, failure_count=failure_count)
            raise
        record(MATCH_QUEUE, dry_run=dry_run)
        return result


def _run_once(*, dry_run=True):
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
    from shopping_sync_adapters import _grocy_done
    products = [p for p in products if _grocy_done(p.get("active", True))]
    from shopping_choice_conversion import restore_verified_choices
    import shopping_match_queue
    restore_verified_choices(shopping_match_queue, MATCH_QUEUE, grocy_rows, products)
    refresh_matches(MATCH_QUEUE, alexa, products, grocy_rows)
    choices = resolved_choices(MATCH_QUEUE, alexa, products)
    # Persistent aliases are explicit user mappings, not fuzzy suggestions.
    from shopping_aliases import choices as alias_choices
    for alias, selected in alias_choices(MATCH_QUEUE, products, names=alexa).items():
        if alias in choices and int(choices[alias]["product_id"]) != int(selected["product_id"]):
            raise IdentityConflict("Alexa alias conflicts with a pending manual choice")
        choices[alias] = {**selected, "trusted_alias": True}
    removals = [row for row in pending_matches(MATCH_QUEUE) if row.get("removed")]
    if removals:
        # Explicit manual deletion wins even before the first union/checkpoint.
        # In read-only mode it only suppresses re-import; no Alexa writes occur.
        from shopping_choice_conversion import delete_verified
        from shopping_sync import suggest_catalog_matches
        removed_names = {entry["key"] for entry in removals}
        removed_products = {int(entry["removal"].get("product_id") or 0)
                            for entry in removals if entry.get("removal")}
        removed_products.discard(0)
        # Before the first verified checkpoint, another known synonym must not
        # resurrect a deliberately removed canonical row. Expand only exact or
        # explicitly validated IDs, never fuzzy candidates or unrelated notes.
        for name in alexa:
            key = normalize(name)
            chosen = choices.get(key)
            decision, candidates = suggest_catalog_matches(name, products)
            pid = int(chosen["product_id"]) if chosen else (
                int(candidates[0]["id"]) if decision == "exact" else None)
            if pid in removed_products:
                removed_names.add(key)
        if not dry_run:
            for entry in removals:
                if entry.get("removal"):
                    delete_verified(grocy, entry["removal"])
            source_names = {normalize(name): name for name in alexa}
            source_names.update({entry["key"]: entry["name"] for entry in removals})
            for key in sorted(removed_names):
                remove_alexa_identity({"name": source_names[key]})
            observed = ha_todo_items()
            if {normalize(name) for name in observed}.intersection(removed_names):
                raise RuntimeError("Manual Alexa removal could not be verified")
            grocy_rows = grocy_entries()
            from shopping_match_queue import finish_removals
            finish_removals(MATCH_QUEUE, [entry["key"] for entry in removals])
        removed_ids = {int(entry["removal"]["id"]) for entry in removals if entry.get("removal")}
        alexa = [name for name in alexa if normalize(name) not in removed_names]
        grocy_rows = [(name, row) for name, row in grocy_rows if int(row["id"]) not in removed_ids]
    # An old manual selection that is no longer a valid candidate must never
    # silently become free text and trigger a deletion via the old checkpoint.
    present_names = {normalize(name) for name in alexa}
    for row in pending_matches(MATCH_QUEUE):
        if (row["key"] in present_names and not row.get("removed")
                and row["selected_product_id"] is not None and row["key"] not in choices):
            raise IdentityConflict("An Alexa selection needs renewed review", product_ids=(row["selected_product_id"],))
    previous = load_identity_state(STATE_V2)
    from shopping_choice_conversion import project_choices, apply_choices
    projected, conversions = project_choices(grocy_rows, products, choices)
    # Validate the entire projected graph before the first association write.
    if conversions:
        reconcile_identity(alexa, projected, products, previous, choices, dry_run=True)
    if conversions and not dry_run:
        apply_choices(grocy, conversions)
        grocy_rows = grocy_entries()
    elif dry_run:
        grocy_rows = projected
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
        final_products = [p for p in grocy("GET", "objects/products") if _grocy_done(p.get("active", True))]
        final_a, final_g = verify_bindings(
            final_alexa, final_grocy, final_products, choices, previous)
        expected = set(result["next_baseline"])
        if set(final_a) != expected or set(final_g) != expected:
            raise RuntimeError("Shopping identity sync verification failed")
        save_identity_state(STATE_V2, result["next_baseline"],
                            current_bindings(final_a))
        from shopping_match_queue import acknowledge_choices
        acknowledge_choices(MATCH_QUEUE, choices)
    return result

class SyncScheduler:
    """Persisted cooldown, with an in-memory fallback if health storage fails.

    Events coalesce during a pause; each retry still uses a fresh full snapshot.
    The journal/checkpoint and manual UI actions are outside this scheduler.
    """
    def __init__(self, path):
        from shopping_sync_status import retry_state
        retry = retry_state(path)
        self.path = path
        self.failures = retry["consecutive_failures"]
        self.retry_at = retry["next_retry_at"]
        self.revision = self.status_revision()

    def status_revision(self):
        try:
            return Path(str(self.path) + ".sync-status.json").stat().st_mtime_ns
        except OSError:
            return None

    def refresh(self):
        # A CSRF-protected manual cycle can complete while this worker is paused.
        # Ordinary list events do not change health and cannot shorten a pause.
        from shopping_sync_status import snapshot
        revision = self.status_revision()
        if revision is None or revision == self.revision:
            return
        health = snapshot(self.path)
        if health.get("state") not in ("ok", "error"):
            return
        self.failures = health.get("consecutive_failures", 0)
        self.retry_at = health.get("next_retry_at") or 0
        self.revision = revision

    def remaining(self):
        return max(0, self.retry_at - time.time())

    def run(self, *, dry_run):
        from shopping_sync_status import retry_delay
        self.refresh()
        if self.remaining():
            return None
        try:
            result = run_once(dry_run=dry_run, failure_count=min(31, self.failures + 1), blocking=False)
        except BlockingIOError:
            # A manual cycle owns the shared lock. Observe its result later.
            return None
        except Exception:
            self.failures = min(31, self.failures + 1)
            self.retry_at = time.time() + retry_delay(self.failures)
            self.revision = self.status_revision()
            raise
        self.revision = self.status_revision()
        self.failures, self.retry_at = 0, 0
        return result

    def wait(self, wake):
        from shopping_sync_status import poll_interval
        was_paused = bool(self.remaining())
        while self.remaining():
            # Bound local checks so a manual cycle can replace the schedule even
            # if its advisory wake notification could not be written.
            wake.wait(timeout=min(1, self.remaining()))
            wake.clear()
            self.refresh()
        if was_paused and self.retry_at:
            return "retry"
        return "event" if wake.wait(timeout=poll_interval()) else "polling"


def main():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with open(str(STATE) + ".lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        wake = threading.Event()
        threading.Thread(target=listen, args=(wake,), daemon=True).start()
        threading.Thread(target=listen_local, args=(wake, MATCH_QUEUE), daemon=True).start()
        scheduler = SyncScheduler(MATCH_QUEUE)
        trigger = "startup"
        while True:
            # Events arriving during a cycle remain set for the following cycle.
            wake.clear()
            try:
                result = scheduler.run(dry_run=os.environ.get("SHOPPING_SYNC_ENABLED") != "1")
                if result is not None:
                    print("Shopping sync checked (" + trigger + "): " +
                          ", ".join(key + "=" + str(len(result[key])) for key in (
                              "add_alexa", "add_grocy", "remove_alexa", "remove_grocy")),
                          flush=True)
            except Exception as exc:
                # Only our own fixed conflict messages are safe to print.
                # Remote exception strings can contain tokens or private data.
                reason = str(exc) if isinstance(exc, IdentityConflict) else type(exc).__name__
                print("Shopping sync failed: " + reason + "; retry in " + str(int(scheduler.remaining()) + 1) + "s", flush=True)
            trigger = scheduler.wait(wake)


if __name__ == "__main__":
    main()
