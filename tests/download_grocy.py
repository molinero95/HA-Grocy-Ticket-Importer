"""Fetch the pinned upstream release; reject any checksum mismatch before use."""
import argparse
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

VERSION = "4.7.1"
SHA256 = "c4a10e96ed76664baf465e9b27dc7a31aa08c0e3ad876afdfae4f1ff9ab2fc19"
URL = f"https://github.com/grocy/grocy/releases/download/v{VERSION}/grocy_{VERSION}.zip"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    raw = urllib.request.urlopen(URL, timeout=120).read()
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise SystemExit("Grocy release checksum mismatch")
    args.destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(raw)) as package:
        for name in package.namelist():
            if not (args.destination / name).resolve().is_relative_to(args.destination.resolve()):
                raise SystemExit("Unsafe archive member")
        package.extractall(args.destination)
    print(f"Verified Grocy {VERSION}: {SHA256}")
