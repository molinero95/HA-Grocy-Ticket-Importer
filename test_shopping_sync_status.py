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
