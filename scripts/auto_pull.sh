#!/usr/bin/env bash
# One-shot refresh: pull latest FAA data, update DB/JSON, refresh contacts list.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 heli_tracker.py "$@"
python3 scripts/find_contacts.py || true
echo "Done. Open the dashboard with: python3 serve.py"
