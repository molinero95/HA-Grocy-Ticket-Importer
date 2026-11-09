"""Worker integration tests without network access."""
import unittest
from unittest.mock import patch

import shopping_sync_worker as worker
from shopping_identity_sync import IdentityConflict


class ShoppingWorkerTests(unittest.TestCase):
    def test_ambiguity_queue_precedes_identity_dry_run(self):
        events = []
        products = [{"id": 1, "name": "Arroz basmati"}]
        result = {"add_alexa": [], "add_grocy": [], "remove_alexa": [],
                  "remove_grocy": [], "next_baseline": [], "next_bindings": {}}
        def record_queue(path, names, catalog, rows):
            events.append("queue")
            self.assertEqual(names, ["Arroz"])
            self.assertEqual(catalog, products)
        def record_reconcile(*args, **kwargs):
            events.append("reconcile")
            self.assertTrue(kwargs["dry_run"])
            return result
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=products), \
             patch.object(worker, "refresh_matches", side_effect=record_queue), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", side_effect=record_reconcile), \
             patch.object(worker, "save_identity_state") as save:
            self.assertEqual(worker.run_once(dry_run=True), result)
        self.assertEqual(events, ["queue", "reconcile"])
        save.assert_not_called()

    def test_failed_catalog_audit_prevents_sync_mutations(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=None), \
             patch.object(worker, "reconcile_identity") as reconcile:
            with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
                worker.run_once(dry_run=False)
        reconcile.assert_not_called()

    def test_stale_manual_selection_blocks_all_writes(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=[{"id": 1, "name": "Arroz basmati"}]), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[
                 {"key": "arroz", "selected_product_id": 2}]), \
             patch.object(worker, "reconcile_identity") as reconcile:
            with self.assertRaisesRegex(IdentityConflict, "renewed review"):
                worker.run_once(dry_run=False)
        reconcile.assert_not_called()

    def test_verified_run_saves_v2_checkpoint(self):
        products = [{"id": 2, "name": "Arroz basmati"}]
        grocy_rows = [("Arroz basmati", {"id": 7, "product_id": 2, "amount": 1})]
        result = {"add_alexa": [], "add_grocy": [], "remove_alexa": [],
                  "remove_grocy": [], "next_baseline": ["p:2"], "next_bindings": {"arroz": 2}}
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=grocy_rows), \
             patch.object(worker, "grocy", return_value=products), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={"arroz": {"product_id": 2}}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", return_value=result), \
             patch.object(worker, "save_identity_state") as save:
            self.assertEqual(worker.run_once(dry_run=False), result)
        save.assert_called_once_with(worker.STATE_V2, ["p:2"], {"arroz": 2})

    def test_partial_failure_never_advances_checkpoint(self):
        with patch.object(worker, "ha_todo_items", return_value=["Arroz"]), \
             patch.object(worker, "grocy_entries", return_value=[]), \
             patch.object(worker, "grocy", return_value=[{"id": 2, "name": "Arroz basmati"}]), \
             patch.object(worker, "refresh_matches"), \
             patch.object(worker, "resolved_choices", return_value={}), \
             patch.object(worker, "pending_matches", return_value=[]), \
             patch.object(worker, "load_identity_state", return_value=None), \
             patch.object(worker, "reconcile_identity", side_effect=RuntimeError("write failed")), \
             patch.object(worker, "save_identity_state") as save:
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                worker.run_once(dry_run=False)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class SyncSchedulerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'queue.sqlite3'
        self.now = 10000
        clock = patch('shopping_sync_worker.time.time', side_effect=lambda: self.now)
        clock.start(); self.addCleanup(clock.stop)
        env = patch.dict('os.environ', {'SHOPPING_SYNC_INTERVAL_SECONDS': '30'})
        env.start(); self.addCleanup(env.stop)

    def test_event_storm_never_retries_early_and_success_resets_backoff(self):
        scheduler = worker.SyncScheduler(self.path)
        with patch.object(worker, 'run_once', side_effect=RuntimeError('private')) as run:
            for delay in [120, 240, 480, 960, 1800, 1800]:
                before = run.call_count
                with self.assertRaises(RuntimeError): scheduler.run(dry_run=False)
                self.assertEqual(scheduler.remaining(), delay)
                for _ in range(20):
                    self.assertIsNone(scheduler.run(dry_run=False))
                self.assertEqual(run.call_count, before + 1)
                from unittest.mock import Mock
                started = self.now
                wake = Mock()
                def wait(timeout):
                    self.now += timeout
                    return True  # A continuous event stream still cannot bypass the deadline.
                wake.wait.side_effect = wait
                self.assertEqual(scheduler.wait(wake), 'retry')
                self.assertEqual(self.now - started, delay)
                self.assertEqual(run.call_count, before + 1)
                self.now = started
                self.now += delay - 1
                self.assertIsNone(scheduler.run(dry_run=False))
                self.now += 1
        with patch.object(worker, 'run_once', return_value={'ok': True}) as run:
            self.assertEqual(scheduler.run(dry_run=False), {'ok': True})
            self.assertEqual(scheduler.remaining(), 0)
            self.assertEqual(scheduler.failures, 0)
            run.assert_called_once_with(dry_run=False, failure_count=7, blocking=False)
        with patch.object(worker, 'run_once', side_effect=RuntimeError()):
            with self.assertRaises(RuntimeError): scheduler.run(dry_run=False)
            self.assertEqual(scheduler.remaining(), 120)

    def test_restart_honors_persisted_pause_and_due_retry_reads_fresh_state(self):
        from shopping_sync_status import record
        record(self.path, dry_run=False, error=IdentityConflict('Multiple Alexa items resolve to the same identity'))
        self.now += 10
        scheduler = worker.SyncScheduler(self.path)
        with patch.object(worker, 'run_once', return_value={}) as run:
            self.assertIsNone(scheduler.run(dry_run=False))
            self.assertEqual(scheduler.remaining(), 110)
            run.assert_not_called()
            self.now += 110
            self.assertEqual(scheduler.run(dry_run=False), {})
            run.assert_called_once_with(dry_run=False, failure_count=2, blocking=False)

    def test_storage_failure_does_not_disable_in_memory_backoff(self):
        scheduler = worker.SyncScheduler(self.path)
        with patch.object(worker, '_run_once', side_effect=RuntimeError('token secret')) as run, \
             patch('shopping_sync_status.tempfile.mkstemp', side_effect=OSError()):
            with self.assertRaises(RuntimeError): scheduler.run(dry_run=True)
            self.assertEqual(scheduler.remaining(), 120)
            self.assertIsNone(scheduler.run(dry_run=True))
            run.assert_called_once()
            self.now += 120
            with self.assertRaises(RuntimeError): scheduler.run(dry_run=True)
            self.assertEqual(scheduler.remaining(), 240)

    def test_normal_events_and_configured_longer_interval_are_preserved(self):
        from unittest.mock import Mock
        scheduler = worker.SyncScheduler(self.path)
        wake = Mock(); wake.wait.return_value = True
        self.assertEqual(scheduler.wait(wake), 'event')
        wake.wait.assert_called_once_with(timeout=30)
        with patch.dict('os.environ', {'SHOPPING_SYNC_INTERVAL_SECONDS': '3600'}), \
             patch.object(worker, 'run_once', side_effect=RuntimeError()):
            with self.assertRaises(RuntimeError): scheduler.run(dry_run=False)
            self.assertEqual(scheduler.remaining(), 3600)


    def test_explicit_manual_cycle_replaces_a_sleeping_workers_schedule(self):
        from shopping_sync_status import record
        env = {'SHOPPING_SYNC_ENABLED': '1', 'ALEXA_SHOPPING_LIST_ENTITY': 'todo.test'}
        with patch.dict('os.environ', env):
            record(self.path, dry_run=False, error=RuntimeError())
            scheduler = worker.SyncScheduler(self.path)
            self.assertEqual(scheduler.remaining(), 120)
            self.now += 5
            record(self.path, dry_run=False, error=RuntimeError())
            scheduler.refresh()
            self.assertEqual(scheduler.remaining(), 240)
            self.assertEqual(scheduler.failures, 2)
            self.now += 5
            record(self.path, dry_run=False)
            scheduler.refresh()
            self.assertEqual(scheduler.remaining(), 0)
            self.assertEqual(scheduler.failures, 0)


    def test_scheduled_cycle_does_not_wait_behind_or_compete_with_manual_cycle(self):
        scheduler = worker.SyncScheduler(self.path)
        with patch.object(worker, 'run_once', side_effect=BlockingIOError()) as run:
            self.assertIsNone(scheduler.run(dry_run=False))
            self.assertEqual(scheduler.failures, 0)
            self.assertEqual(scheduler.remaining(), 0)
            run.assert_called_once_with(dry_run=False, failure_count=1, blocking=False)
