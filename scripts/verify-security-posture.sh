#!/usr/bin/env bash
# ==============================================================================
# scripts/verify-security-posture.sh
# End-to-end security posture validation for MyGameDNA — SBGC-109.
# Fails fast (exit 1) on any posture violation.
#
# Six gates:
#   [1/6] backend vulnerability audit (pip-audit)
#   [2/6] frontend vulnerability audit (npm audit --audit-level=high)
#   [3/6] tracked-repo secret / owner-identifier / certificate scan
#   [4/6] Django migration-drift check (makemigrations --check)
#   [5/6] Django configuration-only deployment check (--deploy, no DB)
#   [6/6] Django automated security test suite (security.tests)
#
# Requires the backend venv at apps/backend/.venv (see README prerequisites)
# and an installed frontend workspace (npm install).
# ==============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/apps/backend"
PYTHON="$BACKEND_DIR/.venv/bin/python"
PIP_AUDIT="$BACKEND_DIR/.venv/bin/pip-audit"
MANAGE="$BACKEND_DIR/manage.py"
TMP_LOG="$(mktemp)"
trap 'rm -f "$TMP_LOG"' EXIT

echo "=================================================="
echo "Starting MyGameDNA Security Posture Verification"
echo "=================================================="

# ------------------------------------------------------------------------------
# Gate helpers: print PASSED, or print FAILED + the tail of captured output.
# ------------------------------------------------------------------------------
_gate_passed() { echo "PASSED"; }

_gate_failed() {
  echo "FAILED!"
  echo "----- captured output (last 30 lines) -----"
  tail -n 30 "$TMP_LOG" || true
  exit 1
}

# _run <command...> — runs the command, hiding output unless it fails.
_run() {
  if "$@" > "$TMP_LOG" 2>&1; then
    _gate_passed
  else
    _gate_failed
  fi
}

# ------------------------------------------------------------------------------
# [1/6] Backend dependency vulnerability audit
# ------------------------------------------------------------------------------
echo -n "[1/6] Running backend vulnerability audit (pip-audit)... "
_run "$PIP_AUDIT" --desc on

# ------------------------------------------------------------------------------
# [2/6] Frontend dependency vulnerability audit (high/critical block delivery)
# ------------------------------------------------------------------------------
echo -n "[2/6] Running frontend vulnerability audit (npm audit)... "
_run npm audit --audit-level=high --workspace=apps/frontend

# ------------------------------------------------------------------------------
# [3/6] Tracked-repo secret scan
#   - development owner identifiers (SBGC-109 scrub target);
#   - private-key / certificate material;
#   - certificate/private-key file extensions.
# context.md is the immutable project journal and may name the former fixture;
# this script naturally contains the patterns it scans for.
# ------------------------------------------------------------------------------
echo -n "[3/6] Auditing tracked files for secrets and owner identifiers... "
_EXCLUDES=(
  ':(exclude)context.md'
  ':(exclude)scripts/verify-security-posture.sh'
)

matches="$(
  git -C "$REPO_ROOT" grep -I -n -E -e "thenamesammaris" -- "${_EXCLUDES[@]}" 2>&1 || true
)"
if [[ -n "$matches" ]]; then
  echo "FAILED!"
  echo "ERROR: development owner identifier detected in tracked files:"
  echo "$matches"
  exit 1
fi

matches="$(
  git -C "$REPO_ROOT" grep -I -n -E -e "-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----" -- "${_EXCLUDES[@]}" 2>&1 || true
)"
if [[ -n "$matches" ]]; then
  echo "FAILED!"
  echo "ERROR: private-key material detected in tracked files:"
  echo "$matches"
  exit 1
fi

cert_files="$(
  git -C "$REPO_ROOT" ls-files | grep -E '\.(pem|key|p12|pfx|p8|cer|crt|jks|keystore)$' || true
)"
if [[ -n "$cert_files" ]]; then
  echo "FAILED!"
  echo "ERROR: certificate/private-key files tracked in git:"
  echo "$cert_files"
  exit 1
fi
_gate_passed

# ------------------------------------------------------------------------------
# [4/6] Django migration-drift check
# ------------------------------------------------------------------------------
echo -n "[4/6] Verifying zero pending model migrations... "
_run "$PYTHON" "$MANAGE" makemigrations --check --settings=config.settings.test

# ------------------------------------------------------------------------------
# [5/6] Django configuration-only deployment check (no database connection)
# ------------------------------------------------------------------------------
echo -n "[5/6] Executing configuration deployment check... "
_run bash "$REPO_ROOT/scripts/backend-deploy-check.sh"

# ------------------------------------------------------------------------------
# [6/6] Django automated security test suite
# ------------------------------------------------------------------------------
echo -n "[6/6] Executing automated security test suite... "
_run "$PYTHON" "$MANAGE" test security.tests --settings=config.settings.test

echo "=================================================="
echo "Security Posture Verified: All 6 Gates Passed."
echo "=================================================="
