import { useEffect, useState } from "react";

import { ApiError, getResultRunDetail, listResultRuns } from "../api/client";
import type { RunDetailResponse, RunSummary } from "../api/types";
import { formatMetric, formatNumber, formatTimestamp } from "../lib/format";

export function Results(): JSX.Element {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetailResponse | null>(null);

  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadRuns(cursor: string | null, append: boolean): Promise<void> {
    setLoadingList(true);
    setError(null);

    try {
      const payload = await listResultRuns(20, cursor);
      setRuns((current) => (append ? [...current, ...payload.items] : payload.items));
      setNextCursor(payload.next_cursor);

      const nextSelected = selectedLabel ?? payload.items[0]?.label ?? null;
      setSelectedLabel(nextSelected);
      if (nextSelected && (!detail || detail.summary.label !== nextSelected)) {
        void loadDetail(nextSelected);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to load runs";
      setError(message);
      if (!append) {
        setRuns([]);
      }
    } finally {
      setLoadingList(false);
    }
  }

  async function loadDetail(label: string): Promise<void> {
    setLoadingDetail(true);
    setError(null);

    try {
      const payload = await getResultRunDetail(label);
      setDetail(payload);
      setSelectedLabel(label);
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to load run detail";
      setError(message);
      setDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    void loadRuns(null, false);
  }, []);

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Results</h2>
          <p className="page-subtitle">Run history, summary outcomes, and detailed experiment artifacts.</p>
        </div>
      </header>

      {error ? <div className="error-state">{error}</div> : null}

      <section className="split-grid">
        <article className="surface">
          <div className="status-row" style={{ marginBottom: 12 }}>
            <h3 className="section-title">Run history</h3>
            <span className="badge">{runs.length} loaded</span>
          </div>

          {loadingList && runs.length === 0 ? <div className="loading-state">Loading run list…</div> : null}

          {runs.length > 0 ? (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Mode</th>
                    <th>Users</th>
                    <th>Delta ASR</th>
                    <th>Delta NDCG</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr
                      key={run.label}
                      className={run.label === selectedLabel ? "is-selected" : ""}
                      onClick={() => void loadDetail(run.label)}
                    >
                      <td>
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <span>{run.label}</span>
                          <span className="text-meta">{formatTimestamp(run.generated_at_utc)}</span>
                        </div>
                      </td>
                      <td>{run.mode ?? "-"}</td>
                      <td>{formatNumber(run.evaluated_users)}</td>
                      <td>{formatMetric(run.delta.asr)}</td>
                      <td>{formatMetric(run.delta.ndcg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : !loadingList ? (
            <div className="empty-state">No run history available.</div>
          ) : null}

          {nextCursor ? (
            <button type="button" className="btn" style={{ marginTop: 12 }} onClick={() => void loadRuns(nextCursor, true)}>
              Load more
            </button>
          ) : null}
        </article>

        <article className="surface">
          <h3 className="section-title">Run detail</h3>

          {loadingDetail ? <div className="loading-state" style={{ marginTop: 12 }}>Loading run detail…</div> : null}

          {!loadingDetail && !detail ? (
            <div className="empty-state" style={{ marginTop: 12 }}>Select a run to inspect details.</div>
          ) : null}

          {detail ? (
            <div className="stack" style={{ marginTop: 14 }}>
              <div className="metric-grid" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
                <article className="metric-card">
                  <p className="metric-label">Baseline ASR</p>
                  <p className="metric-value">{formatMetric(detail.summary.baseline.asr)}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Attacked ASR</p>
                  <p className="metric-value warning">{formatMetric(detail.summary.attacked.asr)}</p>
                </article>
                <article className="metric-card">
                  <p className="metric-label">Delta ASR</p>
                  <p className="metric-value warning">{formatMetric(detail.summary.delta.asr)}</p>
                </article>
              </div>

              <div className="surface-elevated">
                <div className="status-row">
                  <span className="text-meta">Label</span>
                  <span className="badge primary">{detail.summary.label}</span>
                </div>
                <div className="status-row" style={{ marginTop: 8 }}>
                  <span className="text-meta">Generated</span>
                  <span className="text-meta">{formatTimestamp(detail.summary.generated_at_utc)}</span>
                </div>
                <div className="status-row" style={{ marginTop: 8 }}>
                  <span className="text-meta">Warnings</span>
                  <span className="badge warning">{detail.warnings.length}</span>
                </div>
              </div>

              {detail.warnings.length > 0 ? (
                <div className="surface-elevated">
                  <p className="text-meta">Warnings</p>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
                    {detail.warnings.map((warning) => (
                      <li key={warning} style={{ fontSize: 13, marginBottom: 4 }}>
                        {warning}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="surface-elevated">
                <p className="text-meta">Artifacts</p>
                <pre className="code-block" style={{ marginTop: 8 }}>{JSON.stringify(detail.artifacts, null, 2)}</pre>
              </div>

              {detail.manifest ? (
                <div className="surface-elevated">
                  <p className="text-meta">Manifest</p>
                  <pre className="code-block" style={{ marginTop: 8 }}>{JSON.stringify(detail.manifest, null, 2)}</pre>
                </div>
              ) : null}
            </div>
          ) : null}
        </article>
      </section>
    </div>
  );
}
