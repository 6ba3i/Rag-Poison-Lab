#!/usr/bin/env sh
set -eu

ES_URL="${ES_URL:-${ELASTICSEARCH_URL:-http://elasticsearch:9200}}"
INDEX_NAME="movies_poisoned"
MAPPING_FILE="${MAPPING_FILE:-/workspace/docker/es/movies_poisoned_index.json}"
BULK_FILE="${BULK_FILE:-/workspace/data/processed/es_bulk_poisoned_movies.jsonl}"

echo "[index-poisoned] Elasticsearch URL: ${ES_URL}"
echo "[index-poisoned] Index: ${INDEX_NAME}"
echo "[index-poisoned] Mapping file: ${MAPPING_FILE}"
echo "[index-poisoned] Bulk file: ${BULK_FILE}"

if [ ! -s "${MAPPING_FILE}" ]; then
  echo "[index-poisoned] Mapping file missing or empty: ${MAPPING_FILE}" >&2
  exit 1
fi

if [ ! -s "${BULK_FILE}" ]; then
  echo "[index-poisoned] Bulk file missing or empty: ${BULK_FILE}" >&2
  exit 1
fi

line_count="$(wc -l < "${BULK_FILE}" | tr -d '[:space:]')"
if ! [ "${line_count}" -gt 0 ] 2>/dev/null; then
  echo "[index-poisoned] Bulk file has no lines: ${BULK_FILE}" >&2
  exit 1
fi

if [ $((line_count % 2)) -ne 0 ]; then
  echo "[index-poisoned] Bulk JSONL must have action/document line pairs; got ${line_count} lines" >&2
  exit 1
fi

expected_docs=$((line_count / 2))
echo "[index-poisoned] Expected documents from bulk file: ${expected_docs}"

python - "${ES_URL}" "${INDEX_NAME}" "${MAPPING_FILE}" "${BULK_FILE}" "${expected_docs}" <<'PY'
import json
import sys
from pathlib import Path
import urllib.error
import urllib.request

es_url, index_name, mapping_file, bulk_file, expected_docs_raw = sys.argv[1:]
expected_docs = int(expected_docs_raw)
es_url = es_url.rstrip("/")


def request(method: str, path: str, *, data: bytes | None = None, content_type: str | None = None) -> tuple[int, bytes]:
    req = urllib.request.Request(f"{es_url}{path}", data=data, method=method)
    if content_type is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


mapping_path = Path(mapping_file)
bulk_path = Path(bulk_file)

try:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"[index-poisoned] Invalid mapping JSON '{mapping_path}': {exc}")

status, _ = request("HEAD", f"/{index_name}")
if status == 404:
    print(f"[index-poisoned] Creating index '{index_name}'")
    create_status, create_body = request(
        "PUT",
        f"/{index_name}",
        data=json.dumps(mapping).encode("utf-8"),
        content_type="application/json",
    )
    if create_status not in {200, 201}:
        raise SystemExit(
            f"[index-poisoned] Failed to create index '{index_name}' (HTTP {create_status}): "
            f"{create_body.decode('utf-8', errors='replace')}"
        )
elif status == 200:
    print(f"[index-poisoned] Index '{index_name}' already exists; reusing")
else:
    raise SystemExit(f"[index-poisoned] Failed to check index '{index_name}' (HTTP {status})")

bulk_payload = bulk_path.read_bytes()
if not bulk_payload.endswith(b"\n"):
    bulk_payload += b"\n"

bulk_status, bulk_response_body = request(
    "POST",
    "/_bulk?refresh=true",
    data=bulk_payload,
    content_type="application/x-ndjson",
)
if bulk_status != 200:
    raise SystemExit(
        f"[index-poisoned] Bulk request failed (HTTP {bulk_status}): "
        f"{bulk_response_body.decode('utf-8', errors='replace')}"
    )

try:
    bulk_response = json.loads(bulk_response_body.decode("utf-8"))
except Exception as exc:
    raise SystemExit(f"[index-poisoned] Failed to parse bulk response JSON: {exc}")

if bulk_response.get("errors"):
    items = bulk_response.get("items") or []
    first_error: str | None = None
    for item in items:
        detail = item.get("index", {})
        if "error" in detail:
            first_error = json.dumps(detail["error"], sort_keys=True)
            break
    raise SystemExit(f"[index-poisoned] Bulk indexing reported errors. First error: {first_error or 'unknown'}")

count_status, count_body = request("GET", f"/{index_name}/_count")
if count_status != 200:
    raise SystemExit(
        f"[index-poisoned] Count request failed (HTTP {count_status}): "
        f"{count_body.decode('utf-8', errors='replace')}"
    )

try:
    indexed_docs = int(json.loads(count_body.decode("utf-8"))["count"])
except Exception as exc:
    raise SystemExit(f"[index-poisoned] Failed to parse count response: {exc}")

if indexed_docs != expected_docs:
    raise SystemExit(
        f"[index-poisoned] Document count mismatch for index '{index_name}': "
        f"expected {expected_docs}, got {indexed_docs}"
    )

print(f"[index-poisoned] Indexing complete. Verified {indexed_docs} documents in '{index_name}'")
PY
