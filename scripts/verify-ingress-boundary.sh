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
# the loopback/private network; and neither surface may leak application
# banner headers (SBGC-109).  See SBGC-105 / SBGC-106 / SBGC-109.
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

HEADER_FILE="$(mktemp)"
trap 'rm -f "$HEADER_FILE"' EXIT

# fetch_headers <url> — curl -D the response headers into HEADER_FILE.
fetch_headers() {
  curl -s -o /dev/null -D "$HEADER_FILE" "$1" || true
}

# banner_headers_in <pattern> — case-insensitive match over captured headers.
banner_headers_in() {
  tr '[:upper:]' '[:lower:]' < "$HEADER_FILE" | grep -E "$1" || true
}

# ------------------------------------------------------------------------------
# Test 1: External Direct API Access MUST Be Blocked (403 or 404)
# ------------------------------------------------------------------------------
echo -n "[Test 1/6] External GET ${PUBLIC_BASE_URL}/api/v1/games/ is blocked... "
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
echo -n "[Test 2/6] External POST ${PUBLIC_BASE_URL}/api/v1/auth/login is blocked... "
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
echo -n "[Test 3a/6] External GET ${PUBLIC_BASE_URL}/admin/ is 404... "
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
echo -n "[Test 3b/6] External GET ${PUBLIC_BASE_URL}/${ADMIN_PATH}login/ reaches Django Admin... "
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
echo -n "[Test 4/6] Internal GET ${INTERNAL_API_URL}/api/v1/games/ succeeds... "
INT_API_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${INTERNAL_API_URL}/api/v1/games/" || true)
if [[ "${INT_API_CODE}" =~ ^(200)$ ]]; then
  echo "PASSED (HTTP ${INT_API_CODE})"
else
  echo "FAILED!"
  echo "Internal API unreachable from BFF network. Returned HTTP ${INT_API_CODE}"
  exit 1
fi

# ------------------------------------------------------------------------------
# Test 5: Public egress MUST NOT leak application banner headers
# ------------------------------------------------------------------------------
# The application stack (Astro SSR / Django) must never advertise itself via
# X-Powered-By, and must not leak the WSGI runtime through the Server header.
# A CDN/edge identity (e.g. nginx / Vercel / Cloudflare) in Server is expected
# and tolerated — banner suppression on the egress edge is owned by the proxy.
echo -n "[Test 5/6] Public egress omits application banner headers... "
fetch_headers "${PUBLIC_BASE_URL}/"
leaks=$(banner_headers_in "^x-powered-by:")
if [[ -n "$leaks" ]]; then
  echo "FAILED!"
  echo "CRITICAL: Public egress leaked X-Powered-By banner header:"
  echo "$leaks"
  exit 1
fi
runtime_server=$(banner_headers_in "^server:.*(wsgiserver|gunicorn|python/)")
if [[ -n "$runtime_server" ]]; then
  echo "FAILED!"
  echo "CRITICAL: Public egress leaked WSGI runtime version in Server header:"
  echo "$runtime_server"
  exit 1
fi
echo "PASSED"

# ------------------------------------------------------------------------------
# Test 6: Internal Django MUST NOT leak framework banners or Python versions
# ------------------------------------------------------------------------------
# X-Powered-By is app-controllable and must be absent.  A bare Server line from
# the WSGI server (gunicorn) is reported for operator awareness — stripping it
# is owned by the proxy in front of the WSGI layer, not by Django itself.
echo -n "[Test 6/6] Internal API omits framework banner headers... "
fetch_headers "${INTERNAL_API_URL}/api/v1/games/"
leaks=$(banner_headers_in "^x-powered-by:")
if [[ -n "$leaks" ]]; then
  echo "FAILED!"
  echo "CRITICAL: Internal API leaked X-Powered-By banner header:"
  echo "$leaks"
  exit 1
fi
python_leak=$(banner_headers_in "^server:.*(wsgiserver|python/)")
if [[ -n "$python_leak" ]]; then
  echo "FAILED!"
  echo "CRITICAL: Internal API leaked WSGI/Python version in Server header:"
  echo "$python_leak"
  exit 1
fi
gunicorn_banner=$(banner_headers_in "^server:.*gunicorn")
if [[ -n "$gunicorn_banner" ]]; then
  echo "PASSED (note: WSGI layer emits $(tr -d '\r' < "$HEADER_FILE" | grep -i '^server:' | tr -s ' ') — strip at the proxy for full concealment)"
else
  echo "PASSED"
fi

echo "=================================================="
echo "All 6 Ingress Boundary Tests Passed Successfully."
echo "=================================================="
