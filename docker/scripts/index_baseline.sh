#!/usr/bin/env sh
set -eu

ES_URL="${ES_URL:-${ELASTICSEARCH_URL:-http://elasticsearch:9200}}"
PROCESSED_DIR="${PROCESSED_DIR:-/workspace/data/processed}"

echo "[index-baseline] Delegating to canonical CLI index path"
python -m api.app.cli.cli index baseline --es-url "${ES_URL}" --processed-dir "${PROCESSED_DIR}"
