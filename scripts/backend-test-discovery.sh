#!/usr/bin/env bash
# SBGC-44 — backend test discovery audit.
# Thin launcher for config.discovery.audit_discovery.
# Exits 0 when no structural defects are found.
set -euo pipefail

APPS_DIR="${APPS_DIR_OVERRIDE:-$(dirname "$0")/../apps/backend}"

exec flatpak-spawn --host "$APPS_DIR/.venv/bin/python" -c "
import os, sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings.test'
os.environ['DJANGO_SKIP_DOTENV'] = '1'
sys.path.insert(0, '$APPS_DIR')

import django
django.setup()

from config.discovery import audit_discovery

report = audit_discovery('$APPS_DIR')
print(f'Total discovered: {report.total}')
print()
print('By module:')
for mod, count in sorted(report.by_module.items()):
    print(f'  {mod}: {count}')

if report.duplicate_ids:
    print()
    print('DUPLICATE TEST IDs:')
    for d in report.duplicate_ids:
        print(f'  {d}')

if report.import_errors:
    print()
    print('IMPORT ERRORS:')
    for err in report.import_errors:
        print(f'  {err}')

if report.empty_modules:
    print()
    print('EMPTY TEST MODULES:')
    for m in report.empty_modules:
        print(f'  {m}')

if not report.success:
    print()
    print('Discovery audit FAILED: structural defects found.')
    sys.exit(1)

print()
print('Discovery audit passed.')
"
