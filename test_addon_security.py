"""Packaging and credential-handling checks without Home Assistant access."""
from pathlib import Path
import unittest

ADDON = Path(__file__).resolve().parent / "ha_grocy_ticket_importer"


class AddonSecurityTests(unittest.TestCase):
    def test_config_uses_isolated_persistent_storage(self):
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("type: app_config", config)
        self.assertNotIn("type: homeassistant_config", config)
        self.assertNotIn("type: all_app_configs", config)

    def test_native_ha_options_are_configured_without_embedded_secrets(self):
        config = (ADDON / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("grocy_api_key: \"password\"", config)
        self.assertIn("openai_api_key: \"password\"", config)
        self.assertIn("grocy_url: \"url\"", config)
        self.assertNotIn("OPENAI_API_KEY=", config)
        self.assertNotIn("GROCY_API_KEY=", config)

    def test_bootstrap_uses_ha_options_and_preserves_ledger(self):
        startup = (ADDON / "run.sh").read_text(encoding="utf-8")
        bootstrap = (ADDON / "addon_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("/app/addon_bootstrap.py", startup)
        self.assertIn("/data/options.json", bootstrap)
        self.assertIn("CREATE TABLE IF NOT EXISTS receipt_items", bootstrap)
        self.assertNotIn("GROCY_ENV_FILE=", startup)
        self.assertNotIn("cp \"$CONFIG_DIR/.env\"", startup)


if __name__ == "__main__":
    unittest.main()
