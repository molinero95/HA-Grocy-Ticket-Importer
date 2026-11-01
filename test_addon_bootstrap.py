"""Bootstrap regression tests: no real keys, no network or stock writes."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parent / "ha_grocy_ticket_importer" / "addon_bootstrap.py"
spec = importlib.util.spec_from_file_location("addon_bootstrap", MODULE)
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


class BootstrapTests(unittest.TestCase):
    def test_config_requires_keys_and_uses_home_assistant_options(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "options.json"
            file.write_text(json.dumps({"grocy_url": "http://grocy:80/",
                "grocy_api_key": "test-secret", "openai_api_key": "test-openai",
                "grocy_location_id": 2}))
            result = boot.load_config(file)
            self.assertEqual(result["GROCY_URL"], "http://grocy:80")
            self.assertEqual(result["GROCY_LOCATION_ID"], "2")
            self.assertEqual(result["OPENAI_API_KEY"], "test-openai")
            file.write_text(json.dumps({"grocy_url": "http://grocy:80"}))
            with self.assertRaises(ValueError):
                boot.load_config(file)

    def test_voice_defaults_disabled_and_requires_both_skill_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'options.json'
            options={'grocy_url':'http://grocy:80','grocy_api_key':'test','openai_api_key':'test'}
            file.write_text(json.dumps(options))
            self.assertEqual(boot.load_config(file)['ALEXA_SKILL_ENABLED'],'0')
            options['alexa_skill_enabled']=True;file.write_text(json.dumps(options))
            with self.assertRaises(ValueError):boot.load_config(file)
            options.update(alexa_skill_id='amzn1.ask.skill.test',alexa_skill_user_id='amzn1.ask.account.test')
            file.write_text(json.dumps(options));self.assertEqual(boot.load_config(file)['ALEXA_SKILL_ENABLED'],'1')

    def test_new_and_existing_receipt_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "ledger.sqlite3"
            boot.ensure_ledger(file)
            with sqlite3.connect(file) as db:
                db.execute("INSERT INTO receipt_items VALUES (?,?,?,?,?)",
                           ("old-receipt", 1, 7, "imported", "legacy data"))
                db.commit()
            boot.ensure_ledger(file)
            with sqlite3.connect(file) as db:
                rows = db.execute("SELECT receipt_hash, state FROM receipt_items").fetchall()
            self.assertEqual(rows, [("old-receipt", "imported")])

    def test_read_only_alexa_review_starts_without_enabling_remote_sync(self):
        config = {"ALEXA_SHOPPING_LIST_ENTITY": "todo.alexa_shopping",
                  "SHOPPING_SYNC_ENABLED": "0"}
        self.assertTrue(boot.should_start_shopping_worker(config))
        self.assertFalse(boot.should_start_shopping_worker({
            "ALEXA_SHOPPING_LIST_ENTITY": "", "SHOPPING_SYNC_ENABLED": "0"}))
        with patch.object(boot, "load_config", return_value=config), \
             patch.object(boot, "ensure_ledger"), \
             patch.object(boot.subprocess, "run") as nginx, \
             patch.object(boot.subprocess, "Popen") as worker, \
             patch.object(boot.Path, "read_text", return_value='version: "0.16.1"'), \
             patch.object(boot.os, "execvpe", side_effect=RuntimeError("intercepted")), \
             patch.dict(boot.os.environ, {}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "intercepted"):
                boot.main()
            self.assertEqual(worker.call_args.kwargs["env"]["SHOPPING_SYNC_ENABLED"], "0")
        nginx.assert_called_once_with(["nginx"], check=True)
        worker.assert_called_once()
        self.assertEqual(worker.call_args.args[0][1], "/app/shopping_sync_worker.py")

    def test_bootstrap_does_not_run_services_when_config_missing(self):
        with patch.object(boot, "load_config", side_effect=ValueError("missing")), \
             patch.object(boot.subprocess, "run") as run:
            self.assertEqual(boot.main(), 1)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
