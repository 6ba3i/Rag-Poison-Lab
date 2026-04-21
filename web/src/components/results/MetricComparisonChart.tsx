import { ResponsiveBar } from "@nivo/bar";

import type { MetricRow } from "../../lib/runPresentation";

interface MetricComparisonChartProps {
  mode: string;
  rows: MetricRow[];
}

interface ChartDatum {
  [key: string]: string | number;
  metric: string;
  baseline: number;
  attacked: number;
}

function buildChartData(rows: MetricRow[]): ChartDatum[] {
  return rows
    .filter((row) => row.baseline !== null && row.attacked !== null)
    .map((row) => ({
      metric: row.label,
      baseline: row.baseline ?? 0,
      attacked: row.attacked ?? 0,
    }));
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function clampToUnit(value: number): number {
  if (value < 0) {
    return 0;
  }
  if (value > 1) {
    return 1;
  }
  return value;
}

function connectorColor(baseline: number, attacked: number): string {
  if (attacked > baseline) {
    return "var(--chart-connector-better)";
  }
  if (attacked < baseline) {
    return "var(--chart-connector-worse)";
  }
  return "var(--chart-connector-neutral)";
}

function DumbbellChart({ rows }: { rows: MetricRow[] }): JSX.Element {
  const visibleRows = rows.filter((row) => row.baseline !== null && row.attacked !== null);

  return (
    <div className="dumbbell-chart">
      <div className="dumbbell-legend">
        <span className="legend-item baseline is-active">Baseline</span>
        <span className="legend-item attacked is-active">Attacked</span>
      </div>

      <div className="dumbbell-axis">
        <span>0.0</span>
        <span>1.0</span>
      </div>

      <div className="dumbbell-rows">
        {visibleRows.map((row) => {
          const baseline = clampToUnit(row.baseline ?? 0);
          const attacked = clampToUnit(row.attacked ?? 0);
          const left = Math.min(baseline, attacked);
          const width = Math.abs(attacked - baseline);

          return (
            <div key={row.key} className="dumbbell-row">
              <div className="dumbbell-metric">{row.label}</div>
              <div className="dumbbell-track-wrap">
                <div className="dumbbell-track" />
                <div
                  className="dumbbell-connector"
                  style={{
                    left: `${left * 100}%`,
                    width: `${width * 100}%`,
                    background: connectorColor(baseline, attacked),
                  }}
                />
                <div className="dumbbell-dot baseline" style={{ left: `${baseline * 100}%` }} />
                <div className="dumbbell-dot attacked" style={{ left: `${attacked * 100}%` }} />
              </div>
              <div className="dumbbell-values">
                <span>{formatPercent(baseline)}</span>
                <span>{formatPercent(attacked)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GroupedBarChart({ rows }: { rows: MetricRow[] }): JSX.Element {
  const data = buildChartData(rows);

  return (
    <div className="metric-chart" style={{ height: 260 }}>
      <ResponsiveBar
        data={data}
        keys={["baseline", "attacked"]}
        indexBy="metric"
        margin={{ top: 20, right: 16, bottom: 40, left: 48 }}
        padding={0.3}
        groupMode="grouped"
        valueScale={{ type: "linear", min: 0, max: 1 }}
        indexScale={{ type: "band", round: true }}
        colors={({ id }) => (id === "baseline" ? "var(--baseline-strong)" : "var(--attack-strong)")}
        borderRadius={4}
        enableGridY
        axisBottom={{
          tickSize: 0,
          tickPadding: 8,
        }}
        axisLeft={{
          tickSize: 0,
          tickPadding: 8,
          tickValues: [0, 0.25, 0.5, 0.75, 1],
          format: (value) => Number(value).toFixed(2),
        }}
        theme={{
          text: {
            fill: "var(--chart-text)",
            fontSize: 12,
          },
          axis: {
            ticks: {
              line: { stroke: "var(--chart-grid)" },
              text: { fill: "var(--chart-text)" },
            },
            domain: {
              line: { stroke: "var(--chart-grid)" },
            },
          },
          grid: {
            line: { stroke: "var(--chart-grid)", strokeOpacity: 0.45 },
          },
          tooltip: {
            container: {
              background: "var(--chart-tooltip-bg)",
              color: "var(--chart-tooltip-text)",
              border: "1px solid var(--chart-tooltip-border)",
              borderRadius: "8px",
            },
          },
        }}
        labelSkipWidth={16}
        labelSkipHeight={16}
        labelTextColor="var(--chart-tooltip-text)"
        tooltip={({ id, value, color }) => (
          <div className="chart-tooltip">
            <span className="chart-tooltip-dot" style={{ background: color }} />
            <span>{String(id)}</span>
            <strong>{formatPercent(Number(value))}</strong>
          </div>
        )}
      />
    </div>
  );
}

export function MetricComparisonChart({ mode, rows }: MetricComparisonChartProps): JSX.Element {
  const hasData = rows.some((row) => row.baseline !== null && row.attacked !== null);

  if (!hasData) {
    return <div className="empty-state">Metrics are unavailable for chart rendering.</div>;
  }

  if (mode === "single") {
    return <DumbbellChart rows={rows} />;
  }

  return <GroupedBarChart rows={rows} />;
}
