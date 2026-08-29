#!/usr/bin/env zsh
# AgentPay-IR v2 — deterministic ESCI (Shopping Queries) download (G052).
# Shallow official clone + Git LFS pull of only shopping_queries_dataset/*.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RAW="$REPO/data/agentpay_ir_v2/raw"
DEST="$RAW/esci-data"
mkdir -p "$RAW"
if [ ! -d "$DEST/.git" ]; then
  git clone --depth 1 https://github.com/amazon-science/esci-data.git "$DEST"
fi
cd "$DEST"
git lfs pull --include="shopping_queries_dataset/*"
shasum -a 256 shopping_queries_dataset/* || true
