#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT_DIR}/deployments/docker-compose.yaml"

echo "[INFO] Docker Compose stack을 중지합니다..."
docker compose -f "${COMPOSE_FILE}" down
echo "[DONE] 중지 완료"
