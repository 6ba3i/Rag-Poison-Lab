import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import {
  DEFAULT_FILTERS,
  METRIC_LABELS,
  METRIC_OPTIONS,
  type FilterState,
  type MatrixManifest,
  type MatrixMetricKey,
  type MatrixRow,
  applyFilters,
  metricEffect,
  overallAttackEffect,
  average,
  displayRunId,
  formatDecimal,
  formatPercent,
  formatScenarioLabel,
  formatSigned,
  insightCards,
  metricPairs,
  normalizeMatrixRows,
  parseCsv,
  rankerSummaries,
  scenarioColor,
  scenarioSummaries,
  shortHash,
  strongestBy,
  uniqueValues,
  validateMatrixColumns,
} from "../lib/matrixResults";

interface MatrixPayload {
  rows: MatrixRow[];
  manifest: MatrixManifest;
  markdown: string;
}

interface KpiCard {
  label: string;
  value: string;
  caption: string;
  tone: "baseline" | "attack" | "warning" | "neutral";
}

const DATA_BASE = `${import.meta.env.BASE_URL}matrix-results`.replace(/\/$/, "");

function toneClass(tone: KpiCard["tone"]): string {
  return `matrix-tone-${tone}`;
}

async function loadMatrixPayload(): Promise<MatrixPayload> {
  const [csvResponse, manifestResponse, markdownResponse] = await Promise.all([
    fetch(`${DATA_BASE}/combined_results.csv`),
    fetch(`${DATA_BASE}/manifest.json`),
    fetch(`${DATA_BASE}/combined_results.md`),
  ]);

  if (!csvResponse.ok || !manifestResponse.ok) {
    throw new Error("Matrix snapshot assets are unavailable.");
  }

  const csvText = await csvResponse.text();
  const manifest = (await manifestResponse.json()) as MatrixManifest;
  const markdown = markdownResponse.ok ? await markdownResponse.text() : "";
  const records = parseCsv(csvText);
  validateMatrixColumns(records);
  const rows = normalizeMatrixRows(records);

  if (manifest.row_count !== rows.length) {
    throw new Error(`Matrix manifest row count ${manifest.row_count} does not match parsed CSV row count ${rows.length}.`);
  }

  return { rows, manifest, markdown };
}

function updateFilter<K extends keyof FilterState>(filters: FilterState, key: K, value: FilterState[K]): FilterState {
  return { ...filters, [key]: value };
}

function FilterGroup({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <div className="matrix-filter-group">
      <span className="caps-label">{label}</span>
      <div className="matrix-filter-pills">
        {["all", ...options].map((option) => (
          <button
            key={option}
            type="button"
            className={["matrix-pill", value === option ? "active" : ""].join(" ").trim()}
            onClick={() => onChange(option)}
          >
            {option === "all" ? "All" : formatScenarioLabel(option)}
          </button>
        ))}
      </div>
    </div>
  );
}

function MetricSelector({ value, onChange }: { value: MatrixMetricKey; onChange: (value: MatrixMetricKey) => void }): JSX.Element {
  return (
    <div className="matrix-filter-group">
      <span className="caps-label">Metric</span>
      <div className="matrix-filter-pills">
        {METRIC_OPTIONS.map((metric) => (
          <button
            key={metric}
            type="button"
            className={["matrix-pill", value === metric ? "active" : ""].join(" ").trim()}
            onClick={() => onChange(metric)}
          >
            {METRIC_LABELS[metric]}
          </button>
        ))}
      </div>
    </div>
  );
}

function buildKpis(rows: MatrixRow[], allRows: MatrixRow[], metric: MatrixMetricKey): KpiCard[] {
  const successful = rows.filter((row) => row.status === "success").length;
  const avgAsr = average(rows.map((row) => row.attacked.asr));
  const avgNdcgDelta = average(rows.map((row) => row.delta.ndcg));
  const strongest = strongestBy(rows, (row) => metricEffect(row, metric));
  const blankAsr = allRows.filter((row) => row.delta.asr === null).length;

  return [
    {
      label: "Matrix runs",
      value: String(rows.length),
      caption: `${successful} success rows from ${allRows.length} total`,
      tone: "baseline",
    },
    {
      label: "Average attacked ASR",
      value: formatPercent(avgAsr),
      caption: blankAsr ? `${blankAsr} rows exclude ASR because source cells are blank` : "All filtered rows include ASR",
      tone: "attack",
    },
    {
      label: "Average NDCG delta",
      value: formatSigned(avgNdcgDelta),
      caption: "Computed from delta_ndcg across filtered rows",
      tone: "warning",
    },
    {
      label: "Strongest selected effect",
      value: formatSigned(strongest ? metricEffect(strongest, metric) : null),
      caption: strongest ? displayRunId(strongest) : "No supported metric rows",
      tone: "attack",
    },
  ];
}

function KpiGrid({ cards }: { cards: KpiCard[] }): JSX.Element {
  return (
    <section className="matrix-kpi-grid">
      {cards.map((card, index) => (
        <motion.article
          key={card.label}
          className={["matrix-kpi-card", toneClass(card.tone)].join(" ")}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.32, delay: index * 0.08 }}
        >
          <p className="metric-label">{card.label}</p>
          <p className="matrix-kpi-value mono">{card.value}</p>
          <p className="section-caption">{card.caption}</p>
        </motion.article>
      ))}
    </section>
  );
}

function MainComparison({ rows, playNonce }: { rows: MatrixRow[]; playNonce: number }): JSX.Element {
  const prefersReducedMotion = useReducedMotion();
  const pairs = metricPairs(rows).filter((pair) => pair.baseline !== null && pair.attacked !== null);

  if (pairs.length === 0) {
    return <div className="empty-state">No baseline/attacked metric pairs are available for the current filters.</div>;
  }

  return (
    <div className="matrix-dumbbell">
      <div className="dumbbell-legend">
        <span className="legend-item baseline is-active">Clean / Baseline</span>
        <span className="legend-item attacked is-active">Poisoned / Attacked</span>
      </div>
      <div className="dumbbell-axis">
        <span>0.0</span>
        <span>1.0</span>
      </div>
      <div className="dumbbell-rows">
        {pairs.map((pair) => {
          const baseline = Math.max(0, Math.min(1, pair.baseline ?? 0));
          const attacked = Math.max(0, Math.min(1, pair.attacked ?? 0));
          const left = Math.min(baseline, attacked);
          const width = Math.abs(attacked - baseline);
          return (
            <div key={pair.key} className="dumbbell-row matrix-dumbbell-row">
              <div className="dumbbell-metric">
                {pair.label}
                {pair.excluded ? <span className="matrix-muted-note">{pair.excluded} null</span> : null}
              </div>
              <div className="dumbbell-track-wrap">
                <div className="dumbbell-track" />
                <motion.div
                  className="dumbbell-connector"
                  style={{ left: `${left * 100}%`, background: pair.delta && pair.delta > 0 ? "var(--matrix-targeted)" : "var(--matrix-degradation)" }}
                  initial={false}
                  animate={{ width: `${width * 100}%` }}
                  transition={{ duration: prefersReducedMotion ? 0 : 0.5 }}
                />
                <div className="dumbbell-dot baseline" style={{ left: `${baseline * 100}%` }} />
                <motion.div
                  key={`${pair.key}-${playNonce}`}
                  className="dumbbell-dot attacked matrix-play-dot"
                  initial={{ left: `${baseline * 100}%` }}
                  animate={{ left: `${attacked * 100}%` }}
                  transition={{ duration: prefersReducedMotion ? 0 : playNonce ? 1.2 : 0.35, ease: "easeOut" }}
                />
              </div>
              <div className="dumbbell-values mono">
                <span>{formatPercent(pair.baseline)}</span>
                <span>{formatPercent(pair.attacked)}</span>
                <strong>{formatSigned(pair.delta)}</strong>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ScenarioCards({ rows }: { rows: MatrixRow[] }): JSX.Element {
  const summaries = scenarioSummaries(rows);
  if (!summaries.length) {
    return <div className="empty-state">No scenarios match the active filters.</div>;
  }
  return (
    <section className="matrix-card-grid">
      {summaries.map((summary) => {
        const max = Math.max(...summary.sparkValues, 0.000001);
        return (
          <article key={summary.attackType} className="surface matrix-scenario-card" style={{ borderColor: scenarioColor(summary.attackType) }}>
            <div className="status-row">
              <div>
                <p className="caps-label">Scenario</p>
                <h3 className="card-title">{formatScenarioLabel(summary.attackType)}</h3>
              </div>
              <span className={["badge", summary.badgeTone, "mono"].join(" ")}>{summary.badge}</span>
            </div>
            <div className="matrix-scenario-metrics">
              <div>
                <p className="metric-label">Key {METRIC_LABELS[summary.keyMetric]}</p>
                <p className="matrix-card-number mono">{summary.keyMetric === "asr" ? formatPercent(summary.keyValue) : formatDecimal(summary.keyValue, 4)}</p>
              </div>
              <div>
                <p className="metric-label">Avg delta</p>
                <p className="matrix-card-number mono">{formatSigned(summary.keyDelta)}</p>
              </div>
            </div>
            <div className="matrix-sparkline" aria-label={`${summary.attackType} mini bar chart`}>
              {summary.sparkValues.map((value, index) => (
                <span key={`${summary.attackType}-${index}`} style={{ height: `${Math.max(8, (Math.abs(value) / max) * 100)}%`, background: scenarioColor(summary.attackType) }} />
              ))}
            </div>
            <p className="section-caption">{summary.rows.length} rows; values computed from filtered CSV records.</p>
          </article>
        );
      })}
    </section>
  );
}

function RankerComparison({ rows, metric }: { rows: MatrixRow[]; metric: MatrixMetricKey }): JSX.Element | null {
  const summaries = rankerSummaries(rows, metric);
  if (summaries.length < 2) {
    return null;
  }
  const strongest = strongestBy(summaries, (summary) => summary.averageEffect);
  return (
    <section className="surface matrix-section">
      <div className="status-row">
        <div>
          <h3 className="section-title">Deterministic Ranker vs LLM Reranker</h3>
          <p className="section-caption">Computed from ranking_mode groups and selected {METRIC_LABELS[metric]} effect.</p>
        </div>
        {strongest ? <span className="badge attack mono">Most vulnerable: {formatScenarioLabel(strongest.rankingMode)}</span> : null}
      </div>
      <div className="matrix-ranker-grid">
        {summaries.map((summary) => (
          <article key={summary.rankingMode} className={summary === strongest ? "surface-elevated matrix-ranker-card is-strongest" : "surface-elevated matrix-ranker-card"}>
            <p className="card-title">{formatScenarioLabel(summary.rankingMode)}</p>
            <p className="matrix-card-number mono">{formatSigned(summary.averageEffect)}</p>
            <p className="section-caption">{summary.rows.length} rows; strongest {formatSigned(summary.strongestEffect)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Heatmap({ rows, metric }: { rows: MatrixRow[]; metric: MatrixMetricKey }): JSX.Element {
  const max = Math.max(...rows.map((row) => Math.abs(metricEffect(row, metric) ?? 0)), 0.000001);
  return (
    <section className="surface matrix-section">
      <h3 className="section-title">Matrix heatmap</h3>
      <p className="section-caption">Rows are matrix runs; intensity is selected {METRIC_LABELS[metric]} attack-effect magnitude.</p>
      <div className="matrix-heatmap">
        {rows.map((row) => {
          const value = metricEffect(row, metric);
          const intensity = value === null ? 0 : Math.min(1, Math.abs(value) / max);
          return (
            <div key={row.label} className="matrix-heatmap-row">
              <span className="matrix-heatmap-label mono" title={`run_id: ${row.runId}; original label: ${row.label}`}>{displayRunId(row)}<small>{row.runId}</small></span>
              <span
                className="matrix-heatmap-cell"
                style={{ opacity: value === null ? 0.32 : 0.45 + intensity * 0.55, background: value === null ? "var(--bg-elevated)" : `linear-gradient(90deg, var(--matrix-heat-low), var(--matrix-heat-high))` }}
                title={`${row.label}: ${formatSigned(value)}`}
              />
              <span className="matrix-heatmap-value mono">{formatSigned(value)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function RunDrawer({ row, onClose }: { row: MatrixRow | null; onClose: () => void }): JSX.Element {
  return (
    <AnimatePresence>
      {row ? (
        <motion.div className="matrix-drawer-overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.aside className="matrix-drawer" initial={{ x: 420 }} animate={{ x: 0 }} exit={{ x: 420 }} transition={{ duration: 0.25 }}>
            <div className="status-row">
              <div>
                <p className="caps-label">Run explorer</p>
                <h3 className="section-title">{displayRunId(row)}</h3>
                <p className="section-caption mono">Canonical run_id: {row.runId}</p>
              </div>
              <button type="button" className="btn" onClick={onClose}>Close</button>
            </div>
            <div className="matrix-delta-grid">
              {METRIC_OPTIONS.map((metric) => (
                <div key={metric} className="surface-elevated">
                  <p className="metric-label">{METRIC_LABELS[metric]}</p>
                  <p className="mono">{formatDecimal(row.baseline[metric], 4)} → {formatDecimal(row.attacked[metric], 4)}</p>
                  <strong className="mono">{formatSigned(row.delta[metric])}</strong>
                </div>
              ))}
            </div>
            <p className="section-caption">Original encoded label: <span className="mono">{row.label}</span></p>
            <h4 className="card-title">Snapshot fields</h4>
            <div className="matrix-field-list">
              {Object.entries(row.raw).map(([key, value]) => (
                <div key={key}>
                  <span>{key}</span>
                  <code>{value || "—"}</code>
                </div>
              ))}
            </div>
          </motion.aside>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

function RunExplorer({ rows, onSelect }: { rows: MatrixRow[]; onSelect: (row: MatrixRow) => void }): JSX.Element {
  const [sortKey, setSortKey] = useState<"label" | "attackType" | "rankingMode" | "effect">("effect");
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      if (sortKey === "effect") {
        return Math.abs(overallAttackEffect(b) ?? 0) - Math.abs(overallAttackEffect(a) ?? 0);
      }
      return String(a[sortKey]).localeCompare(String(b[sortKey]));
    });
  }, [rows, sortKey]);

  return (
    <section className="surface matrix-section">
      <div className="status-row">
        <div>
          <h3 className="section-title">Run explorer</h3>
          <p className="section-caption">Use Inspect to open all CSV fields and metric deltas for a run.</p>
        </div>
        <select className="matrix-select" value={sortKey} onChange={(event) => setSortKey(event.target.value as typeof sortKey)}>
          <option value="effect">Sort by effect</option>
          <option value="label">Sort by run ID</option>
          <option value="attackType">Sort by scenario</option>
          <option value="rankingMode">Sort by ranker</option>
        </select>
      </div>
      <div className="data-table-wrap">
        <table className="data-table matrix-run-table">
          <thead>
            <tr>
              <th>Run ID</th>
              <th>Source run</th>
              <th>Scenario</th>
              <th>Ranker</th>
              <th>Attacker</th>
              <th>ASR</th>
              <th>ΔNDCG</th>
              <th>ΔMRR</th>
              <th>ΔHR</th>
              <th>Inspect</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.label}>
                <td className="mono" title={row.label}>{displayRunId(row)}</td>
                <td className="mono">{row.runId}</td>
                <td>{formatScenarioLabel(row.attackType)}</td>
                <td>{formatScenarioLabel(row.rankingMode)}</td>
                <td>{row.attackerProvider}</td>
                <td className="mono">{formatPercent(row.attacked.asr)}</td>
                <td className="mono">{formatSigned(row.delta.ndcg)}</td>
                <td className="mono">{formatSigned(row.delta.mrr)}</td>
                <td className="mono">{formatSigned(row.delta.hr)}</td>
                <td><button type="button" className="matrix-inspect-button" onClick={() => onSelect(row)}>Inspect</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function RawTable({ rows }: { rows: MatrixRow[] }): JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const filtered = rows.filter((row) => JSON.stringify(row.raw).toLowerCase().includes(query.toLowerCase()));
  const columns = rows[0] ? Object.keys(rows[0].raw) : [];
  return (
    <section className="surface matrix-section">
      <button type="button" className="matrix-collapse-button" onClick={() => setOpen((current) => !current)}>
        <span>Raw matrix table</span>
        <span className="badge neutral mono">{open ? "Hide" : "Show"}</span>
      </button>
      {open ? (
        <div className="stack" style={{ marginTop: 14 }}>
          <input className="matrix-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search raw CSV rows…" />
          <div className="data-table-wrap matrix-raw-wrap">
            <table className="data-table matrix-raw-table">
              <thead>
                <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.label}>{columns.map((column) => <td key={column}>{row.raw[column] || "—"}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function MatrixResults(): JSX.Element {
  const [payload, setPayload] = useState<MatrixPayload | null>(null);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [error, setError] = useState<string | null>(null);
  const [playNonce, setPlayNonce] = useState(0);
  const [selectedRun, setSelectedRun] = useState<MatrixRow | null>(null);

  useEffect(() => {
    let canceled = false;
    loadMatrixPayload()
      .then((nextPayload) => {
        if (!canceled) {
          setPayload(nextPayload);
        }
      })
      .catch((err) => {
        if (!canceled) {
          setError(err instanceof Error ? err.message : "Failed to load matrix results");
        }
      });
    return () => {
      canceled = true;
    };
  }, []);

  const allRows = payload?.rows ?? [];
  const filteredRows = useMemo(() => applyFilters(allRows, filters), [allRows, filters]);
  const options = useMemo(() => ({
    attackTypes: uniqueValues(allRows, (row) => row.attackType),
    rankingModes: uniqueValues(allRows, (row) => row.rankingMode),
    retrievalModes: uniqueValues(allRows, (row) => row.retrievalMode),
    attackerProviders: uniqueValues(allRows, (row) => row.attackerProvider),
    statuses: uniqueValues(allRows, (row) => row.status),
  }), [allRows]);
  const kpis = useMemo(() => buildKpis(filteredRows, allRows, filters.metric), [filteredRows, allRows, filters.metric]);
  const insights = useMemo(() => insightCards(filteredRows, filters.metric), [filteredRows, filters.metric]);
  const playable = metricPairs(filteredRows).some((pair) => pair.baseline !== null && pair.attacked !== null);

  return (
    <div className="page-wrap matrix-page-wrap">
      <header className="matrix-hero">
        <div className="matrix-hero-grid" aria-hidden="true" />
        <div>
          <span className="badge accent mono">Attack Surface Map</span>
          <h2 className="page-title">Matrix Results</h2>
          <p className="page-subtitle">Full matrix benchmark across runs, scenarios, conditions, and rankers.</p>
        </div>
        {payload ? (
          <div className="matrix-provenance">
            <p className="caps-label">Snapshot provenance</p>
            <p className="mono">{payload.manifest.row_count} rows · {shortHash(payload.manifest.sha256)}</p>
            <p className="section-caption">Source: {payload.manifest.source_path}</p>
          </div>
        ) : null}
      </header>

      {error ? <div className="error-state">{error}</div> : null}
      {!payload && !error ? <div className="loading-state">Loading matrix snapshot…</div> : null}

      {payload ? (
        <>
          <KpiGrid cards={kpis} />

          <section className="surface matrix-filter-panel">
            <FilterGroup label="Scenario" value={filters.attackType} options={options.attackTypes} onChange={(value) => setFilters(updateFilter(filters, "attackType", value))} />
            <FilterGroup label="Ranker" value={filters.rankingMode} options={options.rankingModes} onChange={(value) => setFilters(updateFilter(filters, "rankingMode", value))} />
            <FilterGroup label="Retrieval" value={filters.retrievalMode} options={options.retrievalModes} onChange={(value) => setFilters(updateFilter(filters, "retrievalMode", value))} />
            <FilterGroup label="Attacker" value={filters.attackerProvider} options={options.attackerProviders} onChange={(value) => setFilters(updateFilter(filters, "attackerProvider", value))} />
            <FilterGroup label="Status" value={filters.status} options={options.statuses} onChange={(value) => setFilters(updateFilter(filters, "status", value))} />
            <MetricSelector value={filters.metric} onChange={(value) => setFilters(updateFilter(filters, "metric", value))} />
          </section>

          <section className="surface matrix-section">
            <div className="status-row">
              <div>
                <h3 className="section-title">Clean vs poisoned comparison</h3>
                <p className="section-caption">Averages compare baseline_* and attacked_* columns for {filteredRows.length} filtered rows.</p>
              </div>
              <button type="button" className="btn btn-primary" disabled={!playable} onClick={() => setPlayNonce((current) => current + 1)}>
                Play attack
              </button>
            </div>
            <MainComparison rows={filteredRows} playNonce={playNonce} />
          </section>

          <ScenarioCards rows={filteredRows} />
          <RankerComparison rows={filteredRows} metric={filters.metric} />

          <section className="split-grid matrix-proof-grid">
            <Heatmap rows={filteredRows} metric={filters.metric} />
            <section className="surface matrix-section">
              <h3 className="section-title">Computed insights</h3>
              <div className="stack" style={{ marginTop: 14 }}>
                {insights.map((insight) => (
                  <article key={insight.title} className={["surface-elevated", "matrix-insight", toneClass(insight.tone)].join(" ")}>
                    <p className="card-title">{insight.title}</p>
                    <p className="section-caption">{insight.evidence}</p>
                  </article>
                ))}
              </div>
            </section>
          </section>

          <RunExplorer rows={filteredRows} onSelect={setSelectedRun} />
          <RawTable rows={filteredRows} />

          <section className="surface matrix-section">
            <h3 className="section-title">Markdown summary</h3>
            <pre className="matrix-markdown-preview">{payload.markdown.slice(0, 1400)}</pre>
          </section>
        </>
      ) : null}

      <RunDrawer row={selectedRun} onClose={() => setSelectedRun(null)} />
    </div>
  );
}
