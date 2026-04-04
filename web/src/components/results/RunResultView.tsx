import { useMemo, useState } from "react";

import type { RunDetailResponse } from "../../api/types";
import { formatMetric, formatNumber, formatTimestamp } from "../../lib/format";
import {
  buildHeroInfo,
  getAttackConfigInfo,
  getTargetRetrievalInfo,
  listMetricRows,
  metricVisibleInRun,
  summarizeTargetRetrieval,
  toRawJsonRecord,
} from "../../lib/runPresentation";
import { JsonResultDrawer } from "./JsonResultDrawer";
import { MetricComparisonChart } from "./MetricComparisonChart";

interface RawSection {
  title: string;
  payload: unknown;
}

interface RunResultViewProps {
  detail: RunDetailResponse;
  rawSections?: RawSection[];
}

function formatDelta(value: number | null): string {
  if (value === null) {
    return "-";
  }
  if (value > 0) {
    return `▲ ${value.toFixed(3)}`;
  }
  if (value < 0) {
    return `▼ ${Math.abs(value).toFixed(3)}`;
  }
  return value.toFixed(3);
}

function deltaToneClass(value: number | null): "tone-warning" | "tone-attack" | "tone-tertiary" {
  if (value === null || value === 0) {
    return "tone-tertiary";
  }
  return value > 0 ? "tone-warning" : "tone-attack";
}

function outcomeBadgeClass(label: string): string {
  if (label === "Attack succeeded") {
    return "badge attack mono";
  }
  if (label === "Target influence increased") {
    return "badge warning mono";
  }
  return "badge neutral mono";
}

function yesNo(value: boolean | null): string {
  if (value === null) {
    return "-";
  }
  return value ? "Yes" : "No";
}

function compactJson(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value);
}

export function RunResultView({ detail, rawSections = [] }: RunResultViewProps): JSX.Element {
  const [drawerOpen, setDrawerOpen] = useState(false);

  const hero = useMemo(() => buildHeroInfo(detail), [detail]);
  const metricRows = useMemo(() => listMetricRows(detail).filter(metricVisibleInRun), [detail]);
  const target = useMemo(() => getTargetRetrievalInfo(detail), [detail]);
  const targetSummary = useMemo(() => summarizeTargetRetrieval(target, detail.summary.mode ?? "-"), [detail.summary.mode, target]);
  const attackConfig = useMemo(() => getAttackConfigInfo(detail), [detail]);

  const combinedRawSections = useMemo<RawSection[]>(() => {
    const sections: RawSection[] = [{ title: "Run detail", payload: toRawJsonRecord(detail) }];
    return sections.concat(rawSections);
  }, [detail, rawSections]);

  const metadata = (detail.metadata ?? {}) as Record<string, unknown>;
  const runtimeSnapshots = (metadata.runtime_snapshot_paths ?? {}) as Record<string, unknown>;
  const indexProvenance = (metadata.index_provenance ?? {}) as Record<string, unknown>;

  return (
    <div className="stack result-view">
      <article className="surface">
        <div className="status-row" style={{ alignItems: "flex-start" }}>
          <div>
            <h3 className="section-title">Run summary</h3>
            <p className="section-caption">Layer 1: immediate outcome and interpretation.</p>
          </div>
          <button type="button" className="btn" onClick={() => setDrawerOpen(true)}>
            See raw JSON result
          </button>
        </div>

        <div className="hero-badges" style={{ marginTop: 12 }}>
          <span className="run-label-chip">{hero.runLabel}</span>
          <span className="badge neutral mono">Mode: {hero.mode}</span>
          <span className="badge attack mono">Attack: {hero.attackType}</span>
          <span className="badge neutral mono">Target: {formatNumber(hero.targetMovieId)}</span>
          {hero.selectedUsers.length > 0 ? <span className="badge neutral mono">Users: {hero.selectedUsers.join(", ")}</span> : null}
          <span className={outcomeBadgeClass(hero.outcome.label)}>{hero.outcome.label}</span>
        </div>

        <p className="run-interpretation">{hero.interpretation}</p>
      </article>

      <article className="surface">
        <h3 className="section-title">Main metrics</h3>
        <p className="section-caption">Layer 2: baseline vs attacked evidence.</p>

        <div className="metric-grid metrics-kpi" style={{ marginTop: 12 }}>
          {metricRows.map((row) => {
            return (
              <article key={row.key} className="metric-card kpi-card">
                <p className="metric-label">{row.label}</p>
                <div className="metric-rows">
                  <div className="metric-line baseline">
                    <span className="metric-line-label">Baseline</span>
                    <strong className="metric-line-value">{formatMetric(row.baseline)}</strong>
                  </div>
                  <div className="metric-line attacked">
                    <span className="metric-line-label">Attacked</span>
                    <strong className="metric-line-value">{formatMetric(row.attacked)}</strong>
                  </div>
                  <div className={["metric-line", "delta", deltaToneClass(row.delta)].join(" ")}>
                    <span className="metric-line-label">Delta</span>
                    <strong className="metric-line-value">{formatDelta(row.delta)}</strong>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </article>

      <article className="surface">
        <h3 className="section-title">Baseline vs attacked</h3>
        <p className="section-caption">{detail.summary.mode === "single" ? "Single-user dumbbell comparison." : "Grouped aggregate comparison."}</p>
        <div style={{ marginTop: 12 }}>
          <MetricComparisonChart mode={detail.summary.mode ?? "-"} rows={metricRows} />
        </div>
      </article>

      <div className="result-evidence-grid">
        <article className="surface">
          <h3 className="section-title">Target retrieval</h3>
          <p className="section-caption">{targetSummary}</p>

          <div className="kv-grid" style={{ marginTop: 12 }}>
            <div className="kv-row">
              <span>Target movie</span>
              <strong>{formatNumber(target.targetMovieId)}</strong>
            </div>
            <div className="kv-row">
              <span>Baseline present</span>
              <strong>{yesNo(target.baselinePresent)}</strong>
            </div>
            <div className="kv-row">
              <span>Attacked present</span>
              <strong>{yesNo(target.attackedPresent)}</strong>
            </div>
            <div className="kv-row">
              <span>Attacked rank</span>
              <strong>{formatNumber(target.attackedRank)}</strong>
            </div>
            <div className="kv-row">
              <span>Rank changed</span>
              <strong>{yesNo(target.rankChanged)}</strong>
            </div>
            {detail.summary.mode !== "single" ? (
              <>
                <div className="kv-row">
                  <span>Baseline users</span>
                  <strong>{formatNumber(target.baselineUsers)}</strong>
                </div>
                <div className="kv-row">
                  <span>Attacked users</span>
                  <strong>{formatNumber(target.attackedUsers)}</strong>
                </div>
                <div className="kv-row">
                  <span>Total users</span>
                  <strong>{formatNumber(target.users)}</strong>
                </div>
              </>
            ) : null}
          </div>
        </article>

        <article className="surface">
          <h3 className="section-title">Attack config summary</h3>
          <p className="section-caption">Key run configuration inputs and poison counts.</p>

          <div className="kv-grid" style={{ marginTop: 12 }}>
            <div className="kv-row">
              <span>Attack type</span>
              <strong>{attackConfig.attackType}</strong>
            </div>
            <div className="kv-row">
              <span>Poison fraction</span>
              <strong>{attackConfig.poisonFraction === null ? "-" : attackConfig.poisonFraction.toFixed(2)}</strong>
            </div>
            <div className="kv-row">
              <span>Target movie id</span>
              <strong>{formatNumber(attackConfig.targetMovieId)}</strong>
            </div>
            <div className="kv-row">
              <span>Boost policy</span>
              <strong>{attackConfig.boostPolicy}</strong>
            </div>
            <div className="kv-row">
              <span>Boost strength</span>
              <strong>{formatNumber(attackConfig.boostStrength)}</strong>
            </div>
            <div className="kv-row">
              <span>Target fields</span>
              <strong>{attackConfig.targetFields.length > 0 ? attackConfig.targetFields.join(", ") : "-"}</strong>
            </div>
            <div className="kv-row">
              <span>Expected poisoned docs</span>
              <strong>{formatNumber(attackConfig.expectedPoisonedDocs)}</strong>
            </div>
            <div className="kv-row">
              <span>Actual poisoned docs</span>
              <strong>{formatNumber(attackConfig.actualPoisonedDocs)}</strong>
            </div>
          </div>
        </article>
      </div>

      <article className="surface">
        <h3 className="section-title">Warnings and validations</h3>
        <p className="section-caption">Run diagnostics from validation and evaluation steps.</p>

        {detail.warnings.length > 0 ? (
          <ul className="warnings-list" style={{ marginTop: 12 }}>
            {detail.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : (
          <div className="empty-state" style={{ marginTop: 12 }}>
            No warnings reported.
          </div>
        )}
      </article>

      <article className="surface">
        <details className="technical-details" open={false}>
          <summary>Technical details</summary>
          <div className="stack" style={{ marginTop: 12 }}>
            <div className="surface-elevated kv-grid">
              <div className="kv-row">
                <span>Generated</span>
                <strong>{formatTimestamp(detail.summary.generated_at_utc)}</strong>
              </div>
              <div className="kv-row">
                <span>Config hash</span>
                <strong>{compactJson(metadata.attack_config_sha256)}</strong>
              </div>
              <div className="kv-row">
                <span>Config path</span>
                <strong>{compactJson(metadata.attack_config_path)}</strong>
              </div>
              <div className="kv-row">
                <span>Manifest path</span>
                <strong>{detail.artifacts.manifest_path ?? "-"}</strong>
              </div>
              <div className="kv-row">
                <span>Metrics path</span>
                <strong>{detail.artifacts.metrics_path ?? "-"}</strong>
              </div>
              <div className="kv-row">
                <span>Attack trace path</span>
                <strong>{detail.artifacts.attack_trace_path ?? "-"}</strong>
              </div>
              <div className="kv-row">
                <span>LLM runtime snapshot</span>
                <strong>{compactJson(runtimeSnapshots.llm_config_runtime_path ?? detail.artifacts.llm_runtime_path)}</strong>
              </div>
              <div className="kv-row">
                <span>Attack runtime snapshot</span>
                <strong>{compactJson(runtimeSnapshots.attack_config_runtime_path ?? detail.artifacts.attack_runtime_path)}</strong>
              </div>
            </div>

            <div className="surface-elevated">
              <p className="text-meta" style={{ margin: 0 }}>
                Index provenance
              </p>
              <pre className="code-block" style={{ marginTop: 8 }}>
                {JSON.stringify(indexProvenance, null, 2)}
              </pre>
            </div>
          </div>
        </details>
      </article>

      <JsonResultDrawer
        open={drawerOpen}
        title={`Raw JSON - ${detail.summary.label}`}
        sections={combinedRawSections}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
