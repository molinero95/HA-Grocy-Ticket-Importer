"""Health reporting never leaks private exception strings or changes checkpoints."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from shopping_sync_status import record, snapshot
from shopping_identity_sync import IdentityConflict

class SyncStatusTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'queue.sqlite3'
        env = patch.dict(os.environ, {'ALEXA_SHOPPING_LIST_ENTITY': 'todo.test', 'SHOPPING_SYNC_ENABLED': '1'})
        env.start(); self.addCleanup(env.stop)

    def test_health_missing_disabled_and_unconfigured(self):
        self.assertEqual(snapshot(self.path)['state'], 'unknown')
        with patch.dict(os.environ, {'SHOPPING_SYNC_ENABLED': '0'}):
            self.assertEqual(snapshot(self.path)['state'], 'disabled')
        with patch.dict(os.environ, {'ALEXA_SHOPPING_LIST_ENTITY': ''}):
            self.assertEqual(snapshot(self.path)['state'], 'unconfigured')

    def test_error_is_sanitized_and_stale_worker_is_detected(self):
        record(self.path, dry_run=False, error=RuntimeError('secret credential and private list'))
        self.assertNotIn('secret', Path(str(self.path)+'.sync-status.json').read_text())
        self.assertEqual(snapshot(self.path)['reason'], 'unavailable')
        record(self.path, dry_run=False, error=IdentityConflict('A Grocy note conflicts with a canonical product'))
        self.assertEqual(snapshot(self.path)['reason'], 'note_conflict')
        with patch('shopping_sync_status.time.time', return_value=10**12):
            self.assertEqual(snapshot(self.path)['state'], 'stale')

    def test_success_keeps_last_verified_time_through_error_and_dry_run(self):
        record(self.path, dry_run=False)
        saved=json.loads(Path(str(self.path)+'.sync-status.json').read_text())['last_success_at']
        record(self.path, dry_run=True)
        record(self.path, dry_run=False, error=RuntimeError())
        self.assertEqual(json.loads(Path(str(self.path)+'.sync-status.json').read_text())['last_success_at'], saved)

    def test_status_io_failure_does_not_change_worker_outcome(self):
        with patch('shopping_sync_status.tempfile.mkstemp', side_effect=OSError()):
            record(self.path, dry_run=False)

    def test_fixed_identity_details_and_last_success_are_exposed_without_raw_exceptions(self):
        record(self.path, dry_run=False)
        record(self.path, dry_run=False, error=IdentityConflict('Multiple Alexa items resolve to the same identity'))
        health = snapshot(self.path)
        self.assertEqual(health['detail_code'], 'duplicate_alexa_identity')
        self.assertIsInstance(health['last_success_at'], (int, float))
        record(self.path, dry_run=False, error=RuntimeError('private provider exception'))
        health = snapshot(self.path)
        self.assertIsNone(health['detail_code'])
        self.assertNotIn('private', json.dumps(health))

    def test_candidate_conflict_reports_only_product_ids_and_success_clears_them(self):
        record(self.path, dry_run=False, error=IdentityConflict('Selected product is no longer a valid candidate', product_ids=(7, 7, -1, True)))
        self.assertEqual(snapshot(self.path)['affected_product_ids'], [7])
        record(self.path, dry_run=False)
        self.assertEqual(snapshot(self.path)['affected_product_ids'], [])


    def test_exponential_pause_persists_safely_and_is_not_reported_as_stale(self):
        from shopping_sync_status import retry_state
        now = 10000
        with patch('shopping_sync_status.time.time', side_effect=lambda: now):
            for delay in [120, 240, 480, 960, 1800, 1800]:
                record(self.path, dry_run=False, error=RuntimeError('private token'))
                health = snapshot(self.path)
                self.assertTrue(health['paused'])
                self.assertEqual(health['next_retry_at'], now + delay)
                now += delay - 1
                self.assertEqual(snapshot(self.path)['state'], 'error')
                self.assertTrue(snapshot(self.path)['paused'])
                now += 1
                self.assertFalse(snapshot(self.path)['paused'])
            record(self.path, dry_run=False)
            self.assertEqual(retry_state(self.path)['consecutive_failures'], 0)
            self.assertFalse(snapshot(self.path)['paused'])
            self.assertIsNone(snapshot(self.path)['next_retry_at'])
            record(self.path, dry_run=False, error=RuntimeError())
            self.assertEqual(snapshot(self.path)['next_retry_at'], now + 120)
        self.assertNotIn('private', Path(str(self.path)+'.sync-status.json').read_text())

    def test_corrupt_or_unbounded_pause_cannot_suspend_worker_indefinitely(self):
        from shopping_sync_status import retry_state
        for checked, retry, count in [(0, 10**12, 1), (10**12, 10**12+120, 1),
                                      (float('nan'), 120, 1), (0, float('inf'), 1),
                                      (0, 120, True), (10**400, 10**400, 1)]:
            Path(str(self.path)+'.sync-status.json').write_text(json.dumps({
                'state': 'error', 'checked_at': checked, 'next_retry_at': retry,
                'consecutive_failures': count, 'dry_run': False}))
            self.assertEqual(retry_state(self.path)['next_retry_at'], 0)
