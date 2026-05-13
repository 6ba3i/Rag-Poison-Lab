#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

STATE_DIR="data/results/full/_state"
CACHE_PATH="${STATE_DIR}/best_attack_params.json"
RUNNER="./tools/run_full_matrix.sh"

usage() {
  cat <<'USAGE'
Usage:
  ./tools/run_full_matrix_reuse_tuned.sh [run_full_matrix options]

Behavior:
  - Defaults to fresh restart (resets progress/aggregates/log state first).
  - Reuses existing tuning cache when valid.
  - If tuning cache is missing/invalid, allows normal run_full_matrix retuning.
  - Pass --resume explicitly to continue from checkpoint.

Examples:
  ./tools/run_full_matrix_reuse_tuned.sh
  ./tools/run_full_matrix_reuse_tuned.sh --dry-run
  ./tools/run_full_matrix_reuse_tuned.sh --resume
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

arg_has_resume() {
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "--resume" ]]; then
      return 0
    fi
  done
  return 1
}

validate_tuning_cache() {
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

print("ok")
PY
}

if [[ ! -x "${RUNNER}" ]]; then
  echo "ERROR: runner missing or not executable: ${RUNNER}" >&2
  exit 1
fi

if arg_has_resume "$@"; then
  log "mode=resume progress_reset=false"
else
  log "mode=fresh progress_reset=true"
  mkdir -p "${STATE_DIR}/logs"
  rm -f \
    "${STATE_DIR}/progress.json" \
    "${STATE_DIR}/records.json" \
    "${STATE_DIR}/completed_runs.csv" \
    "${STATE_DIR}/failures.csv" \
    "${STATE_DIR}/failures.md" \
    "data/results/full/combined_results.csv" \
    "data/results/full/combined_results.md" \
    "data/results/full/completed_runs.csv" \
    "data/results/full/failures.csv" \
    "data/results/full/failures.md"
  find "${STATE_DIR}/logs" -maxdepth 1 -type f -name '*.log' -delete || true
fi

if validate_output="$(validate_tuning_cache "${CACHE_PATH}" 2>&1)"; then
  log "tuning_cache_status=valid cache=${CACHE_PATH}"
  log "action=reuse_cached_tuning"
else
  log "tuning_cache_status=missing_or_invalid cache=${CACHE_PATH} details=${validate_output//$'\n'/ ; }"
  log "action=allow_retune_via_run_full_matrix"
fi

# Enforce non-retune unless main runner decides cache is missing/invalid.
export FORCE_RETUNE=false

log "exec=${RUNNER} $*"
exec "${RUNNER}" "$@"
