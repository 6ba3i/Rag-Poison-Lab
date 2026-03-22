#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

LABEL="${1:-run_single_demo_$(date -u +%Y%m%d_%H%M%S)}"
USER_ID="${2:-}"
K="${K:-10}"
ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "[single] repo=${REPO_ROOT}"
echo "[single] label=${LABEL}"
echo "[single] k=${K}"
echo "[single] es_url=${ES_URL}"
if [[ -n "${USER_ID}" ]]; then
  echo "[single] user_id=${USER_ID}"
else
  echo "[single] user_id=auto"
fi

uv run --project api python -m api.app.cli.cli data prepare
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index both

if [[ -n "${USER_ID}" ]]; then
  ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run --mode single --user-id "${USER_ID}" --k "${K}" --label "${LABEL}"
else
  ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run --mode single --k "${K}" --label "${LABEL}"
fi

uv run --project api python -m api.app.cli.cli report generate --label "${LABEL}"

echo "[single] completed label=${LABEL}"
