#!/usr/bin/env python3
"""AgentPay-IR v2 — deterministic source downloads (G049).

Re-downloads the APPROVED sources into data/agentpay_ir_v2/raw/ with pinned
URLs and prints sha256 for each file. Excluded sources (ANLI, WDC Products,
WDC-PAVE) are intentionally absent and listed for provenance.

Usage: services/api/.venv/bin/python scripts/agentpay_ir_v2_downloads/download_all.py
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "data" / "agentpay_ir_v2" / "raw"

SOURCES = {
    "contract-nli.zip": "https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip",
    # ESCI handled by clone_esci.sh (Git LFS shallow clone)
}

EXCLUDED = {
    "anli_v1.0.zip": "EXCLUDED — CC BY-NC 4.0 (non-commercial; unresolved commercial-use status) — see docs/agentpay_ir_v2/LICENSE_MATRIX.md",
    "wdc-products/*.zip": "EXCLUDED — official page: benchmark data must never appear in training corpora",
    "wdc-pave/*.jsonl": "EXCLUDED — no license found (all rights reserved)",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dest = RAW / name
        if not dest.exists():
            print(f"downloading {name} …")
            urllib.request.urlretrieve(url, dest)  # noqa: S310 (pinned official URL)
        print(f"{name}  sha256={sha256(dest)}  bytes={dest.stat().st_size}")
    for name, why in EXCLUDED.items():
        print(f"{name}  {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
