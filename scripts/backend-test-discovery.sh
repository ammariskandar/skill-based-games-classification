#!/usr/bin/env bash
# SBGC-44 — backend test discovery audit.
# Invokes config.discovery via the project virtual-environment Python.
# Exits 0 when no structural defects are found.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PYTHONPATH="$REPO_ROOT/apps/backend"
export DJANGO_SETTINGS_MODULE="config.settings.test"

exec "$REPO_ROOT/apps/backend/.venv/bin/python3" -m config.discovery
