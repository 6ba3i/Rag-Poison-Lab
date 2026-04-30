#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

PROFILE="${PROFILE:-gpt_fixed_attacker_victims4_attack3}"
MAX_RUNS="${MAX_RUNS:-12}"
RESULTS_ROOT="${RESULTS_ROOT:-data/results/full}"
MAX_RETRIES="${MAX_RETRIES:-5}"
RETRY_SLEEP_SECONDS="${RETRY_SLEEP_SECONDS:-0}"
ES_URL="${ELASTICSEARCH_URL:-}"

log() {
  printf '[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

die() {
  log "ERROR: $*"
  exit 1
}

validate() {
  [[ "${MAX_RUNS}" =~ ^[0-9]+$ ]] || die "MAX_RUNS must be a non-negative integer"
  [[ "${MAX_RETRIES}" =~ ^[0-9]+$ ]] || die "MAX_RETRIES must be a non-negative integer"
  [[ "${RETRY_SLEEP_SECONDS}" =~ ^[0-9]+$ ]] || die "RETRY_SLEEP_SECONDS must be a non-negative integer"
}

build_cmd() {
  local include_resume="$1"
  shift
  local -a cmd=(
    tools/run_full_matrix.sh
    --profile "${PROFILE}"
    --max-runs "${MAX_RUNS}"
    --results-root "${RESULTS_ROOT}"
    --fail-fast
  )

  if [[ -n "${ES_URL}" ]]; then
    cmd+=(--es-url "${ES_URL}")
  fi
  if [[ "${include_resume}" == "true" ]]; then
    cmd+=(--resume)
  fi

  cmd+=("$@")
  printf '%s\0' "${cmd[@]}"
}

main() {
  validate
  local -a passthrough=("$@")

  log "profile=${PROFILE} max_runs=${MAX_RUNS} results_root=${RESULTS_ROOT} max_retries=${MAX_RETRIES}"

  local -a first_cmd=()
  mapfile -d '' -t first_cmd < <(build_cmd "false" "${passthrough[@]}")
  if "${first_cmd[@]}"; then
    log "completed on initial attempt"
    return 0
  fi

  local attempt=1
  while (( attempt <= MAX_RETRIES )); do
    log "retry_attempt=${attempt}/${MAX_RETRIES} (resume from failed combo)"

    if (( RETRY_SLEEP_SECONDS > 0 )); then
      sleep "${RETRY_SLEEP_SECONDS}"
    fi

    local -a retry_cmd=()
    mapfile -d '' -t retry_cmd < <(build_cmd "true" "${passthrough[@]}")
    if "${retry_cmd[@]}"; then
      log "completed on retry_attempt=${attempt}"
      return 0
    fi
    attempt=$((attempt + 1))
  done

  die "failed after ${MAX_RETRIES} retries"
}

main "$@"
