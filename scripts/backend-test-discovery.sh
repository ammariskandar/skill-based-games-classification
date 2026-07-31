#!/usr/bin/env bash
# SBGC-44 — backend test discovery audit.
# Runs manage.py test at verbosity 2 and reports discovered tests.
set -euo pipefail

APPS_DIR="$(dirname "$0")/../apps/backend"

flatpak-spawn --host "$APPS_DIR/.venv/bin/python" \
  "$APPS_DIR/manage.py" test apps/backend \
  --settings=config.settings.test --noinput --verbosity 2 2>&1 | \
  "$APPS_DIR/.venv/bin/python" -c "
import sys, re

by_module = {}
total = 0
ok = False

for line in sys.stdin:
    line = line.rstrip()
    m = re.match(r'^Found (\d+) test', line)
    if m:
        total = int(m.group(1))
    # test_name (module.Class.method)
    m2 = re.match(r'^test_\w+ \(([\w.]+)\.\w+\.\w+\)', line)
    if m2:
        mod = m2.group(1)
        # Normalise: strip 'apps.backend.' or 'apps/backend/' prefix
        mod = re.sub(r'^apps\.backend\.', '', mod)
        by_module[mod] = by_module.get(mod, 0) + 1
    if line.strip() == 'OK':
        ok = True

print(f'Total discovered: {total}')
print()
print('By module:')
for mod in sorted(by_module):
    print(f'  {mod}: {by_module[mod]}')

if not ok:
    print()
    print('Suite FAILED.')
    sys.exit(1)

print()
print('Discovery audit passed.')
" 2>&1
