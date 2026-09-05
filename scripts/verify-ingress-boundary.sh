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
# the loopback/private network.  See SBGC-105.
# ==============================================================================
set -euo pipefail

PUBLIC_BASE_URL="${1:-https://mygamedna.com}"
INTERNAL_API_URL="${2:-http://127.0.0.1:8000}"

echo "=================================================="
echo "Starting Ingress Security Boundary Verification"
echo "Public Ingress:   ${PUBLIC_BASE_URL}"
echo "Internal Ingress: ${INTERNAL_API_URL}"
echo "=================================================="

# ------------------------------------------------------------------------------
# Test 1: External Direct API Access MUST Be Blocked (403 or 404)
# ------------------------------------------------------------------------------
echo -n "[Test 1/4] External GET ${PUBLIC_BASE_URL}/api/v1/games/ is blocked... "
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
echo -n "[Test 2/4] External POST ${PUBLIC_BASE_URL}/api/v1/auth/login is blocked... "
EXT_AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "${PUBLIC_BASE_URL}/api/v1/auth/login" || true)
if [[ "${EXT_AUTH_CODE}" =~ ^(403|404)$ ]]; then
  echo "PASSED (HTTP ${EXT_AUTH_CODE})"
else
  echo "FAILED!"
  echo "CRITICAL SECURITY BREACH: External /api/v1/auth/login is reachable! Returned HTTP ${EXT_AUTH_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 3: External Admin Route MUST Reach Django Authentication (200 or 302)
# ------------------------------------------------------------------------------
echo -n "[Test 3/4] External GET ${PUBLIC_BASE_URL}/admin/login/ reaches Django Admin... "
EXT_ADMIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${PUBLIC_BASE_URL}/admin/login/" || true)
if [[ "${EXT_ADMIN_CODE}" =~ ^(200|302)$ ]]; then
  echo "PASSED (HTTP ${EXT_ADMIN_CODE})"
else
  echo "FAILED!"
  echo "External Admin route failed to reach Django. Returned HTTP ${EXT_ADMIN_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 4: Internal API Access from Astro BFF Subnet MUST Succeed
# ------------------------------------------------------------------------------
echo -n "[Test 4/4] Internal GET ${INTERNAL_API_URL}/api/v1/games/ succeeds... "
INT_API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${INTERNAL_API_URL}/api/v1/games/" || true)
if [[ "${INT_API_CODE}" =~ ^(200)$ ]]; then
  echo "PASSED (HTTP ${INT_API_CODE})"
else
  echo "FAILED!"
  echo "Internal API unreachable from BFF network. Returned HTTP ${INT_API_CODE}"
  exit 1
fi

echo "=================================================="
echo "All 4 Ingress Boundary Tests Passed Successfully."
echo "=================================================="
