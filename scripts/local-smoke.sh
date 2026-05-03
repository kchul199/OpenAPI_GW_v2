#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.local"
ADMIN_KEY="changeme-admin-key"

if [ -f "${ENV_FILE}" ]; then
  value="$(grep -E '^ADMIN_API_KEY=' "${ENV_FILE}" | tail -n 1 | cut -d'=' -f2- || true)"
  if [ -n "${value}" ]; then
    ADMIN_KEY="${value}"
  fi
fi

pretty_json() {
  python -m json.tool
}

fetch_json() {
  local endpoint="$1"
  shift
  local body
  if ! body="$(curl -fsS "$@" "${endpoint}")"; then
    echo "[ERROR] 요청 실패: ${endpoint}"
    exit 1
  fi
  printf "%s" "${body}"
}

echo "[INFO] Gateway health 확인"
fetch_json "http://127.0.0.1:8080/_health" | pretty_json

echo "[INFO] Admin health 확인"
fetch_json "http://127.0.0.1:9000/_health" | pretty_json

echo "[INFO] Admin dashboard 확인"
fetch_json \
  "http://127.0.0.1:9000/api/v1/dashboard" \
  -H "X-Admin-Key: ${ADMIN_KEY}" \
  | python -c 'import json,sys; print(json.dumps(json.load(sys.stdin)["summary"], indent=2))'

echo "[INFO] Route 목록 확인"
fetch_json \
  "http://127.0.0.1:9000/api/v1/routes" \
  -H "X-Admin-Key: ${ADMIN_KEY}" \
  | python -c 'import json,sys; print(len(json.load(sys.stdin)["routes"]))'

echo
echo "[DONE] 스모크 테스트가 완료되었습니다."
