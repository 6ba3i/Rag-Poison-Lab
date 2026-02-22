#!/usr/bin/env sh
set -eu

ES_URL="${ES_URL:-${ELASTICSEARCH_URL:-http://elasticsearch:9200}}"
MAX_RETRIES="${ES_WAIT_RETRIES:-60}"
SLEEP_SECONDS="${ES_WAIT_SLEEP_SECONDS:-2}"

if ! [ "${MAX_RETRIES}" -gt 0 ] 2>/dev/null; then
  echo "[wait-for-es] ES_WAIT_RETRIES must be a positive integer, got '${MAX_RETRIES}'" >&2
  exit 1
fi

if ! [ "${SLEEP_SECONDS}" -gt 0 ] 2>/dev/null; then
  echo "[wait-for-es] ES_WAIT_SLEEP_SECONDS must be a positive integer, got '${SLEEP_SECONDS}'" >&2
  exit 1
fi

echo "[wait-for-es] Waiting for Elasticsearch at ${ES_URL}"

attempt=1
while [ "${attempt}" -le "${MAX_RETRIES}" ]; do
  if python - "${ES_URL}" <<'PY'
import json
import sys
import urllib.error
import urllib.request

url = sys.argv[1].rstrip("/") + "/_cluster/health"
try:
    with urllib.request.urlopen(url, timeout=2) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)

status = str(payload.get("status", "")).lower()
if status in {"yellow", "green"}:
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    echo "[wait-for-es] Elasticsearch is ready (status yellow/green)"
    exit 0
  fi

  echo "[wait-for-es] Attempt ${attempt}/${MAX_RETRIES} failed; retrying in ${SLEEP_SECONDS}s"
  sleep "${SLEEP_SECONDS}"
  attempt=$((attempt + 1))
done

echo "[wait-for-es] Elasticsearch did not become ready after ${MAX_RETRIES} attempts" >&2
exit 1
