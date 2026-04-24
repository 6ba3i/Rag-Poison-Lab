#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

ES_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
RESULTS_ROOT="${RESULTS_ROOT:-data/results/runs}"
ATTACK_CONFIG_PATH="data/config/attack_config.json"
LLM_CONFIG_PATH="data/config/llm_config.json"

LABEL_PREFIX="${1:-run_batch10_cross}"
RUN_ID="$(date -u +%Y%m%d_%H%M%S)"
K="${K:-10}"
REPEAT_COUNT="${REPEAT_COUNT:-1}"
SEED="${SEED:-42}"
BATCH_SIZE=10

ATTACK_TYPE="targeted_promotion"
TARGET_BOOST_POLICY="keyword_burst"
POISON_FRACTION="0.2"
RETRIEVAL_MODE="hybrid"
RANKING_MODE="llm_rerank"

BACKUP_ATTACK_CONFIG=""
BACKUP_LLM_CONFIG=""

COMBOS=(
  "deepseek|deepseek-reasoner|dsk|gemini|gemini-2.5-pro|gem"
  "gemini|gemini-2.5-pro|gem|deepseek|deepseek-reasoner|dsk"
  "claude|claude-sonnet-4-6|cld|chatgpt|gpt-5.4|gpt"
  "chatgpt|gpt-5.4|gpt|claude|claude-sonnet-4-6|cld"
  "qwen|qwen-3.5-plus|qwn|chatgpt|gpt-5.4|gpt"
  "chatgpt|gpt-5.4|gpt|qwen|qwen-3.5-plus|qwn"
)

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

validate() {
  [[ "${K}" =~ ^[0-9]+$ ]] || die "K must be a non-negative integer"
  [[ "${REPEAT_COUNT}" =~ ^[0-9]+$ ]] || die "REPEAT_COUNT must be a non-negative integer"
  [[ "${SEED}" =~ ^[0-9]+$ ]] || die "SEED must be a non-negative integer"

  [[ -f "${ATTACK_CONFIG_PATH}" ]] || die "Missing attack config: ${ATTACK_CONFIG_PATH}"
  [[ -f "${LLM_CONFIG_PATH}" ]] || die "Missing llm config: ${LLM_CONFIG_PATH}"
  command -v uv >/dev/null 2>&1 || die "uv is required"
  command -v python3 >/dev/null 2>&1 || die "python3 is required"
}

backup_configs() {
  BACKUP_ATTACK_CONFIG="$(mktemp)"
  BACKUP_LLM_CONFIG="$(mktemp)"
  cp "${ATTACK_CONFIG_PATH}" "${BACKUP_ATTACK_CONFIG}"
  cp "${LLM_CONFIG_PATH}" "${BACKUP_LLM_CONFIG}"
}

restore_configs() {
  if [[ -n "${BACKUP_ATTACK_CONFIG}" && -f "${BACKUP_ATTACK_CONFIG}" ]]; then
    cp "${BACKUP_ATTACK_CONFIG}" "${ATTACK_CONFIG_PATH}"
  fi
  if [[ -n "${BACKUP_LLM_CONFIG}" && -f "${BACKUP_LLM_CONFIG}" ]]; then
    cp "${BACKUP_LLM_CONFIG}" "${LLM_CONFIG_PATH}"
  fi
}

cleanup() {
  restore_configs
  if [[ -n "${BACKUP_ATTACK_CONFIG}" && -f "${BACKUP_ATTACK_CONFIG}" ]]; then
    rm -f "${BACKUP_ATTACK_CONFIG}"
  fi
  if [[ -n "${BACKUP_LLM_CONFIG}" && -f "${BACKUP_LLM_CONFIG}" ]]; then
    rm -f "${BACKUP_LLM_CONFIG}"
  fi
}

run_step() {
  local label="$1"
  local step_name="$2"
  shift 2
  log "[${label}] step=${step_name}"
  "$@"
}

write_combo_configs() {
  local victim_provider="$1"
  local victim_model="$2"
  local attacker_provider="$3"
  local attacker_model="$4"

  ATTACK_TYPE="${ATTACK_TYPE}" \
  TARGET_BOOST_POLICY="${TARGET_BOOST_POLICY}" \
  POISON_FRACTION="${POISON_FRACTION}" \
  RETRIEVAL_MODE="${RETRIEVAL_MODE}" \
  RANKING_MODE="${RANKING_MODE}" \
  VICTIM_PROVIDER="${victim_provider}" \
  VICTIM_MODEL="${victim_model}" \
  ATTACKER_PROVIDER="${attacker_provider}" \
  ATTACKER_MODEL="${attacker_model}" \
  BASE_ATTACK_CONFIG="${BACKUP_ATTACK_CONFIG}" \
  BASE_LLM_CONFIG="${BACKUP_LLM_CONFIG}" \
  ATTACK_CONFIG_PATH="${ATTACK_CONFIG_PATH}" \
  LLM_CONFIG_PATH="${LLM_CONFIG_PATH}" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

attack_path = Path(os.environ["ATTACK_CONFIG_PATH"])
llm_path = Path(os.environ["LLM_CONFIG_PATH"])
base_attack_path = Path(os.environ["BASE_ATTACK_CONFIG"])
base_llm_path = Path(os.environ["BASE_LLM_CONFIG"])

attack_payload = json.loads(base_attack_path.read_text(encoding="utf-8"))
llm_payload = json.loads(base_llm_path.read_text(encoding="utf-8"))

if not isinstance(attack_payload, dict):
    raise SystemExit("base attack config is not a JSON object")
if not isinstance(llm_payload, dict):
    raise SystemExit("base llm config is not a JSON object")

attack_payload["attack_type"] = os.environ["ATTACK_TYPE"]
attack_payload["target_boost_policy"] = os.environ["TARGET_BOOST_POLICY"]
attack_payload["poison_fraction"] = float(os.environ["POISON_FRACTION"])

llm_payload["retrieval_mode"] = os.environ["RETRIEVAL_MODE"]
llm_payload["ranking_mode"] = os.environ["RANKING_MODE"]
llm_payload["victim"] = {
    "provider": os.environ["VICTIM_PROVIDER"],
    "model": os.environ["VICTIM_MODEL"],
}
llm_payload["attacker"] = {
    "provider": os.environ["ATTACKER_PROVIDER"],
    "model": os.environ["ATTACKER_MODEL"],
}

attack_path.write_text(json.dumps(attack_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
llm_path.write_text(json.dumps(llm_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

main() {
  validate
  mkdir -p "${RESULTS_ROOT}"
  backup_configs
  trap cleanup EXIT INT TERM

  log "repo_root=${REPO_ROOT}"
  log "es_url=${ES_URL}"
  log "results_root=${RESULTS_ROOT}"
  log "run_id=${RUN_ID}"
  log "label_prefix=${LABEL_PREFIX}"
  log "combos=${#COMBOS[@]} batch_size=${BATCH_SIZE} k=${K} repeat_count=${REPEAT_COUNT} seed=${SEED}"
  log "fixed attack_type=${ATTACK_TYPE} target_boost_policy=${TARGET_BOOST_POLICY} poison_fraction=${POISON_FRACTION}"
  log "fixed retrieval_mode=${RETRIEVAL_MODE} ranking_mode=${RANKING_MODE}"

  local combo_index=0
  local combo_spec victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag label
  for combo_spec in "${COMBOS[@]}"; do
    IFS='|' read -r victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag <<< "${combo_spec}"
    label="${LABEL_PREFIX}_${RUN_ID}_$(printf '%02d' "${combo_index}")_v${victim_tag}_a${attacker_tag}"

    log "combo_index=${combo_index} label=${label} victim=${victim_provider}:${victim_model} attacker=${attacker_provider}:${attacker_model}"
    write_combo_configs "${victim_provider}" "${victim_model}" "${attacker_provider}" "${attacker_model}"

    run_step "${label}" "index_baseline" \
      env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index baseline
    run_step "${label}" "attack_build_poisoned" \
      env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli attack build-poisoned
    run_step "${label}" "index_poisoned" \
      env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index poisoned
    run_step "${label}" "eval_run" \
      env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run \
      --mode batch \
      --batch-size "${BATCH_SIZE}" \
      --k "${K}" \
      --label "${label}" \
      --repeat-count "${REPEAT_COUNT}" \
      --seed "${SEED}" \
      --results-root "${RESULTS_ROOT}" \
      --require-rerank-success \
      --overwrite
    run_step "${label}" "report_generate" \
      env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli report generate \
      --label "${label}" \
      --results-root "${RESULTS_ROOT}"

    combo_index=$((combo_index + 1))
  done

  log "completed run_id=${RUN_ID} total_runs=${combo_index}"
}

main "$@"
