export type MatrixMetricKey = "hr" | "ndcg" | "mrr" | "asr";

export interface MatrixManifest {
  source_path: string;
  source_markdown_path: string;
  copied_at_utc: string;
  row_count: number;
  sha256: string;
  source_updated_at_min: string | null;
  source_updated_at_max: string | null;
  notes: string;
}

export interface MatrixRow {
  raw: Record<string, string>;
  comboIndex: number | null;
  runId: string;
  label: string;
  status: string;
  attackType: string;
  targetBoostPolicy: string;
  retrievalMode: string;
  rankingMode: string;
  victimProvider: string;
  victimModel: string;
  attackerProvider: string;
  attackerModel: string;
  pairType: string;
  poisonFraction: number | null;
  requestedPoisonFraction: number | null;
  targetMovieId: number | null;
  k: number | null;
  evaluatedUsers: number | null;
  requestedUsers: number | null;
  skippedUsers: number | null;
  baseline: Record<MatrixMetricKey, number | null>;
  attacked: Record<MatrixMetricKey, number | null>;
  delta: Record<MatrixMetricKey, number | null>;
  targetRetrievalRankBaseline: number | null;
  targetRetrievalRankAttacked: number | null;
  runDir: string;
  runLogPath: string;
  metricsPath: string;
  summaryPath: string;
  deltaCsvPath: string;
  updatedAtUtc: string;
}

export interface FilterState {
  attackType: string;
  rankingMode: string;
  retrievalMode: string;
  attackerProvider: string;
  status: string;
  metric: MatrixMetricKey;
}

export interface MetricPairSummary {
  key: MatrixMetricKey;
  label: string;
  baseline: number | null;
  attacked: number | null;
  delta: number | null;
  count: number;
  excluded: number;
}

export interface ScenarioSummary {
  attackType: string;
  rows: MatrixRow[];
  keyMetric: MatrixMetricKey;
  keyValue: number | null;
  keyDelta: number | null;
  badge: string;
  badgeTone: "attack" | "warning" | "baseline" | "neutral";
  sparkValues: number[];
}

export interface RankerSummary {
  rankingMode: string;
  rows: MatrixRow[];
  averageEffect: number | null;
  strongestEffect: number | null;
  representativeMetric: MatrixMetricKey;
}

export interface InsightCard {
  title: string;
  evidence: string;
  tone: "attack" | "warning" | "baseline" | "neutral";
}

export const METRIC_LABELS: Record<MatrixMetricKey, string> = {
  hr: "HR",
  ndcg: "NDCG",
  mrr: "MRR",
  asr: "ASR",
};

export const METRIC_OPTIONS: MatrixMetricKey[] = ["asr", "ndcg", "mrr", "hr"];

export const REQUIRED_MATRIX_COLUMNS = [
  "combo_index",
  "run_id",
  "label",
  "status",
  "attack_type",
  "retrieval_mode",
  "ranking_mode",
  "attacker_provider",
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
] as const;

export function validateMatrixColumns(records: Record<string, string>[]): void {
  const first = records[0];
  if (!first) {
    throw new Error("Matrix CSV contains no data rows.");
  }
  const missing = REQUIRED_MATRIX_COLUMNS.filter((column) => !(column in first));
  if (missing.length > 0) {
    throw new Error(`Matrix CSV is missing required columns: ${missing.join(", ")}.`);
  }
}

export const DEFAULT_FILTERS: FilterState = {
  attackType: "all",
  rankingMode: "all",
  retrievalMode: "all",
  attackerProvider: "all",
  status: "all",
  metric: "asr",
};

const ATTACK_PREFIX: Record<string, string> = {
  targeted_promotion: "TPROM",
  prompt_injection: "PINJ",
  untargeted_degradation: "UDEG",
  metadata_poisoning: "META",
};

function providerCode(value: string): string {
  const cleaned = value.replace(/[^a-z0-9]/gi, "").toUpperCase();
  if (!cleaned) {
    return "UNK";
  }
  return cleaned.slice(0, 4);
}

export function displayRunId(row: MatrixRow): string {
  const index = row.comboIndex === null ? "XX" : String(row.comboIndex).padStart(2, "0");
  const attack = ATTACK_PREFIX[row.attackType] ?? providerCode(row.attackType).slice(0, 5);
  const ranker = row.rankingMode === "llm_rerank" ? "LLM" : "DET";
  const retrieval = providerCode(row.retrievalMode).slice(0, 3);
  const attacker = providerCode(row.attackerProvider);
  return `${index}-${attack}-${ranker}-${retrieval}-${attacker}`;
}

export function parseNullableNumber(value: string | undefined): number | null {
  if (value === undefined) {
    return null;
  }
  const trimmed = value.trim();
  if (trimmed === "" || trimmed.toLowerCase() === "none" || trimmed.toLowerCase() === "nan") {
    return null;
  }
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatScenarioLabel(value: string): string {
  if (!value) {
    return "Unknown";
  }
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function scenarioColor(value: string): string {
  if (value === "targeted_promotion") {
    return "var(--matrix-targeted)";
  }
  if (value === "prompt_injection" || value === "metadata_poisoning") {
    return "var(--matrix-injection)";
  }
  if (value === "untargeted_degradation") {
    return "var(--matrix-degradation)";
  }
  return "var(--matrix-baseline)";
}

export function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") {
        i += 1;
      }
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }

  const [headers = [], ...body] = rows.filter((cells) => cells.some((value) => value.trim() !== ""));
  return body.map((cells) => {
    const record: Record<string, string> = {};
    headers.forEach((header, index) => {
      record[header] = cells[index] ?? "";
    });
    return record;
  });
}

export function normalizeMatrixRows(records: Record<string, string>[]): MatrixRow[] {
  return records.map((raw) => ({
    raw,
    comboIndex: parseNullableNumber(raw.combo_index),
    runId: raw.run_id ?? "",
    label: raw.label ?? "",
    status: raw.status ?? "",
    attackType: raw.attack_type ?? "",
    targetBoostPolicy: raw.target_boost_policy ?? "",
    retrievalMode: raw.retrieval_mode ?? "",
    rankingMode: raw.ranking_mode ?? "",
    victimProvider: raw.victim_provider ?? "",
    victimModel: raw.victim_model ?? "",
    attackerProvider: raw.attacker_provider ?? "",
    attackerModel: raw.attacker_model ?? "",
    pairType: raw.pair_type ?? "",
    poisonFraction: parseNullableNumber(raw.poison_fraction),
    requestedPoisonFraction: parseNullableNumber(raw.requested_poison_fraction),
    targetMovieId: parseNullableNumber(raw.target_movie_id),
    k: parseNullableNumber(raw.k),
    evaluatedUsers: parseNullableNumber(raw.evaluated_users),
    requestedUsers: parseNullableNumber(raw.requested_users),
    skippedUsers: parseNullableNumber(raw.skipped_users),
    baseline: {
      hr: parseNullableNumber(raw.baseline_hr),
      ndcg: parseNullableNumber(raw.baseline_ndcg),
      mrr: parseNullableNumber(raw.baseline_mrr),
      asr: parseNullableNumber(raw.baseline_asr),
    },
    attacked: {
      hr: parseNullableNumber(raw.attacked_hr),
      ndcg: parseNullableNumber(raw.attacked_ndcg),
      mrr: parseNullableNumber(raw.attacked_mrr),
      asr: parseNullableNumber(raw.attacked_asr),
    },
    delta: {
      hr: parseNullableNumber(raw.delta_hr),
      ndcg: parseNullableNumber(raw.delta_ndcg),
      mrr: parseNullableNumber(raw.delta_mrr),
      asr: parseNullableNumber(raw.delta_asr),
    },
    targetRetrievalRankBaseline: parseNullableNumber(raw.target_retrieval_rank_baseline),
    targetRetrievalRankAttacked: parseNullableNumber(raw.target_retrieval_rank_attacked),
    runDir: raw.run_dir ?? "",
    runLogPath: raw.run_log_path ?? "",
    metricsPath: raw.metrics_path ?? "",
    summaryPath: raw.summary_path ?? "",
    deltaCsvPath: raw.delta_csv_path ?? "",
    updatedAtUtc: raw.updated_at_utc ?? "",
  }));
}

export function uniqueValues(rows: MatrixRow[], getter: (row: MatrixRow) => string): string[] {
  return Array.from(new Set(rows.map(getter).filter(Boolean))).sort();
}

export function applyFilters(rows: MatrixRow[], filters: FilterState): MatrixRow[] {
  return rows.filter((row) => {
    if (filters.attackType !== "all" && row.attackType !== filters.attackType) return false;
    if (filters.rankingMode !== "all" && row.rankingMode !== filters.rankingMode) return false;
    if (filters.retrievalMode !== "all" && row.retrievalMode !== filters.retrievalMode) return false;
    if (filters.attackerProvider !== "all" && row.attackerProvider !== filters.attackerProvider) return false;
    if (filters.status !== "all" && row.status !== filters.status) return false;
    return true;
  });
}

export function average(values: Array<number | null>): number | null {
  const valid = values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (valid.length === 0) {
    return null;
  }
  return valid.reduce((sum, value) => sum + value, 0) / valid.length;
}

export function strongestBy<T>(items: T[], score: (item: T) => number | null): T | null {
  let best: T | null = null;
  let bestScore = -Infinity;
  items.forEach((item) => {
    const value = score(item);
    if (value !== null && value > bestScore) {
      best = item;
      bestScore = value;
    }
  });
  return best;
}

export function metricEffect(row: MatrixRow, metric: MatrixMetricKey): number | null {
  const value = row.delta[metric];
  if (value === null) {
    return null;
  }
  return metric === "asr" ? value : Math.abs(value);
}

export function overallAttackEffect(row: MatrixRow): number | null {
  const metricEffects = METRIC_OPTIONS.map((metric) => metricEffect(row, metric)).filter((value): value is number => value !== null);
  return metricEffects.length ? Math.max(...metricEffects) : null;
}

export function metricPairs(rows: MatrixRow[]): MetricPairSummary[] {
  return METRIC_OPTIONS.map((key) => {
    const usable = rows.filter((row) => row.baseline[key] !== null && row.attacked[key] !== null);
    return {
      key,
      label: METRIC_LABELS[key],
      baseline: average(usable.map((row) => row.baseline[key])),
      attacked: average(usable.map((row) => row.attacked[key])),
      delta: average(usable.map((row) => row.delta[key])),
      count: usable.length,
      excluded: rows.length - usable.length,
    };
  });
}

function badgeForScenario(metric: MatrixMetricKey, value: number | null, rows: MatrixRow[]): ScenarioSummary["badge"] {
  if (value === null) {
    return "insufficient data";
  }
  const maxEffect = Math.max(...rows.map((row) => metricEffect(row, metric) ?? 0));
  const magnitude = metric === "asr" ? value : Math.abs(value);
  if (maxEffect > 0 && magnitude >= maxEffect * 0.95) {
    return metric === "asr" ? "highest impact" : "strongest degradation";
  }
  if (magnitude < 0.002) {
    return "stable";
  }
  return "measurable effect";
}

export function scenarioSummaries(rows: MatrixRow[]): ScenarioSummary[] {
  const groups = uniqueValues(rows, (row) => row.attackType).map((attackType) => rows.filter((row) => row.attackType === attackType));
  return groups.map((group) => {
    const hasAsr = group.some((row) => row.delta.asr !== null || row.attacked.asr !== null);
    const keyMetric: MatrixMetricKey = hasAsr ? "asr" : "ndcg";
    const keyValue = hasAsr ? average(group.map((row) => row.attacked.asr)) : average(group.map((row) => row.attacked.ndcg));
    const keyDelta = average(group.map((row) => row.delta[keyMetric]));
    const badge = badgeForScenario(keyMetric, keyDelta, rows);
    return {
      attackType: group[0]?.attackType ?? "unknown",
      rows: group,
      keyMetric,
      keyValue,
      keyDelta,
      badge,
      badgeTone: badge.includes("highest") ? "attack" : badge.includes("degradation") ? "warning" : "baseline",
      sparkValues: group.map((row) => metricEffect(row, keyMetric)).filter((value): value is number => value !== null),
    };
  });
}

export function rankerSummaries(rows: MatrixRow[], metric: MatrixMetricKey): RankerSummary[] {
  return uniqueValues(rows, (row) => row.rankingMode).map((rankingMode) => {
    const group = rows.filter((row) => row.rankingMode === rankingMode);
    const effects = group.map((row) => metricEffect(row, metric));
    return {
      rankingMode,
      rows: group,
      averageEffect: average(effects),
      strongestEffect: effects.reduce<number | null>((best, value) => {
        if (value === null) return best;
        return best === null || Math.abs(value) > Math.abs(best) ? value : best;
      }, null),
      representativeMetric: metric,
    };
  });
}

export function insightCards(rows: MatrixRow[], metric: MatrixMetricKey): InsightCard[] {
  const scenarios = scenarioSummaries(rows);
  const highestAsr = strongestBy(rows, (row) => row.attacked.asr);
  const largestNdcgDrop = strongestBy(rows, (row) => (row.delta.ndcg === null ? null : Math.abs(row.delta.ndcg)));
  const rankers = rankerSummaries(rows, metric);
  const vulnerableRanker = strongestBy(rankers, (ranker) => ranker.averageEffect);
  const strongestRun = strongestBy(rows, (row) => metricEffect(row, metric));
  const stableMetric = strongestBy(METRIC_OPTIONS, (key) => {
    const avg = average(rows.map((row) => row.delta[key]));
    return avg === null ? null : -Math.abs(avg);
  });

  return [
    highestAsr
      ? {
          title: `${formatScenarioLabel(highestAsr.attackType)} reaches the highest ASR`,
          evidence: `${displayRunId(highestAsr)} reports attacked ASR ${formatPercent(highestAsr.attacked.asr)} with delta ${formatSigned(highestAsr.delta.asr)}.`,
          tone: "attack" as const,
        }
      : {
          title: "ASR insight unavailable",
          evidence: "No non-null ASR values are present after filtering.",
          tone: "neutral" as const,
        },
    largestNdcgDrop
      ? {
          title: "Largest quality degradation is visible in NDCG",
          evidence: `${displayRunId(largestNdcgDrop)} has delta NDCG ${formatSigned(largestNdcgDrop.delta.ndcg)}.`,
          tone: "warning" as const,
        }
      : {
          title: "NDCG degradation unavailable",
          evidence: "No non-null NDCG deltas are present after filtering.",
          tone: "neutral" as const,
        },
    vulnerableRanker
      ? {
          title: `${formatScenarioLabel(vulnerableRanker.rankingMode)} shows the larger computed effect`,
          evidence: `Average ${METRIC_LABELS[metric]} effect is ${formatSigned(vulnerableRanker.averageEffect)} across ${vulnerableRanker.rows.length} rows.`,
          tone: "attack" as const,
        }
      : {
          title: "Ranker comparison unavailable",
          evidence: "At least one ranker group is required.",
          tone: "neutral" as const,
        },
    strongestRun
      ? {
          title: "Strongest run-level effect",
          evidence: `${displayRunId(strongestRun)} has ${METRIC_LABELS[metric]} effect ${formatSigned(metricEffect(strongestRun, metric))}.`,
          tone: "baseline" as const,
        }
      : stableMetric
        ? {
            title: `${METRIC_LABELS[stableMetric]} is the most stable metric`,
            evidence: `Average delta is ${formatSigned(average(rows.map((row) => row.delta[stableMetric])))} after filtering ${rows.length} rows.`,
            tone: "baseline" as const,
          }
        : {
            title: "Stability insight unavailable",
            evidence: "No metric deltas are present after filtering.",
            tone: "neutral" as const,
          },
  ].slice(0, scenarios.length ? 4 : 3);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDecimal(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

export function formatSigned(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(4)}`;
}

export function shortHash(value: string): string {
  return value.length > 12 ? `${value.slice(0, 12)}…` : value;
}
