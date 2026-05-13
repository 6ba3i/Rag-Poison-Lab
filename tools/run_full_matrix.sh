#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

ES_URL="http://localhost:9200"
RESULTS_ROOT="data/results/full"
ATTACK_CONFIG_PATH="data/config/attack_config.json"
LLM_CONFIG_PATH="data/config/llm_config.json"
EVAL_MODE="full"
K=10
REPEAT_COUNT=1
SEED=42
START_INDEX=0
MAX_RUNS=""
RESUME=false
DRY_RUN=false
FAIL_FAST=true
PROFILE="deterministic_hybrid_attacker5_attack3"
REQUESTED_PROFILE=""
MATRIX_VERSION="deterministic_hybrid_attacker5_attack3_v1"
MATRIX_SIGNATURE=""
MATRIX_ATTACKERS_JSON="[]"
MATRIX_ATTACK_TYPES_CSV="targeted_promotion,prompt_injection,untargeted_degradation"

LLM_MODELS_YAML_PATH="conf/llm_models.yaml"
STABLE_VICTIM_PROVIDER=""
STABLE_VICTIM_MODEL=""
STABLE_VICTIM_TAG=""
TUNING_PLAN_STATUS="unknown"
ATTACKER_EXPECTED_COUNT=5

FORCE_RETUNE="${FORCE_RETUNE:-false}"

TUNING_BATCH_SIZE=100
TUNING_POISON_FRACTIONS=("0.1" "0.2" "0.3")
TUNING_TARGET_POLICIES=("disabled" "keyword_burst" "aggressive")
TUNING_TARGET_STRENGTHS=("2" "4" "6")
TUNING_DEFAULT_STRENGTH=3
TUNING_DISABLED_STRENGTH=1
TUNING_HARD_FAIL_SCORE="-1000000000.0"

STATE_DIR=""
STATE_LOGS_DIR=""
PROGRESS_JSON=""
RECORDS_JSON=""
COMBINED_CSV=""
COMBINED_MD=""
FAILURES_CSV=""
FAILURES_MD=""
COMPLETED_CSV=""
BEST_ATTACK_PARAMS_JSON=""
TUNING_RESULTS_ROOT=""
TUNING_RUN_LOG=""

RUN_ID=""
TOTAL_COMBOS=0

BACKUP_ATTACK_CONFIG=""
BACKUP_LLM_CONFIG=""

declare -A COMPLETED_INDEX
declare -a COMBO_SPECS
declare -a ATTACKER_SPECS

usage() {
  cat <<'USAGE'
Usage:
  tools/run_full_matrix.sh [options]

Options:
  --es-url URL                Elasticsearch URL (default: http://localhost:9200)
  --results-root PATH         Output root for full sweep (default: data/results/full)
  --k INT                     Top-k for eval (default: 10)
  --repeat-count INT          Repeat count for eval (default: 1)
  --seed INT                  Base seed for eval (default: 42)
  --profile NAME              Deprecated compatibility flag (ignored; deterministic matrix is always used)
  --start-index INT           Start combo index (default: 0)
  --max-runs INT              Stop after N combos processed in this invocation
  --resume                    Resume from checkpoint under <results-root>/_state
  --dry-run                   Print planned run count and exit
  --fail-fast                 Stop on first failed combo (default behavior)
  --continue-on-error         Continue sweep when a combo fails
  -h, --help                  Show this message

Notes:
  - This script updates data/config/attack_config.json and data/config/llm_config.json
    for each combo, then restores originals on exit.
  - Checkpoint/resume state is persisted under <results-root>/_state.
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

timestamp_utc() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

short_hash() {
  local text="$1"
  printf '%s' "${text}" | sha256sum | awk '{print substr($1,1,8)}'
}

attack_tag() {
  case "$1" in
    targeted_promotion) echo "tprom" ;;
    untargeted_degradation) echo "udeg" ;;
    prompt_injection) echo "pinj" ;;
    *) echo "atk" ;;
  esac
}

boost_tag() {
  case "$1" in
    disabled) echo "dis" ;;
    keyword_burst) echo "kbr" ;;
    aggressive) echo "agg" ;;
    *) echo "boost" ;;
  esac
}

retrieval_tag() {
  case "$1" in
    hybrid) echo "hyb" ;;
    *) echo "ret" ;;
  esac
}

ranking_tag() {
  case "$1" in
    deterministic) echo "det" ;;
    *) echo "rank" ;;
  esac
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --es-url)
        ES_URL="$2"
        shift 2
        ;;
      --results-root)
        RESULTS_ROOT="$2"
        shift 2
        ;;
      --k)
        K="$2"
        shift 2
        ;;
      --repeat-count)
        REPEAT_COUNT="$2"
        shift 2
        ;;
      --seed)
        SEED="$2"
        shift 2
        ;;
      --profile)
        REQUESTED_PROFILE="$2"
        shift 2
        ;;
      --start-index)
        START_INDEX="$2"
        shift 2
        ;;
      --max-runs)
        MAX_RUNS="$2"
        shift 2
        ;;
      --resume)
        RESUME=true
        shift
        ;;
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --fail-fast)
        FAIL_FAST=true
        shift
        ;;
      --continue-on-error)
        FAIL_FAST=false
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done
}

validate_args() {
  [[ "${K}" =~ ^[0-9]+$ ]] || die "--k must be a non-negative integer"
  [[ "${REPEAT_COUNT}" =~ ^[0-9]+$ ]] || die "--repeat-count must be a non-negative integer"
  [[ "${SEED}" =~ ^[0-9]+$ ]] || die "--seed must be a non-negative integer"
  [[ "${START_INDEX}" =~ ^[0-9]+$ ]] || die "--start-index must be a non-negative integer"
  if [[ -n "${MAX_RUNS}" ]]; then
    [[ "${MAX_RUNS}" =~ ^[0-9]+$ ]] || die "--max-runs must be a non-negative integer"
  fi
  PROFILE="${MATRIX_VERSION}"
  if [[ -n "${REQUESTED_PROFILE}" && "${REQUESTED_PROFILE}" != "${MATRIX_VERSION}" ]]; then
    log "Ignoring deprecated --profile=${REQUESTED_PROFILE}; runner always uses ${MATRIX_VERSION}"
  fi

  [[ -f "${ATTACK_CONFIG_PATH}" ]] || die "Missing attack config: ${ATTACK_CONFIG_PATH}"
  [[ -f "${LLM_CONFIG_PATH}" ]] || die "Missing llm config: ${LLM_CONFIG_PATH}"
  [[ -f "${LLM_MODELS_YAML_PATH}" ]] || die "Missing attacker models yaml: ${LLM_MODELS_YAML_PATH}"
  command -v uv >/dev/null 2>&1 || die "uv is required"
  command -v python3 >/dev/null 2>&1 || die "python3 is required"
}

init_paths() {
  mkdir -p "${RESULTS_ROOT}"
  STATE_DIR="${RESULTS_ROOT}/_state"
  mkdir -p "${STATE_DIR}"
  STATE_LOGS_DIR="${STATE_DIR}/logs"
  mkdir -p "${STATE_LOGS_DIR}"

  PROGRESS_JSON="${STATE_DIR}/progress.json"
  RECORDS_JSON="${STATE_DIR}/records.json"
  COMBINED_CSV="${RESULTS_ROOT}/combined_results.csv"
  COMBINED_MD="${RESULTS_ROOT}/combined_results.md"
  FAILURES_CSV="${RESULTS_ROOT}/failures.csv"
  FAILURES_MD="${RESULTS_ROOT}/failures.md"
  COMPLETED_CSV="${RESULTS_ROOT}/completed_runs.csv"
  BEST_ATTACK_PARAMS_JSON="${STATE_DIR}/best_attack_params.json"
  TUNING_RESULTS_ROOT="${RESULTS_ROOT}/_tuning"
}

write_progress() {
  local status="$1"
  local combo_index="$2"
  local label="$3"
  local step="$4"
  local message="$5"

  STATUS="${status}" \
  COMBO_INDEX="${combo_index}" \
  CURRENT_LABEL="${label}" \
  CURRENT_STEP="${step}" \
  MESSAGE="${message}" \
  TOTAL_COMBOS="${TOTAL_COMBOS}" \
  RUN_ID="${RUN_ID}" \
  PROFILE="${PROFILE}" \
  MATRIX_VERSION="${MATRIX_VERSION}" \
  MATRIX_SIGNATURE="${MATRIX_SIGNATURE}" \
  MATRIX_ATTACKERS_JSON="${MATRIX_ATTACKERS_JSON}" \
  MATRIX_ATTACK_TYPES_CSV="${MATRIX_ATTACK_TYPES_CSV}" \
  PROGRESS_JSON="${PROGRESS_JSON}" \
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

path = Path(os.environ["PROGRESS_JSON"])
payload = {}
if path.exists() and path.stat().st_size > 0:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            payload = raw
    except Exception:
        payload = {}

payload["run_id"] = os.environ["RUN_ID"]
payload["profile"] = os.environ["PROFILE"]
payload["matrix_version"] = os.environ["MATRIX_VERSION"]
payload["matrix_signature"] = os.environ["MATRIX_SIGNATURE"]
payload["matrix_attackers_json"] = os.environ["MATRIX_ATTACKERS_JSON"]
payload["matrix_attack_types_csv"] = os.environ["MATRIX_ATTACK_TYPES_CSV"]
payload["status"] = os.environ["STATUS"]
payload["combo_index"] = int(os.environ["COMBO_INDEX"])
payload["total_combos"] = int(os.environ["TOTAL_COMBOS"])
payload["current_label"] = os.environ["CURRENT_LABEL"]
payload["current_step"] = os.environ["CURRENT_STEP"]
payload["message"] = os.environ["MESSAGE"]
payload["updated_at_utc"] = datetime.now(timezone.utc).isoformat()

path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

load_or_initialize_session() {
  if [[ "${RESUME}" == "true" ]]; then
    [[ -f "${PROGRESS_JSON}" ]] || die "--resume requested but ${PROGRESS_JSON} does not exist"
    local progress_summary
    progress_summary="$(python3 - "${PROGRESS_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
profile = str(payload.get("profile", "") or "")
matrix_version = str(payload.get("matrix_version", "") or "")
matrix_signature = str(payload.get("matrix_signature", "") or "")
run_id = str(payload.get("run_id", "") or "")
combo_index = int(payload.get("combo_index", 0))
print(profile)
print(matrix_version)
print(matrix_signature)
print(run_id)
print(combo_index)
PY
    )"
    local saved_profile saved_matrix_version saved_matrix_signature saved_run_id checkpoint_index
    mapfile -t _resume_lines <<< "${progress_summary}"
    if (( ${#_resume_lines[@]} != 5 )); then
      die "--resume failed: invalid progress metadata format in ${PROGRESS_JSON}"
    fi
    saved_profile="${_resume_lines[0]}"
    saved_matrix_version="${_resume_lines[1]}"
    saved_matrix_signature="${_resume_lines[2]}"
    saved_run_id="${_resume_lines[3]}"
    checkpoint_index="${_resume_lines[4]}"
    [[ -n "${saved_run_id}" ]] || die "--resume failed: missing run_id in ${PROGRESS_JSON}"
    [[ -n "${saved_matrix_version}" ]] || die "--resume failed: missing matrix_version in ${PROGRESS_JSON}; old matrix state cannot be resumed safely"
    [[ -n "${saved_matrix_signature}" ]] || die "--resume failed: missing matrix_signature in ${PROGRESS_JSON}; old matrix state cannot be resumed safely"
    if [[ -n "${saved_profile}" && "${saved_profile}" != "${PROFILE}" ]]; then
      die "--resume profile mismatch: progress has profile=${saved_profile}, requested profile=${PROFILE}"
    fi
    if [[ "${saved_matrix_version}" != "${MATRIX_VERSION}" ]]; then
      die "--resume matrix_version mismatch: progress=${saved_matrix_version} current=${MATRIX_VERSION}"
    fi
    if [[ "${saved_matrix_signature}" != "${MATRIX_SIGNATURE}" ]]; then
      die "--resume matrix_signature mismatch: progress=${saved_matrix_signature} current=${MATRIX_SIGNATURE}"
    fi
    RUN_ID="${saved_run_id}"
    if (( checkpoint_index > START_INDEX )); then
      START_INDEX="${checkpoint_index}"
    fi
    log "Resuming run_id=${RUN_ID} from combo_index=${START_INDEX}"
    return
  fi

  RUN_ID="$(date -u '+%Y%m%d_%H%M%S')"
  rm -f "${PROGRESS_JSON}" "${RECORDS_JSON}" "${COMPLETED_CSV}" "${FAILURES_CSV}" "${FAILURES_MD}" "${COMBINED_CSV}" "${COMBINED_MD}"
  write_progress "initialized" "${START_INDEX}" "" "" "new session initialized"
  log "Initialized new run_id=${RUN_ID}"
}

load_completed_index_lookup() {
  if [[ ! -f "${RECORDS_JSON}" ]]; then
    return
  fi

  while IFS= read -r index; do
    [[ -n "${index}" ]] || continue
    COMPLETED_INDEX["${index}"]=1
  done < <(
    python3 - "${RECORDS_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists() or path.stat().st_size == 0:
    raise SystemExit(0)
raw = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(raw, dict):
    raise SystemExit(0)
for key, value in raw.items():
    if isinstance(value, dict) and value.get("status") == "success":
        print(str(key))
PY
  )
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

write_combo_configs() {
  ATTACK_TYPE="$1" \
  TARGET_BOOST_POLICY="$2" \
  TARGET_BOOST_STRENGTH="$3" \
  RETRIEVAL_MODE="$4" \
  RANKING_MODE="$5" \
  VICTIM_PROVIDER="$6" \
  VICTIM_MODEL="$7" \
  ATTACKER_PROVIDER="$8" \
  ATTACKER_MODEL="$9" \
  POISON_FRACTION="${10}" \
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
attack_payload["target_boost_strength"] = int(os.environ["TARGET_BOOST_STRENGTH"])
attack_payload["poison_fraction"] = float(os.environ["POISON_FRACTION"])
attack_payload["poison_generation_mode"] = "model_tied"
attack_payload["poison_generator"] = {
    "provider": os.environ["ATTACKER_PROVIDER"],
    "model": os.environ["ATTACKER_MODEL"],
}
attack_payload["poison_prompt_profile"] = "model_tied_v1"
attack_payload["poison_generation_seed"] = 42
attack_payload["poison_temperature"] = 0.0
attack_payload["poison_max_tokens"] = 256
attack_payload["poison_cache_policy"] = "reuse"

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

written_attack = json.loads(attack_path.read_text(encoding="utf-8"))
written_llm = json.loads(llm_path.read_text(encoding="utf-8"))
if not isinstance(written_attack, dict):
    raise SystemExit("written attack config is not a JSON object")
if not isinstance(written_llm, dict):
    raise SystemExit("written llm config is not a JSON object")

if str(written_llm.get("retrieval_mode", "")) != os.environ["RETRIEVAL_MODE"]:
    raise SystemExit("llm_config retrieval_mode mismatch after write")
if str(written_llm.get("ranking_mode", "")) != os.environ["RANKING_MODE"]:
    raise SystemExit("llm_config ranking_mode mismatch after write")

victim = written_llm.get("victim")
attacker = written_llm.get("attacker")
if not isinstance(victim, dict) or not isinstance(attacker, dict):
    raise SystemExit("llm_config victim/attacker sections are invalid after write")

if str(victim.get("provider", "")) != os.environ["VICTIM_PROVIDER"] or str(victim.get("model", "")) != os.environ["VICTIM_MODEL"]:
    raise SystemExit("llm_config victim mismatch after write")
if str(attacker.get("provider", "")) != os.environ["ATTACKER_PROVIDER"] or str(attacker.get("model", "")) != os.environ["ATTACKER_MODEL"]:
    raise SystemExit("llm_config attacker mismatch after write")

if str(written_attack.get("attack_type", "")) != os.environ["ATTACK_TYPE"]:
    raise SystemExit("attack_config attack_type mismatch after write")
if str(written_attack.get("target_boost_policy", "")) != os.environ["TARGET_BOOST_POLICY"]:
    raise SystemExit("attack_config target_boost_policy mismatch after write")
if str(written_attack.get("poison_generation_mode", "")) != "model_tied":
    raise SystemExit("attack_config poison_generation_mode mismatch after write")
poison_generator = written_attack.get("poison_generator")
if not isinstance(poison_generator, dict):
    raise SystemExit("attack_config poison_generator missing/invalid after write")
if str(poison_generator.get("provider", "")) != os.environ["ATTACKER_PROVIDER"] or str(poison_generator.get("model", "")) != os.environ["ATTACKER_MODEL"]:
    raise SystemExit("attack_config poison_generator mismatch after write")
try:
    target_boost_strength = int(written_attack.get("target_boost_strength"))
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"attack_config target_boost_strength invalid after write: {exc}") from exc
if target_boost_strength != int(os.environ["TARGET_BOOST_STRENGTH"]):
    raise SystemExit("attack_config target_boost_strength mismatch after write")

try:
    poison_fraction = float(written_attack.get("poison_fraction"))
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"attack_config poison_fraction invalid after write: {exc}") from exc

if abs(poison_fraction - float(os.environ["POISON_FRACTION"])) > 1e-12:
    raise SystemExit("attack_config poison_fraction mismatch after write")
PY
}

run_step() {
  local run_log="$1"
  local step_name="$2"
  local combo_index="$3"
  local label="$4"
  shift 4

  write_progress "running" "${combo_index}" "${label}" "${step_name}" "executing ${step_name}"
  {
    printf '\n[%s] STEP %s\n' "$(timestamp_utc)" "${step_name}"
    printf '[%s] CMD  %s\n' "$(timestamp_utc)" "$*"
  } | tee -a "${run_log}"

  "$@" 2>&1 | tee -a "${run_log}"
  local cmd_status="${PIPESTATUS[0]}"
  return "${cmd_status}"
}

run_tuning_step() {
  local tuning_log="$1"
  local step_name="$2"
  shift 2

  {
    printf '\n[%s] TUNING_STEP %s\n' "$(timestamp_utc)" "${step_name}"
    printf '[%s] TUNING_CMD  %s\n' "$(timestamp_utc)" "$*"
  } | tee -a "${tuning_log}" >&2

  "$@" 2>&1 | tee -a "${tuning_log}" >&2
  local cmd_status="${PIPESTATUS[0]}"
  return "${cmd_status}"
}

create_error_summary() {
  local run_dir="$1"
  local run_log="$2"
  local combo_index="$3"
  local label="$4"
  local failed_step="$5"
  local error_message="$6"

  local summary_path="${run_dir}/error_summary.md"
  {
    echo "# Run Failure"
    echo
    echo "- run_id: \`${RUN_ID}\`"
    echo "- combo_index: \`${combo_index}\`"
    echo "- label: \`${label}\`"
    echo "- failed_step: \`${failed_step}\`"
    echo "- failed_at_utc: \`$(timestamp_utc)\`"
    echo
    echo "## Error"
    echo
    echo "\`${error_message}\`"
    echo
    echo "## Log Tail"
    echo
    echo '```text'
    tail -n 80 "${run_log}" 2>&1 || true
    echo '```'
  } > "${summary_path}"
}

upsert_record() {
  local combo_index="$1"
  local label="$2"
  local status="$3"
  local failed_step="$4"
  local error_message="$5"
  local attack_type="$6"
  local target_boost_policy="$7"
  local retrieval_mode="$8"
  local ranking_mode="$9"
  local victim_provider="${10}"
  local victim_model="${11}"
  local attacker_provider="${12}"
  local attacker_model="${13}"
  local pair_type="${14}"
  local requested_poison_fraction="${15}"
  local run_dir="${16}"
  local run_log_path="${17}"

  RECORDS_JSON="${RECORDS_JSON}" \
  RUN_ID="${RUN_ID}" \
  COMBO_INDEX="${combo_index}" \
  LABEL="${label}" \
  STATUS="${status}" \
  FAILED_STEP="${failed_step}" \
  ERROR_MESSAGE="${error_message}" \
  ATTACK_TYPE="${attack_type}" \
  TARGET_BOOST_POLICY="${target_boost_policy}" \
  RETRIEVAL_MODE="${retrieval_mode}" \
  RANKING_MODE="${ranking_mode}" \
  VICTIM_PROVIDER="${victim_provider}" \
  VICTIM_MODEL="${victim_model}" \
  ATTACKER_PROVIDER="${attacker_provider}" \
  ATTACKER_MODEL="${attacker_model}" \
  PAIR_TYPE="${pair_type}" \
  REQUESTED_POISON_FRACTION="${requested_poison_fraction}" \
  RUN_DIR="${run_dir}" \
  RUN_LOG_PATH="${run_log_path}" \
  K="${K}" \
  REPEAT_COUNT="${REPEAT_COUNT}" \
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def metric(payload: dict, section: str, name: str):
    block = payload.get(section, {})
    if not isinstance(block, dict):
        return None
    value = block.get(name)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


records_path = Path(os.environ["RECORDS_JSON"])
records = load_json(records_path)

index_key = str(int(os.environ["COMBO_INDEX"]))
record = records.get(index_key, {})
if not isinstance(record, dict):
    record = {}

record.update(
    {
        "run_id": os.environ["RUN_ID"],
        "combo_index": int(os.environ["COMBO_INDEX"]),
        "label": os.environ["LABEL"],
        "status": os.environ["STATUS"],
        "failed_step": os.environ["FAILED_STEP"],
        "error_message": os.environ["ERROR_MESSAGE"],
        "attack_type": os.environ["ATTACK_TYPE"],
        "target_boost_policy": os.environ["TARGET_BOOST_POLICY"],
        "retrieval_mode": os.environ["RETRIEVAL_MODE"],
        "ranking_mode": os.environ["RANKING_MODE"],
        "victim_provider": os.environ["VICTIM_PROVIDER"],
        "victim_model": os.environ["VICTIM_MODEL"],
        "attacker_provider": os.environ["ATTACKER_PROVIDER"],
        "attacker_model": os.environ["ATTACKER_MODEL"],
        "pair_type": os.environ["PAIR_TYPE"],
        "requested_poison_fraction": float(os.environ["REQUESTED_POISON_FRACTION"]),
        "k": int(os.environ["K"]),
        "repeat_count": int(os.environ["REPEAT_COUNT"]),
        "run_dir": os.environ["RUN_DIR"],
        "run_log_path": os.environ["RUN_LOG_PATH"],
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
)

run_dir = Path(os.environ["RUN_DIR"])
metrics_path = run_dir / "metrics.json"
summary_path = run_dir / "summary.md"
delta_csv_path = run_dir / "delta.csv"

record["metrics_path"] = str(metrics_path) if metrics_path.exists() else ""
record["summary_path"] = str(summary_path) if summary_path.exists() else ""
record["delta_csv_path"] = str(delta_csv_path) if delta_csv_path.exists() else ""

attack_runtime = load_json(run_dir / "attack_config.runtime.json")
if attack_runtime:
    record["poison_fraction"] = attack_runtime.get("poison_fraction")
    record["target_movie_id"] = attack_runtime.get("target_movie_id")
    record["target_boost_strength"] = attack_runtime.get("target_boost_strength")
    fields = attack_runtime.get("target_fields", [])
    keywords = attack_runtime.get("keyword_list", [])
    record["target_fields"] = ",".join(str(v) for v in fields) if isinstance(fields, list) else ""
    if isinstance(keywords, list):
        rendered = [str(v).strip() for v in keywords if str(v).strip()]
        if len(rendered) > 5:
            record["keyword_list_summary"] = ",".join(rendered[:5]) + ",..."
        else:
            record["keyword_list_summary"] = ",".join(rendered)
    else:
        record["keyword_list_summary"] = ""

payload = load_json(metrics_path)
if payload:
    record["mode"] = payload.get("mode")
    record["requested_users"] = payload.get("requested_users")
    record["evaluated_users"] = payload.get("evaluated_users")
    record["skipped_users"] = payload.get("skipped_users")

    for section in ("baseline", "attacked", "delta"):
        for name in ("hr", "ndcg", "mrr", "asr"):
            record[f"{section}_{name}"] = metric(payload, section, name)

    target_retrieval = payload.get("target_retrieval", {})
    if isinstance(target_retrieval, dict):
        record["target_retrieval_rank_baseline"] = target_retrieval.get("target_retrieval_mean_rank_baseline")
        record["target_retrieval_rank_attacked"] = target_retrieval.get("target_retrieval_mean_rank_attacked")

records[index_key] = record
records_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
}

render_aggregate_outputs() {
  RECORDS_JSON="${RECORDS_JSON}" \
  COMBINED_CSV="${COMBINED_CSV}" \
  COMBINED_MD="${COMBINED_MD}" \
  FAILURES_CSV="${FAILURES_CSV}" \
  FAILURES_MD="${FAILURES_MD}" \
  COMPLETED_CSV="${COMPLETED_CSV}" \
  RUN_ID="${RUN_ID}" \
  python3 - <<'PY'
import csv
import json
import os
from pathlib import Path

records_path = Path(os.environ["RECORDS_JSON"])
combined_csv = Path(os.environ["COMBINED_CSV"])
combined_md = Path(os.environ["COMBINED_MD"])
failures_csv = Path(os.environ["FAILURES_CSV"])
failures_md = Path(os.environ["FAILURES_MD"])
completed_csv = Path(os.environ["COMPLETED_CSV"])
run_id = os.environ["RUN_ID"]

if not records_path.exists() or records_path.stat().st_size == 0:
    raise SystemExit(0)

raw = json.loads(records_path.read_text(encoding="utf-8"))
if not isinstance(raw, dict):
    raise SystemExit(0)

rows = []
for key, value in raw.items():
    if not isinstance(value, dict):
        continue
    rows.append(value)

rows.sort(key=lambda row: int(row.get("combo_index", 0)))

headers = [
    "combo_index",
    "run_id",
    "label",
    "status",
    "failed_step",
    "error_message",
    "attack_type",
    "target_boost_policy",
    "retrieval_mode",
    "ranking_mode",
    "victim_provider",
    "victim_model",
    "attacker_provider",
    "attacker_model",
    "pair_type",
    "requested_poison_fraction",
    "poison_fraction",
    "target_movie_id",
    "target_boost_strength",
    "target_fields",
    "keyword_list_summary",
    "k",
    "repeat_count",
    "mode",
    "requested_users",
    "evaluated_users",
    "skipped_users",
    "baseline_hr",
    "baseline_ndcg",
    "baseline_mrr",
    "baseline_asr",
    "attacked_hr",
    "attacked_ndcg",
    "attacked_mrr",
    "attacked_asr",
    "delta_hr",
    "delta_ndcg",
    "delta_mrr",
    "delta_asr",
    "target_retrieval_rank_baseline",
    "target_retrieval_rank_attacked",
    "run_dir",
    "run_log_path",
    "metrics_path",
    "summary_path",
    "delta_csv_path",
    "updated_at_utc",
]

with combined_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=headers)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})

success = sum(1 for row in rows if row.get("status") == "success")
failed = sum(1 for row in rows if row.get("status") != "success")

md_lines = []
md_lines.append(f"# Full Sweep Combined Results ({run_id})")
md_lines.append("")
md_lines.append(f"- total_rows: `{len(rows)}`")
md_lines.append(f"- success: `{success}`")
md_lines.append(f"- failed_or_incomplete: `{failed}`")
md_lines.append("")
md_lines.append("Detailed metrics are in `combined_results.csv`.")
md_lines.append("")
md_lines.append(
    "| idx | label | status | attack | retrieval | ranking | victim | attacker | delta_hr | delta_ndcg | delta_mrr | delta_asr | failed_step |"
)
md_lines.append("|---:|---|---|---|---|---|---|---|---:|---:|---:|---:|---|")
for row in rows:
    victim = f"{row.get('victim_provider', '')}:{row.get('victim_model', '')}"
    attacker = f"{row.get('attacker_provider', '')}:{row.get('attacker_model', '')}"
    md_lines.append(
        "| {idx} | {label} | {status} | {attack} | {retrieval} | {ranking} | {victim} | {attacker} | {dhr} | {dndcg} | {dmrr} | {dasr} | {step} |".format(
            idx=row.get("combo_index", ""),
            label=str(row.get("label", "")).replace("|", "/"),
            status=row.get("status", ""),
            attack=row.get("attack_type", ""),
            retrieval=row.get("retrieval_mode", ""),
            ranking=row.get("ranking_mode", ""),
            victim=victim.replace("|", "/"),
            attacker=attacker.replace("|", "/"),
            dhr=row.get("delta_hr", ""),
            dndcg=row.get("delta_ndcg", ""),
            dmrr=row.get("delta_mrr", ""),
            dasr=row.get("delta_asr", ""),
            step=row.get("failed_step", ""),
        )
    )
combined_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

failure_rows = [row for row in rows if row.get("status") != "success"]
with failures_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "combo_index",
            "label",
            "status",
            "failed_step",
            "error_message",
            "attack_type",
            "retrieval_mode",
            "ranking_mode",
            "victim_provider",
            "victim_model",
            "attacker_provider",
            "attacker_model",
            "pair_type",
            "requested_poison_fraction",
            "run_dir",
            "run_log_path",
            "updated_at_utc",
        ],
    )
    writer.writeheader()
    for row in failure_rows:
        writer.writerow(
            {
                "combo_index": row.get("combo_index", ""),
                "label": row.get("label", ""),
                "status": row.get("status", ""),
                "failed_step": row.get("failed_step", ""),
                "error_message": row.get("error_message", ""),
                "attack_type": row.get("attack_type", ""),
                "retrieval_mode": row.get("retrieval_mode", ""),
                "ranking_mode": row.get("ranking_mode", ""),
                "victim_provider": row.get("victim_provider", ""),
                "victim_model": row.get("victim_model", ""),
                "attacker_provider": row.get("attacker_provider", ""),
                "attacker_model": row.get("attacker_model", ""),
                "pair_type": row.get("pair_type", ""),
                "requested_poison_fraction": row.get("requested_poison_fraction", ""),
                "run_dir": row.get("run_dir", ""),
                "run_log_path": row.get("run_log_path", ""),
                "updated_at_utc": row.get("updated_at_utc", ""),
            }
        )

failure_lines = []
failure_lines.append(f"# Full Sweep Failures ({run_id})")
failure_lines.append("")
failure_lines.append(f"- failure_count: `{len(failure_rows)}`")
failure_lines.append("")
if failure_rows:
    for row in failure_rows:
        failure_lines.append(
            "- idx={idx} label=`{label}` step=`{step}` status=`{status}` error=`{error}`".format(
                idx=row.get("combo_index", ""),
                label=row.get("label", ""),
                step=row.get("failed_step", ""),
                status=row.get("status", ""),
                error=str(row.get("error_message", "")).replace("\n", " ").strip(),
            )
        )
        run_log_path = str(row.get("run_log_path", "")).strip()
        if run_log_path:
            failure_lines.append(f"  log: `{run_log_path}`")
else:
    failure_lines.append("No failures recorded.")
failures_md.write_text("\n".join(failure_lines) + "\n", encoding="utf-8")

with completed_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["combo_index", "label", "updated_at_utc"])
    for row in rows:
        if row.get("status") == "success":
            writer.writerow([row.get("combo_index", ""), row.get("label", ""), row.get("updated_at_utc", "")])
PY
}

default_attack_params_for_type() {
  local attack_type="$1"
  case "${attack_type}" in
    targeted_promotion)
      echo "keyword_burst|${TUNING_DEFAULT_STRENGTH}|0.2"
      ;;
    prompt_injection)
      echo "disabled|${TUNING_DISABLED_STRENGTH}|0.2"
      ;;
    untargeted_degradation)
      echo "disabled|${TUNING_DISABLED_STRENGTH}|0.2"
      ;;
    *)
      die "unsupported attack_type for defaults: ${attack_type}"
      ;;
  esac
}

attacker_tag_from_model() {
  local provider="$1"
  local model="$2"
  TAG_INPUT_PROVIDER="${provider}" TAG_INPUT_MODEL="${model}" python3 - <<'PY'
import os
import re

provider = os.environ["TAG_INPUT_PROVIDER"].strip().lower()
model = os.environ["TAG_INPUT_MODEL"].strip().lower()
slug = re.sub(r"[^a-z0-9]+", "", model)
if not slug:
    slug = "mdl"
tag = (provider[:3] + slug[:6])[:9]
print(tag)
PY
}

load_attackers_from_yaml() {
  ATTACKER_SPECS=()
  local attackers_blob
  attackers_blob="$(
    LLM_MODELS_YAML_PATH="${LLM_MODELS_YAML_PATH}" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["LLM_MODELS_YAML_PATH"])
try:
    import yaml
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"PyYAML is required to parse {path}: {exc}") from exc

if not path.exists() or path.stat().st_size == 0:
    raise SystemExit(f"attacker models yaml missing or empty: {path}")

parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
if not isinstance(parsed, dict):
    raise SystemExit(f"invalid llm_models yaml shape (expected mapping): {path}")

rows: list[tuple[str, str]] = []
for provider, raw_models in parsed.items():
    provider_text = str(provider).strip()
    if provider_text == "" or provider_text == "local":
        continue
    if not isinstance(raw_models, list):
        raise SystemExit(f"provider '{provider_text}' must map to a list of models")
    for raw_model in raw_models:
        model = str(raw_model).strip()
        if model == "":
            continue
        rows.append((provider_text, model))

if not rows:
    raise SystemExit(f"no attacker models found in {path}")

seen: set[tuple[str, str]] = set()
for provider, model in rows:
    key = (provider, model)
    if key in seen:
        raise SystemExit(f"duplicate attacker model entry: {provider}:{model}")
    seen.add(key)
    print(f"{provider}|{model}")
PY
  )"

  while IFS= read -r spec; do
    [[ -n "${spec}" ]] || continue
    ATTACKER_SPECS+=("${spec}")
  done <<< "${attackers_blob}"

  if (( ${#ATTACKER_SPECS[@]} != ATTACKER_EXPECTED_COUNT )); then
    die "attacker invariant failed: expected ${ATTACKER_EXPECTED_COUNT} attacker models from ${LLM_MODELS_YAML_PATH}, got ${#ATTACKER_SPECS[@]}"
  fi
}

resolve_stable_victim_from_attackers() {
  local first_spec
  first_spec="${ATTACKER_SPECS[0]}"
  IFS='|' read -r STABLE_VICTIM_PROVIDER STABLE_VICTIM_MODEL <<< "${first_spec}"
  [[ -n "${STABLE_VICTIM_PROVIDER}" && -n "${STABLE_VICTIM_MODEL}" ]] || die "failed to resolve stable victim from attacker specs"
  STABLE_VICTIM_TAG="$(attacker_tag_from_model "${STABLE_VICTIM_PROVIDER}" "${STABLE_VICTIM_MODEL}")"
}

build_matrix_signature() {
  local attackers_json
  attackers_json="$(
    MATRIX_VERSION="${MATRIX_VERSION}" \
    MATRIX_ATTACK_TYPES_CSV="${MATRIX_ATTACK_TYPES_CSV}" \
    ATTACKER_SPECS_BLOB="$(printf '%s\n' "${ATTACKER_SPECS[@]}")" \
    python3 - <<'PY'
import json
import os
import hashlib

rows = [line.strip() for line in os.environ["ATTACKER_SPECS_BLOB"].splitlines() if line.strip()]
attackers = []
for row in rows:
    provider, model = row.split("|", 1)
    attackers.append({"provider": provider, "model": model})
payload = {
    "matrix_version": os.environ["MATRIX_VERSION"],
    "attack_types": [item for item in os.environ["MATRIX_ATTACK_TYPES_CSV"].split(",") if item],
    "retrieval_mode": "hybrid",
    "ranking_mode": "deterministic",
    "poison_generation_mode": "model_tied",
    "poison_prompt_profile": "model_tied_v1",
    "attackers": attackers,
}
rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]
print(json.dumps(attackers, sort_keys=True))
print(digest)
PY
  )"
  local _sig_lines=()
  mapfile -t _sig_lines <<< "${attackers_json}"
  if (( ${#_sig_lines[@]} != 2 )); then
    die "failed to compute matrix signature"
  fi
  MATRIX_ATTACKERS_JSON="${_sig_lines[0]}"
  MATRIX_SIGNATURE="${_sig_lines[1]}"
}

validate_matrix_invariants() {
  local combo_specs_blob
  combo_specs_blob="$(printf '%s\n' "${COMBO_SPECS[@]}")"
  COMBO_SPECS_BLOB="${combo_specs_blob}" \
  ATTACKER_EXPECTED_COUNT="${ATTACKER_EXPECTED_COUNT}" \
  MATRIX_ATTACK_TYPES_CSV="${MATRIX_ATTACK_TYPES_CSV}" \
  python3 - <<'PY'
import os

combo_specs = [line.strip() for line in os.environ["COMBO_SPECS_BLOB"].splitlines() if line.strip()]
expected_attackers = int(os.environ["ATTACKER_EXPECTED_COUNT"])
expected_attacks = set([item for item in os.environ["MATRIX_ATTACK_TYPES_CSV"].split(",") if item])
if expected_attacks != {"targeted_promotion", "prompt_injection", "untargeted_degradation"}:
    raise SystemExit(f"attack-type invariant failed: expected fixed 3 attacks, got {sorted(expected_attacks)}")
if len(combo_specs) != expected_attackers * len(expected_attacks):
    raise SystemExit(
        f"combo-count invariant failed: expected {expected_attackers * len(expected_attacks)} combos, got {len(combo_specs)}"
    )

pairs = set()
attack_types = set()
attackers = set()
for spec in combo_specs:
    parts = spec.split("|")
    if len(parts) != 13:
        raise SystemExit(f"malformed combo spec: {spec}")
    (
        attack_type,
        _target_boost_policy,
        _target_boost_strength,
        retrieval_mode,
        ranking_mode,
        _victim_provider,
        _victim_model,
        _victim_tag,
        attacker_provider,
        attacker_model,
        _attacker_tag,
        _poison_fraction,
        _pair_type,
    ) = parts
    attack_types.add(attack_type)
    attackers.add((attacker_provider, attacker_model))
    if retrieval_mode != "hybrid":
        raise SystemExit(f"retrieval invariant failed: found retrieval_mode={retrieval_mode}")
    if ranking_mode != "deterministic":
        raise SystemExit(f"ranking invariant failed: found ranking_mode={ranking_mode}")
    if ranking_mode == "llm_rerank":
        raise SystemExit("llm_rerank is forbidden in deterministic matrix")
    if retrieval_mode in {"lexical", "dense"}:
        raise SystemExit("lexical/dense are forbidden in deterministic matrix")
    pair = (attacker_provider, attacker_model, attack_type)
    if pair in pairs:
        raise SystemExit(f"duplicate attacker+attack pair: {pair}")
    pairs.add(pair)

if attack_types != expected_attacks:
    raise SystemExit(
        f"attack-type invariant failed: expected={sorted(expected_attacks)} actual={sorted(attack_types)}"
    )
if len(attackers) != expected_attackers:
    raise SystemExit(
        f"attacker-count invariant failed: expected={expected_attackers} actual={len(attackers)}"
    )
if len(pairs) != expected_attackers * len(expected_attacks):
    raise SystemExit(
        f"pair coverage invariant failed: expected={expected_attackers * len(expected_attacks)} actual={len(pairs)}"
    )
PY
}

resolve_attack_params_for_type() {
  local attack_type="$1"

  if [[ -f "${BEST_ATTACK_PARAMS_JSON}" && -s "${BEST_ATTACK_PARAMS_JSON}" ]]; then
    local resolved
    resolved="$(
      python3 - "${BEST_ATTACK_PARAMS_JSON}" "${attack_type}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
attack_type = sys.argv[2]
payload = json.loads(path.read_text(encoding="utf-8"))
section = payload.get(attack_type)
if not isinstance(section, dict):
    raise SystemExit(1)
policy = str(section.get("target_boost_policy", "")).strip()
if policy not in {"disabled", "keyword_burst", "aggressive"}:
    raise SystemExit(1)
strength = int(section.get("target_boost_strength"))
if strength <= 0:
    raise SystemExit(1)
poison_fraction = float(section.get("poison_fraction"))
if poison_fraction <= 0.0 or poison_fraction > 1.0:
    raise SystemExit(1)
print(f"{policy}|{strength}|{poison_fraction}")
PY
    )" || true
    if [[ -n "${resolved}" ]]; then
      echo "${resolved}"
      return
    fi
  fi

  default_attack_params_for_type "${attack_type}"
}

tuning_score_from_metrics() {
  local attack_type="$1"
  local metrics_path="$2"
  python3 - "${attack_type}" "${metrics_path}" "${TUNING_HARD_FAIL_SCORE}" <<'PY'
import json
import sys
from pathlib import Path

attack_type = sys.argv[1]
path = Path(sys.argv[2])
hard_fail = float(sys.argv[3])

if not path.exists() or path.stat().st_size == 0:
    print(hard_fail)
    raise SystemExit(0)

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print(hard_fail)
    raise SystemExit(0)

delta = payload.get("delta")
if not isinstance(delta, dict):
    print(hard_fail)
    raise SystemExit(0)

if attack_type in {"targeted_promotion", "prompt_injection"}:
    value = delta.get("asr")
    try:
        print(float(value))
    except Exception:
        print(hard_fail)
    raise SystemExit(0)

value = delta.get("ndcg")
try:
    print(-float(value))
except Exception:
    print(hard_fail)
PY
}

sanitize_tuning_score() {
  local raw_score="$1"
  RAW_SCORE="${raw_score}" \
  HARD_FAIL="${TUNING_HARD_FAIL_SCORE}" \
  python3 - <<'PY'
import math
import os

raw = os.environ["RAW_SCORE"].strip()
hard_fail = float(os.environ["HARD_FAIL"])

try:
    value = float(raw)
except Exception:
    print(hard_fail)
    raise SystemExit(0)

if not math.isfinite(value):
    print(hard_fail)
    raise SystemExit(0)

print(value)
PY
}

evaluate_tuning_candidate() {
  local attack_type="$1"
  local target_boost_policy="$2"
  local target_boost_strength="$3"
  local poison_fraction="$4"
  local candidate_key="$5"
  local tuning_log="${TUNING_RUN_LOG:-${STATE_LOGS_DIR}/tuning_${RUN_ID}.log}"

  if ! write_combo_configs \
      "${attack_type}" \
      "${target_boost_policy}" \
      "${target_boost_strength}" \
      "hybrid" \
      "deterministic" \
      "${STABLE_VICTIM_PROVIDER}" \
      "${STABLE_VICTIM_MODEL}" \
      "${STABLE_VICTIM_PROVIDER}" \
      "${STABLE_VICTIM_MODEL}" \
      "${poison_fraction}"; then
    echo "${TUNING_HARD_FAIL_SCORE}"
    return 0
  fi

  if ! run_tuning_step "${tuning_log}" "attack_build_poisoned_${candidate_key}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli attack build-poisoned; then
    echo "${TUNING_HARD_FAIL_SCORE}"
    return 0
  fi
  if ! run_tuning_step "${tuning_log}" "index_poisoned_${candidate_key}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index poisoned; then
    echo "${TUNING_HARD_FAIL_SCORE}"
    return 0
  fi

  local tuning_label metrics_path score
  score="${TUNING_HARD_FAIL_SCORE}"
  tuning_label="tune_${RUN_ID}_$(attack_tag "${attack_type}")_${candidate_key}"
  if run_tuning_step "${tuning_log}" "eval_run_${candidate_key}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli eval run \
      --mode batch \
      --batch-size "${TUNING_BATCH_SIZE}" \
      --label "${tuning_label}" \
      --k "${K}" \
      --repeat-count 1 \
      --seed "${SEED}" \
      --results-root "${TUNING_RESULTS_ROOT}" \
      --overwrite; then
    metrics_path="${TUNING_RESULTS_ROOT}/${tuning_label}/metrics.json"
    score="$(tuning_score_from_metrics "${attack_type}" "${metrics_path}")"
  fi
  echo "${score}"
}

select_best_tuning_candidate() {
  local csv_path="$1"
  local stage="$2"
  python3 - "${csv_path}" "${stage}" <<'PY'
import csv
import math
import sys
from pathlib import Path

path = Path(sys.argv[1])
stage = sys.argv[2]
raw_rows = list(csv.DictReader(path.open(encoding="utf-8")))
if not raw_rows:
    raise SystemExit("no tuning rows to select from")

policy_rank = {"keyword_burst": 0, "aggressive": 1, "disabled": 2}

def as_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default

def as_int(value: object, default: int) -> int:
    try:
        return int(float(value))  # type: ignore[arg-type]
    except Exception:
        return default

rows: list[dict[str, object]] = []
for raw in raw_rows:
    if not isinstance(raw, dict):
        continue
    policy = str(raw.get("policy", "")).strip()
    if policy not in policy_rank:
        continue
    strength = as_int(raw.get("strength"), 1_000_000_000)
    poison_fraction = as_float(raw.get("poison_fraction"), 1_000_000_000.0)
    score = as_float(raw.get("mean_score"), -1_000_000_000.0)
    if strength <= 0:
        continue
    if not math.isfinite(poison_fraction) or poison_fraction <= 0.0 or poison_fraction > 1.0:
        continue
    if not math.isfinite(score):
        continue
    rows.append(
        {
            "policy": policy,
            "strength": strength,
            "poison_fraction": poison_fraction,
            "mean_score": score,
        }
    )

if not rows:
    raise SystemExit("no valid tuning rows after filtering malformed/non-numeric entries")

def sort_key(row: dict[str, object]) -> tuple[float, float, int, int]:
    score = float(row["mean_score"])
    poison_fraction = float(row["poison_fraction"])
    strength = int(row["strength"])
    policy = str(row["policy"])
    p_rank = policy_rank.get(policy, 99)

    if stage == "targeted_stage1":
        return (-score, float(strength), p_rank, poison_fraction)
    if stage == "targeted_stage2":
        return (-score, poison_fraction, float(strength), p_rank)
    return (-score, poison_fraction, float(strength), p_rank)

best = min(rows, key=sort_key)
policy = str(best["policy"])
strength = int(best["strength"])
poison_fraction = float(best["poison_fraction"])
score = float(best["mean_score"])
print(f"{policy}|{strength}|{poison_fraction}|{score}")
PY
}

purge_tuning_artifacts() {
  rm -f "${BEST_ATTACK_PARAMS_JSON}" \
        "${STATE_DIR}/tuning_targeted_stage1.csv" \
        "${STATE_DIR}/tuning_targeted_stage2.csv" \
        "${STATE_DIR}/tuning_prompt_injection.csv" \
        "${STATE_DIR}/tuning_untargeted.csv"
}

validate_best_attack_params_cache() {
  local cache_path="$1"
  BEST_ATTACK_PARAMS_PATH="${cache_path}" python3 - <<'PY'
import json
import math
import os
from pathlib import Path

path = Path(os.environ["BEST_ATTACK_PARAMS_PATH"])
if not path.exists() or path.stat().st_size == 0:
    raise SystemExit("cache file missing or empty")

try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"invalid json: {exc}") from exc

if not isinstance(payload, dict):
    raise SystemExit("cache payload must be a JSON object")

required = ("targeted_promotion", "prompt_injection", "untargeted_degradation")
valid_policies = {"disabled", "keyword_burst", "aggressive"}

for attack_type in required:
    section = payload.get(attack_type)
    if not isinstance(section, dict):
        raise SystemExit(f"missing section: {attack_type}")

    policy = str(section.get("target_boost_policy", "")).strip()
    if policy not in valid_policies:
        raise SystemExit(f"{attack_type}.target_boost_policy invalid: {policy!r}")

    try:
        strength = int(section.get("target_boost_strength"))
    except Exception as exc:
        raise SystemExit(f"{attack_type}.target_boost_strength invalid: {exc}") from exc
    if strength <= 0:
        raise SystemExit(f"{attack_type}.target_boost_strength must be > 0")

    try:
        poison_fraction = float(section.get("poison_fraction"))
    except Exception as exc:
        raise SystemExit(f"{attack_type}.poison_fraction invalid: {exc}") from exc
    if not math.isfinite(poison_fraction) or poison_fraction <= 0.0 or poison_fraction > 1.0:
        raise SystemExit(f"{attack_type}.poison_fraction out of range: {poison_fraction}")
PY
}

tune_attack_params() {
  mkdir -p "${TUNING_RESULTS_ROOT}"
  TUNING_RUN_LOG="${STATE_LOGS_DIR}/tuning_${RUN_ID}.log"
  : > "${TUNING_RUN_LOG}"
  purge_tuning_artifacts

  log "tuning_start matrix=${MATRIX_VERSION} results_root=${TUNING_RESULTS_ROOT} batch_size=${TUNING_BATCH_SIZE} retrieval_mode=hybrid ranking_mode=deterministic tuning_log=${TUNING_RUN_LOG}"
  if ! run_tuning_step "${TUNING_RUN_LOG}" "index_baseline" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index baseline; then
    die "tuning failed: baseline indexing failed"
  fi

  local targeted_stage1_csv="${STATE_DIR}/tuning_targeted_stage1.csv"
  local targeted_stage2_csv="${STATE_DIR}/tuning_targeted_stage2.csv"
  local prompt_csv="${STATE_DIR}/tuning_prompt_injection.csv"
  local untargeted_csv="${STATE_DIR}/tuning_untargeted.csv"

  printf 'policy,strength,poison_fraction,mean_score\n' > "${targeted_stage1_csv}"
  local policy strength mean_score candidate_key
  for policy in "${TUNING_TARGET_POLICIES[@]}"; do
    for strength in "${TUNING_TARGET_STRENGTHS[@]}"; do
      candidate_key="tgt1_${policy}_s${strength}_p0p2"
      mean_score="$(evaluate_tuning_candidate "targeted_promotion" "${policy}" "${strength}" "0.2" "${candidate_key}")"
      mean_score="$(sanitize_tuning_score "${mean_score}")"
      printf '%s,%s,%s,%s\n' "${policy}" "${strength}" "0.2" "${mean_score}" >> "${targeted_stage1_csv}"
      log "tuning_targeted_stage1 policy=${policy} strength=${strength} poison_fraction=0.2 mean_score=${mean_score}"
    done
  done

  local targeted_stage1_best targeted_policy targeted_strength targeted_poison targeted_stage1_score
  targeted_stage1_best="$(select_best_tuning_candidate "${targeted_stage1_csv}" "targeted_stage1")"
  IFS='|' read -r targeted_policy targeted_strength targeted_poison targeted_stage1_score <<< "${targeted_stage1_best}"

  printf 'policy,strength,poison_fraction,mean_score\n' > "${targeted_stage2_csv}"
  local poison_fraction targeted_final_score
  for poison_fraction in "${TUNING_POISON_FRACTIONS[@]}"; do
    candidate_key="tgt2_${targeted_policy}_s${targeted_strength}_p${poison_fraction//./p}"
    mean_score="$(evaluate_tuning_candidate "targeted_promotion" "${targeted_policy}" "${targeted_strength}" "${poison_fraction}" "${candidate_key}")"
    mean_score="$(sanitize_tuning_score "${mean_score}")"
    printf '%s,%s,%s,%s\n' "${targeted_policy}" "${targeted_strength}" "${poison_fraction}" "${mean_score}" >> "${targeted_stage2_csv}"
    log "tuning_targeted_stage2 policy=${targeted_policy} strength=${targeted_strength} poison_fraction=${poison_fraction} mean_score=${mean_score}"
  done
  local targeted_stage2_best
  targeted_stage2_best="$(select_best_tuning_candidate "${targeted_stage2_csv}" "targeted_stage2")"
  IFS='|' read -r targeted_policy targeted_strength targeted_poison targeted_final_score <<< "${targeted_stage2_best}"

  local prompt_policy="disabled"
  local prompt_strength="${TUNING_DISABLED_STRENGTH}"
  local prompt_poison prompt_score prompt_best
  printf 'policy,strength,poison_fraction,mean_score\n' > "${prompt_csv}"
  for poison_fraction in "${TUNING_POISON_FRACTIONS[@]}"; do
    candidate_key="pinj_${prompt_policy}_s${prompt_strength}_p${poison_fraction//./p}"
    mean_score="$(evaluate_tuning_candidate "prompt_injection" "${prompt_policy}" "${prompt_strength}" "${poison_fraction}" "${candidate_key}")"
    mean_score="$(sanitize_tuning_score "${mean_score}")"
    printf '%s,%s,%s,%s\n' "${prompt_policy}" "${prompt_strength}" "${poison_fraction}" "${mean_score}" >> "${prompt_csv}"
    log "tuning_prompt_injection poison_fraction=${poison_fraction} mean_score=${mean_score}"
  done
  prompt_best="$(select_best_tuning_candidate "${prompt_csv}" "prompt")"
  IFS='|' read -r prompt_policy prompt_strength prompt_poison prompt_score <<< "${prompt_best}"

  local untargeted_policy="disabled"
  local untargeted_strength="${TUNING_DISABLED_STRENGTH}"
  local untargeted_poison untargeted_score untargeted_best
  printf 'policy,strength,poison_fraction,mean_score\n' > "${untargeted_csv}"
  for poison_fraction in "${TUNING_POISON_FRACTIONS[@]}"; do
    candidate_key="udeg_${untargeted_policy}_s${untargeted_strength}_p${poison_fraction//./p}"
    mean_score="$(evaluate_tuning_candidate "untargeted_degradation" "${untargeted_policy}" "${untargeted_strength}" "${poison_fraction}" "${candidate_key}")"
    mean_score="$(sanitize_tuning_score "${mean_score}")"
    printf '%s,%s,%s,%s\n' "${untargeted_policy}" "${untargeted_strength}" "${poison_fraction}" "${mean_score}" >> "${untargeted_csv}"
    log "tuning_untargeted poison_fraction=${poison_fraction} mean_score=${mean_score}"
  done
  untargeted_best="$(select_best_tuning_candidate "${untargeted_csv}" "untargeted")"
  IFS='|' read -r untargeted_policy untargeted_strength untargeted_poison untargeted_score <<< "${untargeted_best}"

  TARGETED_POLICY="${targeted_policy}" \
  TARGETED_STRENGTH="${targeted_strength}" \
  TARGETED_POISON="${targeted_poison}" \
  TARGETED_SCORE="${targeted_final_score}" \
  PROMPT_POLICY="${prompt_policy}" \
  PROMPT_STRENGTH="${prompt_strength}" \
  PROMPT_POISON="${prompt_poison}" \
  PROMPT_SCORE="${prompt_score}" \
  UNTARGETED_POLICY="${untargeted_policy}" \
  UNTARGETED_STRENGTH="${untargeted_strength}" \
  UNTARGETED_POISON="${untargeted_poison}" \
  UNTARGETED_SCORE="${untargeted_score}" \
  BEST_ATTACK_PARAMS_JSON="${BEST_ATTACK_PARAMS_JSON}" \
  RUN_ID="${RUN_ID}" \
  TUNING_BATCH_SIZE="${TUNING_BATCH_SIZE}" \
  python3 - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

payload = {
    "metadata": {
        "run_id": os.environ["RUN_ID"],
        "tuned_at_utc": datetime.now(timezone.utc).isoformat(),
        "tuning_batch_size": int(os.environ["TUNING_BATCH_SIZE"]),
    },
    "targeted_promotion": {
        "target_boost_policy": os.environ["TARGETED_POLICY"],
        "target_boost_strength": int(os.environ["TARGETED_STRENGTH"]),
        "poison_fraction": float(os.environ["TARGETED_POISON"]),
        "objective": "delta_asr",
        "mean_score": float(os.environ["TARGETED_SCORE"]),
    },
    "prompt_injection": {
        "target_boost_policy": os.environ["PROMPT_POLICY"],
        "target_boost_strength": int(os.environ["PROMPT_STRENGTH"]),
        "poison_fraction": float(os.environ["PROMPT_POISON"]),
        "objective": "delta_asr",
        "mean_score": float(os.environ["PROMPT_SCORE"]),
    },
    "untargeted_degradation": {
        "target_boost_policy": os.environ["UNTARGETED_POLICY"],
        "target_boost_strength": int(os.environ["UNTARGETED_STRENGTH"]),
        "poison_fraction": float(os.environ["UNTARGETED_POISON"]),
        "objective": "neg_delta_ndcg",
        "mean_score": float(os.environ["UNTARGETED_SCORE"]),
    },
}
path = Path(os.environ["BEST_ATTACK_PARAMS_JSON"])
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

  log "tuning_complete params_file=${BEST_ATTACK_PARAMS_JSON}"
  log "tuned_targeted policy=${targeted_policy} strength=${targeted_strength} poison_fraction=${targeted_poison} score=${targeted_final_score}"
  log "tuned_prompt policy=${prompt_policy} strength=${prompt_strength} poison_fraction=${prompt_poison} score=${prompt_score}"
  log "tuned_untargeted policy=${untargeted_policy} strength=${untargeted_strength} poison_fraction=${untargeted_poison} score=${untargeted_score}"
}

ensure_tuning() {
  local cache_validation_message
  if [[ "${DRY_RUN}" == "true" ]]; then
    if [[ -f "${BEST_ATTACK_PARAMS_JSON}" && -s "${BEST_ATTACK_PARAMS_JSON}" && "${FORCE_RETUNE}" != "true" ]]; then
      if cache_validation_message="$(validate_best_attack_params_cache "${BEST_ATTACK_PARAMS_JSON}" 2>&1)"; then
        TUNING_PLAN_STATUS="dry_run_would_reuse_cached"
      else
        TUNING_PLAN_STATUS="dry_run_would_retune_invalid_cache"
      fi
    else
      TUNING_PLAN_STATUS="dry_run_would_retune"
    fi
    return
  fi
  if [[ -f "${BEST_ATTACK_PARAMS_JSON}" && -s "${BEST_ATTACK_PARAMS_JSON}" && "${FORCE_RETUNE}" != "true" ]]; then
    if cache_validation_message="$(validate_best_attack_params_cache "${BEST_ATTACK_PARAMS_JSON}" 2>&1)"; then
      TUNING_PLAN_STATUS="reuse_cached"
      log "reuse_tuned_params file=${BEST_ATTACK_PARAMS_JSON}"
      return
    fi
    log "invalid_tuned_params_cache file=${BEST_ATTACK_PARAMS_JSON} details=${cache_validation_message//$'\n'/ ; }"
    purge_tuning_artifacts
    TUNING_PLAN_STATUS="retune_invalid_cache"
    tune_attack_params
    return
  fi
  TUNING_PLAN_STATUS="retune"
  purge_tuning_artifacts
  tune_attack_params
}

load_matrix() {
  COMBO_SPECS=()
  local attack_types
  attack_types=("targeted_promotion" "prompt_injection" "untargeted_degradation")
  local attack_type attacker_spec attacker_provider attacker_model attacker_tag tuned
  local target_boost_policy target_boost_strength poison_fraction
  for attacker_spec in "${ATTACKER_SPECS[@]}"; do
    IFS='|' read -r attacker_provider attacker_model <<< "${attacker_spec}"
    attacker_tag="$(attacker_tag_from_model "${attacker_provider}" "${attacker_model}")"
    for attack_type in "${attack_types[@]}"; do
      tuned="$(resolve_attack_params_for_type "${attack_type}")"
      IFS='|' read -r target_boost_policy target_boost_strength poison_fraction <<< "${tuned}"
      COMBO_SPECS+=(
        "${attack_type}|${target_boost_policy}|${target_boost_strength}|hybrid|deterministic|${STABLE_VICTIM_PROVIDER}|${STABLE_VICTIM_MODEL}|${STABLE_VICTIM_TAG}|${attacker_provider}|${attacker_model}|${attacker_tag}|${poison_fraction}|det_hyb_attacker5x3"
      )
    done
  done
  TOTAL_COMBOS="${#COMBO_SPECS[@]}"
  validate_matrix_invariants
}

run_combo() {
  local combo_index="$1"
  local attack_type="$2"
  local target_boost_policy="$3"
  local target_boost_strength="$4"
  local retrieval_mode="$5"
  local ranking_mode="$6"
  local victim_provider="$7"
  local victim_model="$8"
  local victim_tag="$9"
  local attacker_provider="${10}"
  local attacker_model="${11}"
  local attacker_tag="${12}"
  local poison_fraction="${13}"
  local pair_type="${14}"

  local a_tag b_tag r_tag k_tag poison_tag combo_key combo_hash label run_dir run_log
  a_tag="$(attack_tag "${attack_type}")"
  b_tag="$(boost_tag "${target_boost_policy}")"
  r_tag="$(retrieval_tag "${retrieval_mode}")"
  k_tag="$(ranking_tag "${ranking_mode}")"
  poison_tag="${poison_fraction//./p}"
  combo_key="${RUN_ID}|${combo_index}|${attack_type}|${target_boost_policy}|${target_boost_strength}|${retrieval_mode}|${ranking_mode}|${victim_provider}|${victim_model}|${attacker_provider}|${attacker_model}|${poison_fraction}|${pair_type}"
  combo_hash="$(short_hash "${combo_key}")"
  label="det_hyb_${a_tag}_${attacker_tag}_p${poison_tag}_$(printf '%02d' "${combo_index}")_${combo_hash}"
  run_dir="${RESULTS_ROOT}/${label}"
  mkdir -p "${run_dir}"
  run_log="${STATE_LOGS_DIR}/${label}.log"
  ln -sfn "${REPO_ROOT}/${run_log}" "${run_dir}/run.log"

  {
    echo
    echo "[$(timestamp_utc)] ===== combo_attempt_start ====="
    echo "[$(timestamp_utc)] run_id=${RUN_ID}"
    echo "[$(timestamp_utc)] combo_index=${combo_index}/${TOTAL_COMBOS}"
    echo "[$(timestamp_utc)] label=${label}"
    echo "[$(timestamp_utc)] attack_type=${attack_type} target_boost_policy=${target_boost_policy} target_boost_strength=${target_boost_strength} poison_fraction=${poison_fraction}"
    echo "[$(timestamp_utc)] retrieval_mode=${retrieval_mode} ranking_mode=${ranking_mode}"
    echo "[$(timestamp_utc)] poison_generation_mode=model_tied poison_generator=${attacker_provider}:${attacker_model} poison_prompt_profile=model_tied_v1"
    echo "[$(timestamp_utc)] pair_type=${pair_type} victim=${victim_provider}:${victim_model} attacker=${attacker_provider}:${attacker_model}"
  } | tee -a "${run_log}"

  if ! write_combo_configs \
      "${attack_type}" \
      "${target_boost_policy}" \
      "${target_boost_strength}" \
      "${retrieval_mode}" \
      "${ranking_mode}" \
      "${victim_provider}" \
      "${victim_model}" \
      "${attacker_provider}" \
      "${attacker_model}" \
      "${poison_fraction}"; then
    local error_message="failed to write attack/llm config for combo"
    create_error_summary "${run_dir}" "${run_log}" "${combo_index}" "${label}" "write_config" "${error_message}"
    upsert_record \
      "${combo_index}" "${label}" "failed" "write_config" "${error_message}" \
      "${attack_type}" "${target_boost_policy}" "${retrieval_mode}" "${ranking_mode}" \
      "${victim_provider}" "${victim_model}" "${attacker_provider}" "${attacker_model}" "${pair_type}" "${poison_fraction}" \
      "${run_dir}" "${run_log}"
    write_progress "failed" "${combo_index}" "${label}" "write_config" "${error_message}"
    return 1
  fi

  local failed_step=""
  if ! run_step "${run_log}" "index_baseline" "${combo_index}" "${label}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index baseline; then
    failed_step="index_baseline"
  elif ! run_step "${run_log}" "attack_build_poisoned" "${combo_index}" "${label}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli attack build-poisoned; then
    failed_step="attack_build_poisoned"
  elif ! run_step "${run_log}" "index_poisoned" "${combo_index}" "${label}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli index poisoned; then
    failed_step="index_poisoned"
  else
    local -a eval_cmd
    eval_cmd=(
      env
      "ELASTICSEARCH_URL=${ES_URL}"
      uv
      run
      --project
      api
      python
      -m
      api.app.cli.cli
      eval
      run
      --mode
      "${EVAL_MODE}"
      --label
      "${label}"
      --k
      "${K}"
      --repeat-count
      "${REPEAT_COUNT}"
      --seed
      "${SEED}"
      --results-root
      "${RESULTS_ROOT}"
      --overwrite
    )
    if ! run_step "${run_log}" "eval_run" "${combo_index}" "${label}" "${eval_cmd[@]}"; then
      failed_step="eval_run"
    elif ! run_step "${run_log}" "report_generate" "${combo_index}" "${label}" env ELASTICSEARCH_URL="${ES_URL}" uv run --project api python -m api.app.cli.cli report generate --label "${label}" --results-root "${RESULTS_ROOT}"; then
      failed_step="report_generate"
    fi
  fi

  if [[ -n "${failed_step}" ]]; then
    local error_message
    error_message="step ${failed_step} failed (see run.log)"
    create_error_summary "${run_dir}" "${run_log}" "${combo_index}" "${label}" "${failed_step}" "${error_message}"
    upsert_record \
      "${combo_index}" "${label}" "failed" "${failed_step}" "${error_message}" \
      "${attack_type}" "${target_boost_policy}" "${retrieval_mode}" "${ranking_mode}" \
      "${victim_provider}" "${victim_model}" "${attacker_provider}" "${attacker_model}" "${pair_type}" "${poison_fraction}" \
      "${run_dir}" "${run_log}"
    write_progress "failed" "${combo_index}" "${label}" "${failed_step}" "${error_message}"
    return 1
  fi

  upsert_record \
    "${combo_index}" "${label}" "success" "" "" \
    "${attack_type}" "${target_boost_policy}" "${retrieval_mode}" "${ranking_mode}" \
    "${victim_provider}" "${victim_model}" "${attacker_provider}" "${attacker_model}" "${pair_type}" "${poison_fraction}" \
    "${run_dir}" "${run_log}"
  COMPLETED_INDEX["${combo_index}"]=1
  write_progress "running" "${combo_index}" "${label}" "completed" "combo completed"
  return 0
}

main() {
  parse_args "$@"
  validate_args
  load_attackers_from_yaml
  resolve_stable_victim_from_attackers
  build_matrix_signature
  init_paths
  load_or_initialize_session
  backup_configs
  trap cleanup EXIT INT TERM
  ensure_tuning
  load_matrix
  load_completed_index_lookup

  log "repo_root=${REPO_ROOT}"
  log "es_url=${ES_URL}"
  log "results_root=${RESULTS_ROOT}"
  log "profile=${PROFILE} (deterministic matrix only)"
  log "matrix_version=${MATRIX_VERSION} matrix_signature=${MATRIX_SIGNATURE}"
  log "run_id=${RUN_ID}"
  log "k=${K} repeat_count=${REPEAT_COUNT} seed=${SEED}"
  log "eval_mode=${EVAL_MODE} (full users; corpus indices movies/movies_poisoned)"
  log "retrieval_mode=hybrid ranking_mode=deterministic poison_generation_mode=model_tied"
  log "attack_types=${MATRIX_ATTACK_TYPES_CSV}"
  log "attacker_count=${#ATTACKER_SPECS[@]} expected=${ATTACKER_EXPECTED_COUNT}"
  local attacker_spec attacker_provider attacker_model attacker_tag
  local attacker_row=0
  for attacker_spec in "${ATTACKER_SPECS[@]}"; do
    IFS='|' read -r attacker_provider attacker_model <<< "${attacker_spec}"
    attacker_tag="$(attacker_tag_from_model "${attacker_provider}" "${attacker_model}")"
    log "attacker[$((attacker_row + 1))]=${attacker_provider}:${attacker_model} tag=${attacker_tag}"
    attacker_row=$((attacker_row + 1))
  done
  log "total_combos=${TOTAL_COMBOS}"
  if [[ -f "${BEST_ATTACK_PARAMS_JSON}" && -s "${BEST_ATTACK_PARAMS_JSON}" ]]; then
    log "best_attack_params_json=${BEST_ATTACK_PARAMS_JSON}"
  else
    log "best_attack_params_json=missing (defaults will be used until tuning writes cache)"
  fi
  log "tuning_plan_status=${TUNING_PLAN_STATUS}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    local planned
    if [[ -n "${MAX_RUNS}" ]]; then
      planned="${MAX_RUNS}"
    else
      planned=$(( TOTAL_COMBOS - START_INDEX ))
    fi
    log "dry_run=true start_index=${START_INDEX} planned_runs=${planned}"
    local preview_index=0
    local preview_attack_type preview_target_boost_policy preview_target_boost_strength preview_retrieval_mode preview_ranking_mode
    local preview_victim_provider preview_victim_model preview_victim_tag preview_attacker_provider preview_attacker_model preview_attacker_tag
    local preview_poison_fraction preview_pair_type preview_spec
    for ((preview_index=0; preview_index<TOTAL_COMBOS; preview_index++)); do
      preview_spec="${COMBO_SPECS[$preview_index]}"
      IFS='|' read -r \
        preview_attack_type \
        preview_target_boost_policy \
        preview_target_boost_strength \
        preview_retrieval_mode \
        preview_ranking_mode \
        preview_victim_provider \
        preview_victim_model \
        preview_victim_tag \
        preview_attacker_provider \
        preview_attacker_model \
        preview_attacker_tag \
        preview_poison_fraction \
        preview_pair_type <<< "${preview_spec}"
      log "matrix_row idx=${preview_index} attack_type=${preview_attack_type} attacker_provider=${preview_attacker_provider} attacker_model=${preview_attacker_model} attacker_tag=${preview_attacker_tag} retrieval_mode=${preview_retrieval_mode} ranking_mode=${preview_ranking_mode} poison_fraction=${preview_poison_fraction}"
    done
    write_progress "dry_run" "${START_INDEX}" "" "" "dry run only"
    exit 0
  fi

  local processed_this_invocation=0
  local combo_index=0
  local attack_type target_boost_policy target_boost_strength retrieval_mode ranking_mode
  local victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag
  local poison_fraction pair_type combo_spec
  for ((combo_index=0; combo_index<TOTAL_COMBOS; combo_index++)); do
    combo_spec="${COMBO_SPECS[$combo_index]}"
    IFS='|' read -r \
      attack_type \
      target_boost_policy \
      target_boost_strength \
      retrieval_mode \
      ranking_mode \
      victim_provider \
      victim_model \
      victim_tag \
      attacker_provider \
      attacker_model \
      attacker_tag \
      poison_fraction \
      pair_type <<< "${combo_spec}"

    if (( combo_index < START_INDEX )); then
      continue
    fi
    if [[ -n "${MAX_RUNS}" ]] && (( processed_this_invocation >= MAX_RUNS )); then
      break
    fi
    if [[ "${COMPLETED_INDEX[${combo_index}]:-0}" == "1" ]]; then
      log "Skipping completed combo_index=${combo_index}"
      continue
    fi

    processed_this_invocation=$((processed_this_invocation + 1))
    log "Running combo_index=${combo_index} processed_this_invocation=${processed_this_invocation}"
    if ! run_combo \
      "${combo_index}" \
      "${attack_type}" \
      "${target_boost_policy}" \
      "${target_boost_strength}" \
      "${retrieval_mode}" \
      "${ranking_mode}" \
      "${victim_provider}" \
      "${victim_model}" \
      "${victim_tag}" \
      "${attacker_provider}" \
      "${attacker_model}" \
      "${attacker_tag}" \
      "${poison_fraction}" \
      "${pair_type}"; then
      render_aggregate_outputs
      if [[ "${FAIL_FAST}" == "true" ]]; then
        write_progress "failed" "${combo_index}" "" "" "stopped on first failure"
        die "Stopped at combo_index=${combo_index} (resume with --resume)"
      fi
    fi

    render_aggregate_outputs
  done

  render_aggregate_outputs
  write_progress "completed" "${combo_index}" "" "" "session completed or max-runs reached"
  log "Sweep finished. processed_this_invocation=${processed_this_invocation}"
  log "Combined CSV: ${COMBINED_CSV}"
  log "Combined MD: ${COMBINED_MD}"
  log "Failures CSV: ${FAILURES_CSV}"
  log "Checkpoint: ${PROGRESS_JSON}"
}

main "$@"
