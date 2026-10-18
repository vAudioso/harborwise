"""Download the 2019 Caribbean AIS dataset into data/raw/.

Source: Iphar et al., "Port calls and vessel trajectory dataset in the Caribbean with accurate
port quays survey", Zenodo record 10380638 v1.1.0 (DOI 10.5281/zenodo.10380638), CC BY-NC-SA 4.0.

Usage:  python scripts/download_data.py          (about 67 MB download, 300 MB unpacked)
Only the Python standard library is used, so this works before `make setup`.
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

URL = "https://zenodo.org/api/records/10380638/files/CSV.zip/content"
MD5 = "a260ec8776b456dc8c7d30acffaad4b7"
FILES = ["areapresence.csv", "berths.csv", "port_traffic.csv", "portcalls.csv", "ports.csv",
         "segments_port2port.csv", "segments_port2territory.csv", "trajectories.csv",
         "ungt_cont_throughput.csv", "ungt_country_portcalls.csv", "ungt_country_portstats.csv",
         "vesseltype_enriched.csv", "vesseltype_original.csv"]
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


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
    RAW.mkdir(parents=True, exist_ok=True)
    missing = [f for f in FILES if not (RAW / f).exists()]
    if not missing:
        print(f"All {len(FILES)} CSV files are already in {RAW}. Nothing to do.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        zpath = Path(tmp) / "CSV.zip"
        print(f"Downloading the dataset from Zenodo (about 67 MB) ...", flush=True)
        fetch(URL, zpath)
        digest = hashlib.md5(zpath.read_bytes()).hexdigest()
        if digest != MD5:
            sys.exit(f"Download is corrupted (md5 {digest}, expected {MD5}). Please try again.")
        with zipfile.ZipFile(zpath) as z:
            for member in z.infolist():
                name = Path(member.filename).name  # flatten "CSV/x.csv"; ignore any other path
                if name in FILES:
                    with z.open(member) as src, open(RAW / name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
    got = [f for f in FILES if (RAW / f).exists()]
    print(f"Done: {len(got)}/{len(FILES)} CSV files in {RAW}")
    print("Dataset licence: CC BY-NC-SA 4.0 (non-commercial, share alike). Cite: Iphar et al., Data in Brief (2024).")


if __name__ == "__main__":
    main()
