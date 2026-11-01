"""Run the unmodified, SHA-verified Grocy release with disposable local data."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request


class GrocyInstance:
    def __init__(self, distribution, php, port=9888):
        self.distribution = Path(distribution).resolve()
        self.php = php
        self.port = port
        self.directory = tempfile.TemporaryDirectory(prefix="despensa-integration-")
        self.data = Path(self.directory.name)
        (self.data / "grocy").mkdir()
        (self.data / "grocy" / "config.php").write_text(f"<?php\nSetting('DISABLE_AUTH', true);\nSetting('DEFAULT_LOCALE', 'en');\nSetting('BASE_URL', 'http://127.0.0.1:{self.port}');\n")
        self.process = None
        self.log = (self.data / "server.log").open("w")

    def start(self):
        root = str(self.distribution / "public")
        if "frankenphp" in Path(self.php).name:
            command = [self.php, "php-server", "--root", root, "--listen", f"127.0.0.1:{self.port}"]
        else:
            command = [self.php, "-S", f"127.0.0.1:{self.port}", "-t", root, str(self.distribution / "public" / "index.php")]
        self.process = subprocess.Popen(command, env={**os.environ, "GROCY_DATAPATH": str(self.data / "grocy")}, stdout=self.log, stderr=self.log)
        last_error = ""
        for _ in range(100):
            try:
                # Grocy runs its own database migrations on the root route.
                urllib.request.urlopen(self.url + "/", timeout=15).close()
                self.http("GET", "objects/quantity_units")
                return self
            except Exception as exc:
                last_error = str(exc) + (exc.read().decode()[:1000] if isinstance(exc, urllib.error.HTTPError) else "")
                if self.process.poll() is not None:
                    break
                time.sleep(.1)
        raise RuntimeError("Isolated Grocy startup failed: " + last_error + (self.data / "server.log").read_text()[-2000:])

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def http(self, method, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(self.url + "/api/" + path, data=data, method=method, headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Grocy fixture HTTP {exc.code} {path}: " + exc.read().decode()[:800]) from exc

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=15)
            self.process = None

    def close(self):
        self.stop()
        self.log.close()
        self.directory.cleanup()

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
