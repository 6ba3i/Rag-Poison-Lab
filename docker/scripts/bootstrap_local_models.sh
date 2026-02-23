#!/bin/sh
set -eu

MODEL="${OLLAMA_DEFAULT_MODEL:-qwen2.5:1.5b}"
MAX_RETRIES="${OLLAMA_INIT_MAX_RETRIES:-90}"
SLEEP_SECONDS="${OLLAMA_INIT_SLEEP_SECONDS:-2}"

echo "[ollama-init] target model: ${MODEL}"
echo "[ollama-init] OLLAMA_HOST: ${OLLAMA_HOST:-<unset>}"

attempt=0
while true; do
  if LIST_OUTPUT="$(ollama list 2>/dev/null)"; then
    break
  fi

  attempt=$((attempt + 1))
  if [ "${attempt}" -ge "${MAX_RETRIES}" ]; then
    echo "[ollama-init] ERROR: ollama host not ready after ${MAX_RETRIES} attempts" >&2
    exit 1
  fi

  sleep "${SLEEP_SECONDS}"
done

if printf '%s\n' "${LIST_OUTPUT}" | awk 'NR>1 {print $1}' | grep -Fx -- "${MODEL}" >/dev/null; then
  echo "[ollama-init] model already present: ${MODEL}"
  exit 0
fi

echo "[ollama-init] pulling model: ${MODEL}"
ollama pull "${MODEL}"

if ollama list | awk 'NR>1 {print $1}' | grep -Fx -- "${MODEL}" >/dev/null; then
  echo "[ollama-init] model ready: ${MODEL}"
  exit 0
fi

echo "[ollama-init] ERROR: model not found after pull: ${MODEL}" >&2
exit 1
