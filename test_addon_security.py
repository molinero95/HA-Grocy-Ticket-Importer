"""Packaging and credential-handling checks without Home Assistant access."""
from pathlib import Path
import unittest

ADDON = Path(__file__).resolve().parent / "ha_grocy_ticket_importer"


class AddonSecurityTests(unittest.TestCase):
    def test_container_contains_every_imported_application_module(self):
        import ast
        docker = (ADDON / "Dockerfile").read_text()
        root = ADDON.parent
        # Validate the COPY manifest independently of byte-identical source tests.
        import shlex
        import fnmatch
        copied = set()
        for line in docker.splitlines():
            if line.startswith("COPY ") and "--from=" not in line:
                for pattern in shlex.split(line)[1:-1]:
                    copied.update(p.name for p in ADDON.glob(pattern) if p.is_file())
        for module in root.glob("*.py"):
            if module.name.startswith("test_"):
                continue
            for node in ast.walk(ast.parse(module.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    dependency = node.module.split(".")[0] + ".py"
                    if (root / dependency).is_file():
                        self.assertIn(dependency, copied, f"Missing runtime dependency from {module.name}")
        self.assertIn("COPY --from=frontend-build /build/dist /app/frontend_dist", docker)

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
