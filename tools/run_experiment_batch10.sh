#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

LABEL="${1:-run_batch10_$(date -u +%Y%m%d_%H%M%S)}"
K="${K:-10}"
BATCH_SIZE=10
ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"

echo "[batch10] repo=${REPO_ROOT}"
echo "[batch10] label=${LABEL}"
echo "[batch10] k=${K}"
echo "[batch10] batch_size=${BATCH_SIZE}"
echo "[batch10] es_url=${ES_URL}"

uv run --project api python -m api.app.cli.cli data prepare
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up -d --build
ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index both
ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run --mode batch --batch-size "${BATCH_SIZE}" --k "${K}" --label "${LABEL}"
uv run --project api python -m api.app.cli.cli report generate --label "${LABEL}"

echo "[batch10] completed label=${LABEL}"
