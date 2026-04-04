import type { RunDetailResponse } from "../api/types";

export type MetricKey = "hr" | "ndcg" | "mrr" | "asr";

export interface MetricRow {
  key: MetricKey;
  label: string;
  baseline: number | null;
  attacked: number | null;
  delta: number | null;
}

export interface OutcomeInfo {
  label: string;
  tone: "success" | "warning" | "danger" | "neutral";
}

export interface HeroInfo {
  runLabel: string;
  mode: string;
  attackType: string;
  targetMovieId: number | null;
  selectedUsers: number[];
  interpretation: string;
  outcome: OutcomeInfo;
}

export interface TargetRetrievalInfo {
  applicable: boolean;
  targetMovieId: number | null;
  baselinePresent: boolean | null;
  attackedPresent: boolean | null;
  attackedRank: number | null;
  baselineRank: number | null;
  rankChanged: boolean | null;
  baselineUsers: number | null;
  attackedUsers: number | null;
  users: number | null;
  baselineRate: number | null;
  attackedRate: number | null;
}

export interface AttackConfigInfo {
  attackType: string;
  poisonFraction: number | null;
  targetMovieId: number | null;
  boostPolicy: string;
  boostStrength: number | null;
  targetFields: string[];
  expectedPoisonedDocs: number | null;
  actualPoisonedDocs: number | null;
}

const METRIC_KEYS: MetricKey[] = ["hr", "ndcg", "mrr", "asr"];
const METRIC_LABELS: Record<MetricKey, string> = {
  hr: "HR",
  ndcg: "NDCG",
  mrr: "MRR",
  asr: "ASR",
};

function readNumber(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return value;
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object") {
    return {};
  }
  return value as Record<string, unknown>;
}

function readInt(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return Math.trunc(value);
}

function formatRate(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function listMetricRows(detail: RunDetailResponse): MetricRow[] {
  return METRIC_KEYS.map((key) => ({
    key,
    label: METRIC_LABELS[key],
    baseline: readNumber(detail.summary.baseline[key]),
    attacked: readNumber(detail.summary.attacked[key]),
    delta: readNumber(detail.summary.delta[key]),
  }));
}

function getSingleUserRow(detail: RunDetailResponse): Record<string, unknown> | null {
  if (detail.summary.mode !== "single") {
    return null;
  }
  const [first] = detail.per_user;
  if (!first || typeof first !== "object") {
    return null;
  }
  return first as Record<string, unknown>;
}

export function getSelectedUsers(detail: RunDetailResponse): number[] {
  const users = detail.per_user
    .map((row) => readInt((row as Record<string, unknown>).user_id))
    .filter((value): value is number => value !== null);
  return users;
}

export function getTargetRetrievalInfo(detail: RunDetailResponse): TargetRetrievalInfo {
  const source = asRecord(detail.target_retrieval);
  const singleRow = getSingleUserRow(detail);
  const summaryTargetMovie = detail.summary.target_movie_id;
  const targetMovieId = readInt(source.target_movie_id) ?? summaryTargetMovie ?? null;

  const singleBaselinePresent = singleRow ? Boolean(singleRow.target_in_retrieval_baseline) : null;
  const singleAttackedPresent = singleRow ? Boolean(singleRow.target_in_retrieval_attacked) : null;
  const singleAttackedRank = singleRow ? readInt(singleRow.target_retrieval_rank_attacked) : null;
  const singleBaselineRank = singleRow ? readInt(singleRow.target_retrieval_rank_baseline) : null;

  if (detail.summary.mode === "single") {
    const baselinePresent = singleBaselinePresent;
    const attackedPresent = singleAttackedPresent;
    return {
      applicable: Boolean(source.applicable ?? targetMovieId !== null),
      targetMovieId,
      baselinePresent,
      attackedPresent,
      attackedRank: singleAttackedRank,
      baselineRank: singleBaselineRank,
      rankChanged:
        singleBaselineRank !== null || singleAttackedRank !== null
          ? singleBaselineRank !== singleAttackedRank
          : null,
      baselineUsers: baselinePresent === null ? null : baselinePresent ? 1 : 0,
      attackedUsers: attackedPresent === null ? null : attackedPresent ? 1 : 0,
      users: 1,
      baselineRate: baselinePresent === null ? null : baselinePresent ? 1 : 0,
      attackedRate: attackedPresent === null ? null : attackedPresent ? 1 : 0,
    };
  }

  const baselineUsers = readInt(source.target_in_retrieval_baseline_users);
  const attackedUsers = readInt(source.target_in_retrieval_attacked_users);
  const users = readInt(source.users);
  const baselineRate = readNumber(source.target_in_retrieval_baseline_rate);
  const attackedRate = readNumber(source.target_in_retrieval_attacked_rate);
  const baselineRank = readInt(source.target_retrieval_mean_rank_baseline);
  const attackedRank = readInt(source.target_retrieval_mean_rank_attacked);
  const rankChangedUsers = readInt(source.target_retrieval_rank_changed_users);

  return {
    applicable: Boolean(source.applicable ?? targetMovieId !== null),
    targetMovieId,
    baselinePresent: baselineUsers === null ? null : baselineUsers > 0,
    attackedPresent: attackedUsers === null ? null : attackedUsers > 0,
    attackedRank,
    baselineRank,
    rankChanged: rankChangedUsers === null ? null : rankChangedUsers > 0,
    baselineUsers,
    attackedUsers,
    users,
    baselineRate,
    attackedRate,
  };
}

export function summarizeTargetRetrieval(info: TargetRetrievalInfo, mode: string): string {
  if (!info.applicable) {
    return "Target retrieval is not applicable for this run.";
  }

  if (mode === "single") {
    const baseline = info.baselinePresent === true ? "present" : info.baselinePresent === false ? "absent" : "unknown";
    const attacked = info.attackedPresent === true ? "present" : info.attackedPresent === false ? "absent" : "unknown";
    const attackedRank = info.attackedRank !== null ? ` at rank ${info.attackedRank}` : "";
    const changed = info.rankChanged === true ? "Rank changed under attack." : "Rank unchanged.";
    return `Target is ${baseline} in baseline retrieval and ${attacked}${attackedRank} in attacked retrieval. ${changed}`;
  }

  return `Target retrieval presence moved from ${formatRate(info.baselineRate)} baseline to ${formatRate(info.attackedRate)} attacked across ${info.users ?? 0} users.`;
}

export function getAttackConfigInfo(detail: RunDetailResponse): AttackConfigInfo {
  const metadata = asRecord(detail.metadata);
  const diagnostics = asRecord(metadata.attack_config_diagnostics);
  const indexProvenance = asRecord(metadata.index_provenance);
  const poisoned = asRecord(asRecord(indexProvenance.movies_poisoned).provenance);

  const targetFieldsRaw = diagnostics.target_fields;
  const targetFields = Array.isArray(targetFieldsRaw) ? targetFieldsRaw.map(String) : [];

  return {
    attackType: String(diagnostics.attack_type ?? metadata.attack_type ?? "-"),
    poisonFraction: readNumber(diagnostics.poison_fraction),
    targetMovieId: readInt(diagnostics.target_movie_id) ?? detail.summary.target_movie_id ?? null,
    boostPolicy: String(diagnostics.target_boost_policy ?? "-"),
    boostStrength: readInt(diagnostics.target_boost_strength),
    targetFields,
    expectedPoisonedDocs: readInt(diagnostics.expected_poisoned_docs),
    actualPoisonedDocs: readInt(poisoned.poisoned_docs),
  };
}

export function getOutcomeInfo(detail: RunDetailResponse): OutcomeInfo {
  const asrDelta = readNumber(detail.summary.delta.asr);
  const ndcgDelta = readNumber(detail.summary.delta.ndcg);
  const mrrDelta = readNumber(detail.summary.delta.mrr);
  const target = getTargetRetrievalInfo(detail);

  if (asrDelta !== null && asrDelta > 0.001) {
    return { label: "Attack succeeded", tone: "warning" };
  }
  if (target.applicable && target.attackedRate !== null && target.baselineRate !== null && target.attackedRate > target.baselineRate) {
    return { label: "Target influence increased", tone: "warning" };
  }
  if ((asrDelta !== null && asrDelta < -0.001) || (ndcgDelta !== null && ndcgDelta > 0.001 && mrrDelta !== null && mrrDelta > 0.001)) {
    return { label: "Attack weakened", tone: "success" };
  }
  if (asrDelta === null && ndcgDelta === null && mrrDelta === null) {
    return { label: "Completed", tone: "neutral" };
  }
  return { label: "Limited impact", tone: "neutral" };
}

export function buildInterpretation(detail: RunDetailResponse): string {
  const mode = detail.summary.mode ?? "-";
  const target = getTargetRetrievalInfo(detail);

  if (mode === "single") {
    const attackedRankText = target.attackedRank !== null ? `rank ${target.attackedRank}` : "rank unavailable";
    if (target.baselinePresent === false && target.attackedPresent === true) {
      return `Target absent in baseline retrieval, inserted under attack at ${attackedRankText}.`;
    }
    if (target.baselinePresent === true && target.attackedPresent === true) {
      return `Target remained retrievable and moved to ${attackedRankText} under attack.`;
    }
    if (target.baselinePresent === true && target.attackedPresent === false) {
      return "Target was retrievable in baseline but dropped out under attack.";
    }
    return "Single-user run completed; review metric deltas and retrieval evidence.";
  }

  const ndcgDelta = readNumber(detail.summary.delta.ndcg);
  const mrrDelta = readNumber(detail.summary.delta.mrr);
  return `Batch aggregate: ΔNDCG ${ndcgDelta?.toFixed(3) ?? "-"}, ΔMRR ${mrrDelta?.toFixed(3) ?? "-"}, target retrieval ${formatRate(target.baselineRate)} → ${formatRate(target.attackedRate)}.`;
}

export function buildHeroInfo(detail: RunDetailResponse): HeroInfo {
  const metadata = asRecord(detail.metadata);
  return {
    runLabel: detail.summary.label,
    mode: detail.summary.mode ?? "-",
    attackType: String(metadata.attack_type ?? "-"),
    targetMovieId: detail.summary.target_movie_id,
    selectedUsers: getSelectedUsers(detail),
    interpretation: buildInterpretation(detail),
    outcome: getOutcomeInfo(detail),
  };
}

export function getMetricDeltaTone(metricKey: MetricKey, delta: number | null): "success" | "warning" | "danger" | "neutral" {
  if (delta === null || Math.abs(delta) < 0.0005) {
    return "neutral";
  }

  if (metricKey === "asr") {
    return delta > 0 ? "warning" : "success";
  }

  return delta > 0 ? "success" : "danger";
}

export function metricVisibleInRun(row: MetricRow): boolean {
  return row.baseline !== null || row.attacked !== null || row.delta !== null;
}

export function toRawJsonRecord(detail: RunDetailResponse): Record<string, unknown> {
  return {
    summary: detail.summary,
    warnings: detail.warnings,
    metadata: detail.metadata,
    target_retrieval: detail.target_retrieval,
    per_user: detail.per_user,
    manifest: detail.manifest,
    artifacts: detail.artifacts,
  };
}
