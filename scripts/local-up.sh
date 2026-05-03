#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/deployments/docker-compose.yaml"
ENV_FILE="${ROOT_DIR}/.env.local"
ENV_EXAMPLE="${ROOT_DIR}/.env.local.example"
RUNTIME_DIR="${ROOT_DIR}/.runtime"
SERVICES=(redis mock-upstream gateway admin)

if [ "${1:-}" = "--with-monitoring" ]; then
  SERVICES+=(prometheus grafana)
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker 명령을 찾을 수 없습니다."
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "[INFO] .env.local 파일이 없어 .env.local.example에서 복사했습니다."
fi

mkdir -p "${RUNTIME_DIR}"

echo "[INFO] Docker Compose stack을 시작합니다..."
docker compose -f "${COMPOSE_FILE}" up -d --build "${SERVICES[@]}"

wait_http() {
  local name="$1"
  local url="$2"
  local retries=45
  local sleep_sec=2

  for _ in $(seq 1 "${retries}"); do
    if curl -fsS "${url}" >/dev/null 2>&1; then
      echo "[OK] ${name} 준비 완료: ${url}"
      return 0
    fi
    sleep "${sleep_sec}"
  done

  echo "[ERROR] ${name} 준비 실패: ${url}"
  return 1
}

wait_http "Gateway" "http://127.0.0.1:8080/_health"
wait_http "Admin" "http://127.0.0.1:9000/_health"
if [ "${1:-}" = "--with-monitoring" ]; then
  wait_http "Prometheus" "http://127.0.0.1:9091/-/ready"
  wait_http "Grafana" "http://127.0.0.1:3000/api/health"
fi

echo
echo "[DONE] 로컬 실행 준비가 완료되었습니다."
echo "  - Gateway  : http://127.0.0.1:8080"
echo "  - Admin UI : http://127.0.0.1:9000/ui"
if [ "${1:-}" = "--with-monitoring" ]; then
  echo "  - Prometheus: http://127.0.0.1:9091"
  echo "  - Grafana  : http://127.0.0.1:3000 (admin/admin)"
fi
echo
echo "다음 명령으로 스모크 테스트를 실행하세요:"
echo "  ./scripts/local-smoke.sh"
