#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

LABEL="${1:-run_full_$(date -u +%Y%m%d_%H%M%S)}"
K="${K:-10}"
ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "[full] repo=${REPO_ROOT}"
echo "[full] label=${LABEL}"
echo "[full] k=${K}"
echo "[full] es_url=${ES_URL}"

uv run --project api python -m api.app.cli.cli data prepare
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index both
ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run --mode full --k "${K}" --label "${LABEL}"
uv run --project api python -m api.app.cli.cli report generate --label "${LABEL}"

echo "[full] completed label=${LABEL}"
