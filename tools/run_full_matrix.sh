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
PROFILE="forty_mixed"

STATE_DIR=""
PROGRESS_JSON=""
RECORDS_JSON=""
COMBINED_CSV=""
COMBINED_MD=""
FAILURES_CSV=""
FAILURES_MD=""
COMPLETED_CSV=""

RUN_ID=""
TOTAL_COMBOS=0

BACKUP_ATTACK_CONFIG=""
BACKUP_LLM_CONFIG=""

declare -A COMPLETED_INDEX
declare -a COMBO_SPECS

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
  --profile NAME              Matrix profile: forty_mixed (20 runs) or full_matrix (default: forty_mixed)
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
    lexical) echo "lex" ;;
    dense) echo "dns" ;;
    hybrid) echo "hyb" ;;
    *) echo "ret" ;;
  esac
}

ranking_tag() {
  case "$1" in
    deterministic) echo "det" ;;
    llm_rerank) echo "llm" ;;
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
        PROFILE="$2"
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
  if [[ "${PROFILE}" != "forty_mixed" && "${PROFILE}" != "full_matrix" ]]; then
    die "--profile must be one of: forty_mixed, full_matrix"
  fi

  [[ -f "${ATTACK_CONFIG_PATH}" ]] || die "Missing attack config: ${ATTACK_CONFIG_PATH}"
  [[ -f "${LLM_CONFIG_PATH}" ]] || die "Missing llm config: ${LLM_CONFIG_PATH}"
  command -v uv >/dev/null 2>&1 || die "uv is required"
  command -v python3 >/dev/null 2>&1 || die "python3 is required"
}

init_paths() {
  mkdir -p "${RESULTS_ROOT}"
  STATE_DIR="${RESULTS_ROOT}/_state"
  mkdir -p "${STATE_DIR}"

  PROGRESS_JSON="${STATE_DIR}/progress.json"
  RECORDS_JSON="${STATE_DIR}/records.json"
  COMBINED_CSV="${RESULTS_ROOT}/combined_results.csv"
  COMBINED_MD="${RESULTS_ROOT}/combined_results.md"
  FAILURES_CSV="${RESULTS_ROOT}/failures.csv"
  FAILURES_MD="${RESULTS_ROOT}/failures.md"
  COMPLETED_CSV="${RESULTS_ROOT}/completed_runs.csv"
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
    local saved_profile
    saved_profile="$(python3 - "${PROGRESS_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
profile = payload.get("profile", "")
print(str(profile))
PY
)"
    if [[ -n "${saved_profile}" && "${saved_profile}" != "${PROFILE}" ]]; then
      die "--resume profile mismatch: progress has profile=${saved_profile}, requested profile=${PROFILE}"
    fi
    RUN_ID="$(python3 - "${PROGRESS_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
run_id = payload.get("run_id")
if not isinstance(run_id, str) or run_id.strip() == "":
    raise SystemExit("missing run_id in progress.json")
print(run_id.strip())
PY
)"
    local checkpoint_index
    checkpoint_index="$(python3 - "${PROGRESS_JSON}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
value = payload.get("combo_index", 0)
print(int(value))
PY
)"
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
  RETRIEVAL_MODE="$3" \
  RANKING_MODE="$4" \
  VICTIM_PROVIDER="$5" \
  VICTIM_MODEL="$6" \
  ATTACKER_PROVIDER="$7" \
  ATTACKER_MODEL="$8" \
  POISON_FRACTION="$9" \
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
  } >> "${run_log}"

  "$@" >> "${run_log}" 2>&1
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
    tail -n 80 "${run_log}" || true
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

load_matrix() {
  COMBO_SPECS=()

  if [[ "${PROFILE}" == "full_matrix" ]]; then
    local attack_types target_boost_policies retrieval_modes ranking_modes poison_fractions model_specs
    attack_types=("targeted_promotion" "untargeted_degradation" "prompt_injection")
    target_boost_policies=("disabled" "keyword_burst" "aggressive")
    retrieval_modes=("lexical" "dense" "hybrid")
    ranking_modes=("deterministic" "llm_rerank")
    poison_fractions=("0.2")
    model_specs=(
      "chatgpt|gpt-5.4|gpt54"
      "claude|claude-sonnet-4-6|cls46"
      "gemini|gemini-2.5-pro|ge25p"
      "qwen|qwen-3.5-plus|qw35p"
      "deepseek|deepseek-v4-pro|dsv4p"
    )

    local attack_type target_boost_policy retrieval_mode ranking_mode poison_fraction victim_spec attacker_spec
    local victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag
    for attack_type in "${attack_types[@]}"; do
      for target_boost_policy in "${target_boost_policies[@]}"; do
        for retrieval_mode in "${retrieval_modes[@]}"; do
          for ranking_mode in "${ranking_modes[@]}"; do
            for poison_fraction in "${poison_fractions[@]}"; do
              for victim_spec in "${model_specs[@]}"; do
                IFS='|' read -r victim_provider victim_model victim_tag <<< "${victim_spec}"
                for attacker_spec in "${model_specs[@]}"; do
                  IFS='|' read -r attacker_provider attacker_model attacker_tag <<< "${attacker_spec}"
                  COMBO_SPECS+=(
                    "${attack_type}|${target_boost_policy}|${retrieval_mode}|${ranking_mode}|${victim_provider}|${victim_model}|${victim_tag}|${attacker_provider}|${attacker_model}|${attacker_tag}|${poison_fraction}|full"
                  )
                done
              done
            done
          done
        done
      done
    done
  else
    local attack_types
    attack_types=("targeted_promotion" "untargeted_degradation")

    local cross_pairs pair_spec
    cross_pairs=(
      "chatgpt|gpt-5.4|gpt54|claude|claude-sonnet-4-6|cls46"
      "claude|claude-sonnet-4-6|cls46|gemini|gemini-2.5-pro|ge25p"
      "gemini|gemini-2.5-pro|ge25p|qwen|qwen-3.5-plus|qw35p"
      "qwen|qwen-3.5-plus|qw35p|deepseek|deepseek-v4-pro|dsv4p"
      "deepseek|deepseek-v4-pro|dsv4p|chatgpt|gpt-5.4|gpt54"
      "chatgpt|gpt-5.4|gpt54|gemini|gemini-2.5-pro|ge25p"
      "gemini|gemini-2.5-pro|ge25p|deepseek|deepseek-v4-pro|dsv4p"
      "deepseek|deepseek-v4-pro|dsv4p|claude|claude-sonnet-4-6|cls46"
      "claude|claude-sonnet-4-6|cls46|qwen|qwen-3.5-plus|qw35p"
      "qwen|qwen-3.5-plus|qw35p|chatgpt|gpt-5.4|gpt54"
    )

    local attack_type victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag
    for pair_spec in "${cross_pairs[@]}"; do
      IFS='|' read -r victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag <<< "${pair_spec}"
      for attack_type in "${attack_types[@]}"; do
        COMBO_SPECS+=(
          "${attack_type}|keyword_burst|hybrid|llm_rerank|${victim_provider}|${victim_model}|${victim_tag}|${attacker_provider}|${attacker_model}|${attacker_tag}|0.2|cross20"
        )
      done
    done
  fi

  TOTAL_COMBOS="${#COMBO_SPECS[@]}"
}

run_combo() {
  local combo_index="$1"
  local attack_type="$2"
  local target_boost_policy="$3"
  local retrieval_mode="$4"
  local ranking_mode="$5"
  local victim_provider="$6"
  local victim_model="$7"
  local victim_tag="$8"
  local attacker_provider="$9"
  local attacker_model="${10}"
  local attacker_tag="${11}"
  local poison_fraction="${12}"
  local pair_type="${13}"

  local a_tag b_tag r_tag k_tag poison_tag combo_key combo_hash label run_dir run_log
  a_tag="$(attack_tag "${attack_type}")"
  b_tag="$(boost_tag "${target_boost_policy}")"
  r_tag="$(retrieval_tag "${retrieval_mode}")"
  k_tag="$(ranking_tag "${ranking_mode}")"
  poison_tag="${poison_fraction//./p}"
  combo_key="${RUN_ID}|${combo_index}|${attack_type}|${target_boost_policy}|${retrieval_mode}|${ranking_mode}|${victim_provider}|${victim_model}|${attacker_provider}|${attacker_model}|${poison_fraction}|${pair_type}"
  combo_hash="$(short_hash "${combo_key}")"
  label="full_${RUN_ID}_$(printf '%05d' "${combo_index}")_${a_tag}_${b_tag}_${r_tag}_${k_tag}_v${victim_tag}_a${attacker_tag}_p${poison_tag}_${pair_type}_${combo_hash}"
  run_dir="${RESULTS_ROOT}/${label}"
  mkdir -p "${run_dir}"
  run_log="${run_dir}/run.log"

  {
    echo "[$(timestamp_utc)] run_id=${RUN_ID}"
    echo "[$(timestamp_utc)] combo_index=${combo_index}/${TOTAL_COMBOS}"
    echo "[$(timestamp_utc)] label=${label}"
    echo "[$(timestamp_utc)] attack_type=${attack_type} target_boost_policy=${target_boost_policy} poison_fraction=${poison_fraction}"
    echo "[$(timestamp_utc)] retrieval_mode=${retrieval_mode} ranking_mode=${ranking_mode}"
    echo "[$(timestamp_utc)] pair_type=${pair_type} victim=${victim_provider}:${victim_model} attacker=${attacker_provider}:${attacker_model}"
  } >> "${run_log}"

  if ! write_combo_configs \
      "${attack_type}" \
      "${target_boost_policy}" \
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
      "${run_dir}"
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
    if [[ "${ranking_mode}" == "llm_rerank" ]]; then
      eval_cmd+=(--require-rerank-success)
    fi
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
      "${run_dir}"
    write_progress "failed" "${combo_index}" "${label}" "${failed_step}" "${error_message}"
    return 1
  fi

  upsert_record \
    "${combo_index}" "${label}" "success" "" "" \
    "${attack_type}" "${target_boost_policy}" "${retrieval_mode}" "${ranking_mode}" \
    "${victim_provider}" "${victim_model}" "${attacker_provider}" "${attacker_model}" "${pair_type}" "${poison_fraction}" \
    "${run_dir}"
  COMPLETED_INDEX["${combo_index}"]=1
  write_progress "running" "${combo_index}" "${label}" "completed" "combo completed"
  return 0
}

main() {
  parse_args "$@"
  validate_args
  init_paths
  load_matrix
  load_or_initialize_session
  load_completed_index_lookup
  backup_configs
  trap cleanup EXIT INT TERM

  log "repo_root=${REPO_ROOT}"
  log "es_url=${ES_URL}"
  log "results_root=${RESULTS_ROOT}"
  log "profile=${PROFILE}"
  log "run_id=${RUN_ID}"
  log "k=${K} repeat_count=${REPEAT_COUNT} seed=${SEED}"
  log "total_combos=${TOTAL_COMBOS}"

  if [[ "${DRY_RUN}" == "true" ]]; then
    local planned
    if [[ -n "${MAX_RUNS}" ]]; then
      planned="${MAX_RUNS}"
    else
      planned=$(( TOTAL_COMBOS - START_INDEX ))
    fi
    log "dry_run=true start_index=${START_INDEX} planned_runs=${planned}"
    write_progress "dry_run" "${START_INDEX}" "" "" "dry run only"
    exit 0
  fi

  local processed_this_invocation=0
  local combo_index=0
  local attack_type target_boost_policy retrieval_mode ranking_mode
  local victim_provider victim_model victim_tag attacker_provider attacker_model attacker_tag
  local poison_fraction pair_type combo_spec
  for ((combo_index=0; combo_index<TOTAL_COMBOS; combo_index++)); do
    combo_spec="${COMBO_SPECS[$combo_index]}"
    IFS='|' read -r \
      attack_type \
      target_boost_policy \
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
