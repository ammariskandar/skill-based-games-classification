#!/usr/bin/env bash
# ==============================================================================
# scripts/verify-ingress-boundary.sh
# Verifies the edge proxy and internal routing boundaries for MyGameDNA.
# Fails fast (exit 1) if any security assumption is violated.
#
#   usage: verify-ingress-boundary.sh [PUBLIC_BASE_URL] [INTERNAL_API_URL]
#
# Public ingress must terminate /api/v1/* (never forward to Django); the
# Django Admin must be reachable; the internal Astro-BFF API must answer on
# the loopback/private network.  See SBGC-105 / SBGC-106.
# ==============================================================================
set -euo pipefail

PUBLIC_BASE_URL="${1:-https://mygamedna.com}"
INTERNAL_API_URL="${2:-http://127.0.0.1:8000}"
# SBGC-106 — obfuscated admin path (env-tunable; matches Django ADMIN_URL_PATH).
ADMIN_PATH="${ADMIN_URL_PATH:-hiddenworld/}"

echo "=================================================="
echo "Starting Ingress Security Boundary Verification"
echo "Public Ingress:   ${PUBLIC_BASE_URL}"
echo "Internal Ingress: ${INTERNAL_API_URL}"
echo "Admin Path:       ${ADMIN_PATH}"
echo "=================================================="

# ------------------------------------------------------------------------------
# Test 1: External Direct API Access MUST Be Blocked (403 or 404)
# ------------------------------------------------------------------------------
echo -n "[Test 1/5] External GET ${PUBLIC_BASE_URL}/api/v1/games/ is blocked... "
EXT_API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${PUBLIC_BASE_URL}/api/v1/games/" || true)
if [[ "${EXT_API_CODE}" =~ ^(403|404)$ ]]; then
  echo "PASSED (HTTP ${EXT_API_CODE})"
else
  echo "FAILED!"
  echo "CRITICAL SECURITY BREACH: External /api/v1/ is publicly reachable! Returned HTTP ${EXT_API_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 2: External Direct Auth API Access MUST Be Blocked (403 or 404)
# ------------------------------------------------------------------------------
echo -n "[Test 2/5] External POST ${PUBLIC_BASE_URL}/api/v1/auth/login is blocked... "
EXT_AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${PUBLIC_BASE_URL}/api/v1/auth/login" || true)
if [[ "${EXT_AUTH_CODE}" =~ ^(403|404)$ ]]; then
  echo "PASSED (HTTP ${EXT_AUTH_CODE})"
else
  echo "FAILED!"
  echo "CRITICAL SECURITY BREACH: External /api/v1/auth/login is reachable! Returned HTTP ${EXT_AUTH_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 3a: Standard /admin/ MUST NOT expose the Django Admin (404)
# ------------------------------------------------------------------------------
echo -n "[Test 3a/5] External GET ${PUBLIC_BASE_URL}/admin/ is 404... "
STD_ADMIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${PUBLIC_BASE_URL}/admin/" || true)
if [[ "${STD_ADMIN_CODE}" =~ ^(404)$ ]]; then
  echo "PASSED (HTTP 404)"
else
  echo "FAILED! Standard /admin/ exposed! Returned HTTP ${STD_ADMIN_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 3b: Obfuscated admin path reaches Django authentication (200 or 302)
# ------------------------------------------------------------------------------
echo -n "[Test 3b/5] External GET ${PUBLIC_BASE_URL}/${ADMIN_PATH}login/ reaches Django Admin... "
OBF_ADMIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${PUBLIC_BASE_URL}/${ADMIN_PATH}login/" || true)
if [[ "${OBF_ADMIN_CODE}" =~ ^(200|302)$ ]]; then
  echo "PASSED (HTTP ${OBF_ADMIN_CODE})"
else
  echo "FAILED! Obfuscated admin route unreachable. Returned HTTP ${OBF_ADMIN_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 4: Internal API Access from Astro BFF Subnet MUST Succeed
# ------------------------------------------------------------------------------
echo -n "[Test 4/5] Internal GET ${INTERNAL_API_URL}/api/v1/games/ succeeds... "
INT_API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${INTERNAL_API_URL}/api/v1/games/" || true)
if [[ "${INT_API_CODE}" =~ ^(200)$ ]]; then
  echo "PASSED (HTTP ${INT_API_CODE})"
else
  echo "FAILED!"
  echo "Internal API unreachable from BFF network. Returned HTTP ${INT_API_CODE}"
  exit 1
fi

echo "=================================================="
echo "All 5 Ingress Boundary Tests Passed Successfully."
echo "=================================================="
