#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://shadowspark-ai-api.onrender.com}"
# Strip trailing slash if present
BASE_URL="${BASE_URL%/}"

if [[ -z "${SHADOWSPARK_API_TOKEN:-}" ]]; then
  echo "[-] ERROR: SHADOWSPARK_API_TOKEN environment variable must be set." >&2
  echo "    Usage: SHADOWSPARK_API_TOKEN=\"<token>\" [BASE_URL=\"...\"] $0" >&2
  exit 1
fi

echo "[+] Starting ShadowSpark Render E2E Verification against: ${BASE_URL}"

# Helper to extract JSON field using python3
json_field() {
  local json_str="$1"
  local field="$2"
  python3 -c "import sys, json; data = json.loads(sys.argv[1]); print(data.get(sys.argv[2], ''))" "$json_str" "$field" 2>/dev/null || echo ""
}

# 1. Health check: GET /healthz -> 200
echo "[1/6] Testing GET /healthz..."
HEALTH_RESP=$(curl -sS -w "\n%{http_code}" "${BASE_URL}/healthz")
HEALTH_CODE=$(echo "$HEALTH_RESP" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESP" | sed '$d')

if [[ "$HEALTH_CODE" != "200" ]]; then
  echo "[-] FAILED: GET /healthz returned HTTP ${HEALTH_CODE}, expected 200" >&2
  echo "    Body: ${HEALTH_BODY}" >&2
  exit 1
fi
echo "      Passed (HTTP 200: ${HEALTH_BODY})"

# 2. Unauthorized request check: POST /v1/compliance-review-brief without Authorization -> 401
echo "[2/6] Testing unauthorized request (missing Authorization header)..."
IDEM_KEY="idem-e2e-$(date +%s)-$RANDOM"
UNAUTH_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/v1/compliance-review-brief" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: ${IDEM_KEY}" \
  -d '{"exception_id": "ex_a_021"}')
UNAUTH_CODE=$(echo "$UNAUTH_RESP" | tail -n1)
UNAUTH_BODY=$(echo "$UNAUTH_RESP" | sed '$d')

if [[ "$UNAUTH_CODE" != "401" ]]; then
  echo "[-] FAILED: Expected HTTP 401 for unauthorized request, got ${UNAUTH_CODE}" >&2
  echo "    Body: ${UNAUTH_BODY}" >&2
  exit 1
fi
echo "      Passed (HTTP 401 received)"

# 3. Create compliance review brief: POST /v1/compliance-review-brief -> 201
echo "[3/6] Testing POST /v1/compliance-review-brief..."
CREATE_IDEM_KEY="idem-e2e-$(date +%s)-$RANDOM"
CREATE_RESP=$(curl -sS -w "\n%{http_code}" -X POST "${BASE_URL}/v1/compliance-review-brief" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SHADOWSPARK_API_TOKEN}" \
  -H "Idempotency-Key: ${CREATE_IDEM_KEY}" \
  -d '{"exception_id": "ex_a_021"}')
CREATE_CODE=$(echo "$CREATE_RESP" | tail -n1)
CREATE_BODY=$(echo "$CREATE_RESP" | sed '$d')

if [[ "$CREATE_CODE" != "201" ]]; then
  echo "[-] FAILED: POST /v1/compliance-review-brief returned HTTP ${CREATE_CODE}, expected 201" >&2
  echo "    Body: ${CREATE_BODY}" >&2
  exit 1
fi

BRIEF_ID=$(json_field "$CREATE_BODY" "brief_id")
if [[ -z "$BRIEF_ID" ]]; then
  echo "[-] FAILED: brief_id not found in response body" >&2
  echo "    Body: ${CREATE_BODY}" >&2
  exit 1
fi
echo "      Passed (HTTP 201, brief_id=${BRIEF_ID})"

# 4. Read review queue: GET /v1/review-queue/{brief_id} -> 200
echo "[4/6] Testing GET /v1/review-queue/${BRIEF_ID}..."
QUEUE_RESP=$(curl -sS -w "\n%{http_code}" \
  -H "Authorization: Bearer ${SHADOWSPARK_API_TOKEN}" \
  "${BASE_URL}/v1/review-queue/${BRIEF_ID}")
QUEUE_CODE=$(echo "$QUEUE_RESP" | tail -n1)
QUEUE_BODY=$(echo "$QUEUE_RESP" | sed '$d')

if [[ "$QUEUE_CODE" != "200" ]]; then
  echo "[-] FAILED: GET /v1/review-queue/${BRIEF_ID} returned HTTP ${QUEUE_CODE}, expected 200" >&2
  echo "    Body: ${QUEUE_BODY}" >&2
  exit 1
fi

INITIAL_STATE=$(json_field "$QUEUE_BODY" "queue_state")
if [[ "$INITIAL_STATE" != "pending_review" ]]; then
  echo "[-] FAILED: Expected queue_state 'pending_review', got '${INITIAL_STATE}'" >&2
  exit 1
fi
echo "      Passed (HTTP 200, queue_state=${INITIAL_STATE})"

# 5. Append annotation: POST /v1/review-queue/{brief_id}/annotations -> 200
echo "[5/6] Testing POST /v1/review-queue/${BRIEF_ID}/annotations..."
ANN_IDEM_KEY="idem-ann-e2e-$(date +%s)-$RANDOM"
ANNOTATE_RESP=$(curl -sS -w "\n%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${SHADOWSPARK_API_TOKEN}" \
  -H "Idempotency-Key: ${ANN_IDEM_KEY}" \
  -d '{"annotation": "E2E automated verification annotation"}' \
  "${BASE_URL}/v1/review-queue/${BRIEF_ID}/annotations")
ANNOTATE_CODE=$(echo "$ANNOTATE_RESP" | tail -n1)
ANNOTATE_BODY=$(echo "$ANNOTATE_RESP" | sed '$d')

if [[ "$ANNOTATE_CODE" != "200" ]]; then
  echo "[-] FAILED: POST annotations returned HTTP ${ANNOTATE_CODE}, expected 200" >&2
  echo "    Body: ${ANNOTATE_BODY}" >&2
  exit 1
fi

ANNOTATED_STATE=$(json_field "$ANNOTATE_BODY" "queue_state")
if [[ "$ANNOTATED_STATE" != "annotated" ]]; then
  echo "[-] FAILED: Expected annotated state 'annotated', got '${ANNOTATED_STATE}'" >&2
  exit 1
fi
echo "      Passed (HTTP 200, queue_state=${ANNOTATED_STATE})"

# 6. Re-fetch review queue to verify persisted annotation state: GET /v1/review-queue/{brief_id} -> 200
echo "[6/6] Testing GET /v1/review-queue/${BRIEF_ID} for persisted annotation state..."
VERIFY_RESP=$(curl -sS -w "\n%{http_code}" \
  -H "Authorization: Bearer ${SHADOWSPARK_API_TOKEN}" \
  "${BASE_URL}/v1/review-queue/${BRIEF_ID}")
VERIFY_CODE=$(echo "$VERIFY_RESP" | tail -n1)
VERIFY_BODY=$(echo "$VERIFY_RESP" | sed '$d')

if [[ "$VERIFY_CODE" != "200" ]]; then
  echo "[-] FAILED: Final verification GET returned HTTP ${VERIFY_CODE}, expected 200" >&2
  exit 1
fi

FINAL_STATE=$(json_field "$VERIFY_BODY" "queue_state")
if [[ "$FINAL_STATE" != "annotated" ]]; then
  echo "[-] FAILED: Expected final state 'annotated', got '${FINAL_STATE}'" >&2
  exit 1
fi
echo "      Passed (HTTP 200, persisted state=${FINAL_STATE})"

echo "[+] All Render E2E checks passed successfully against ${BASE_URL}!"
