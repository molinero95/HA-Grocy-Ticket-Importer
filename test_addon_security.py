"""Packaging security checks, without Home Assistant access."""
from pathlib import Path
import unittest

ADDON = Path(__file__).resolve().parent / "ha_grocy_ticket_importer"

class AddonSecurityTests(unittest.TestCase):
    def test_config_does_not_mount_entire_home_assistant(self):
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("type: app_config", config)
        self.assertNotIn("type: homeassistant_config", config)
        self.assertNotIn("type: all_app_configs", config)

    def test_run_script_requires_original_import_ledger(self):
        script = (ADDON / "run.sh").read_text(encoding="utf-8")
        self.assertIn('if [ ! -f "$CONFIG_DIR/grocy_imports.sqlite3" ]; then', script)
        self.assertIn('exit 1', script)
        self.assertIn('GROCY_ENV_FILE="$CONFIG_DIR/.env"', script)
        self.assertNotIn('cp "$CONFIG_DIR/.env" /app/.env', script)

if __name__ == "__main__":
    unittest.main()
