"""Download the trained models and processed data, so you can run the website without training.

They are attached to the GitHub release (they are too large to keep in the repository itself).
Usage:  python scripts/download_models.py        (about 140 MB)
Only the Python standard library is used.

The files are derived from the CC BY-NC-SA 4.0 dataset (Iphar et al. 2024) and carry the same
licence: non-commercial use, share alike, with attribution.
"""
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "v1.0.0"
ASSET = f"harborwise-models-{VERSION}.tar.gz"
URL = f"https://github.com/vAudioso/harborwise/releases/download/{VERSION}/{ASSET}"
SHA256 = "9c7934b6a6044023893d39590138a18b916a23b2cf1c3f16f82350e839100fac"
ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("models/", "data/processed/")


def fetch(url: str, dest: Path):
    """Download url to dest. Falls back to curl when Python has no SSL certificates
    (common with the python.org installer on macOS)."""
    try:
        with urllib.request.urlopen(url) as r, open(dest, "wb") as out:
            shutil.copyfileobj(r, out)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" not in str(e) or not shutil.which("curl"):
            raise
        subprocess.run(["curl", "-fsSL", "-o", str(dest), url], check=True)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / ASSET
        print(f"Downloading trained models and processed data ({VERSION}, about 140 MB) ...", flush=True)
        fetch(URL, path)
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        if h.hexdigest() != SHA256:
            sys.exit(f"Download is corrupted (sha256 {h.hexdigest()}). Please try again.")
        with tarfile.open(path) as tar:
            members = []
            for m in tar.getmembers():
                p = Path(m.name)
                # Only plain files under models/ or data/processed/; nothing absolute or with "..".
                if m.isfile() and not p.is_absolute() and ".." not in p.parts and m.name.startswith(ALLOWED):
                    members.append(m)
            for m in members:
                dest = ROOT / m.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(m) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print(f"Done: {len(members)} files into models/ and data/processed/. Start the website with `make app`.")


if __name__ == "__main__":
    main()
