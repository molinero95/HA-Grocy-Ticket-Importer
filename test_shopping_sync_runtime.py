import tempfile
import unittest
from pathlib import Path

from shopping_sync_runtime import load_baseline, reconcile, save_baseline, SyncConflict


class RuntimeTests(unittest.TestCase):
    def test_atomic_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            self.assertIsNone(load_baseline(path))
            save_baseline(path, ["pan", "leche", "pan"])
            self.assertEqual(load_baseline(path), ["leche", "pan"])

    def test_dry_run_no_writes(self):
        self.assertEqual(reconcile(["Pan"], [], None)["add_grocy"], ["Pan"])

    def test_missing_callback_fails_before_writes(self):
        with self.assertRaises(SyncConflict):
            reconcile(["Pan"], [], None, dry_run=False)

    def test_delete_propagates_once(self):
        calls = []
        result = reconcile([], ["Pan"], ["pan"], dry_run=False,
                           remove_grocy=lambda name: calls.append(name))
        self.assertEqual(calls, ["Pan"])
        self.assertEqual(result["next_baseline"], [])


if __name__ == "__main__":
    unittest.main()
