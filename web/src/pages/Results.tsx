import { useEffect, useRef, useState } from "react";

import { ApiError, getResultRunDetail, listResultRuns } from "../api/client";
import type { RunDetailResponse, RunSummary } from "../api/types";
import { formatMetric, formatNumber, formatTimestamp } from "../lib/format";
import { buildHeroInfo } from "../lib/runPresentation";
import { RunResultView } from "../components/results/RunResultView";

function quickOutcome(run: RunSummary, detail: RunDetailResponse | null): { label: string; tone: string } {
  if (detail) {
    const outcome = buildHeroInfo(detail).outcome;
    return { label: outcome.label, tone: outcome.tone };
  }

  const asrDelta = run.delta.asr;
  if (typeof asrDelta === "number" && asrDelta > 0.001) {
    return { label: "Attack succeeded", tone: "warning" };
  }

  return { label: "Completed", tone: "" };
}

function attackTypeForDetail(detail: RunDetailResponse | null): string {
  if (!detail || !detail.metadata || typeof detail.metadata !== "object") {
    return "-";
  }
  const attackType = (detail.metadata as Record<string, unknown>).attack_type;
  return typeof attackType === "string" ? attackType : "-";
}

export function Results(): JSX.Element {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetailResponse | null>(null);
  const [detailCache, setDetailCache] = useState<Record<string, RunDetailResponse>>({});

  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detailInFlight = useRef<Set<string>>(new Set());

  async function enrichRuns(items: RunSummary[]): Promise<void> {
    const labelsToLoad = items
      .map((run) => run.label)
      .filter((label) => !detailCache[label] && !detailInFlight.current.has(label));

    if (labelsToLoad.length === 0) {
      return;
    }

    labelsToLoad.forEach((label) => detailInFlight.current.add(label));

    const results = await Promise.allSettled(
      labelsToLoad.map(async (label) => {
        const payload = await getResultRunDetail(label);
        return { label, payload };
      }),
    );

    setDetailCache((current) => {
      const next = { ...current };
      results.forEach((result) => {
        if (result.status === "fulfilled") {
          next[result.value.label] = result.value.payload;
        }
      });
      return next;
    });

    labelsToLoad.forEach((label) => detailInFlight.current.delete(label));
  }

  async function loadRuns(cursor: string | null, append: boolean): Promise<void> {
    setLoadingList(true);
    setError(null);

    try {
      const payload = await listResultRuns(20, cursor);

      setRuns((current) => {
        const merged = append ? [...current, ...payload.items] : payload.items;
        void enrichRuns(merged);
        return merged;
      });

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

    const cached = detailCache[label] ?? null;
    if (cached) {
      setDetail(cached);
      setSelectedLabel(label);
    }

    try {
      const payload = await getResultRunDetail(label);
      setDetail(payload);
      setSelectedLabel(label);
      setDetailCache((current) => ({ ...current, [label]: payload }));
    } catch (err) {
      if (!cached) {
        const message = err instanceof ApiError ? err.detail : "Failed to load run detail";
        setError(message);
        setDetail(null);
      }
    } finally {
      setLoadingDetail(false);
    }
  }

  useEffect(() => {
    void loadRuns(null, false);
  }, []);

  return (
    <div className="page-wrap results-page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Results</h2>
          <p className="page-subtitle">Run history, summary outcomes, and detailed experiment artifacts.</p>
        </div>
      </header>

      {error ? <div className="error-state">{error}</div> : null}

      <section className="split-grid results-layout-grid">
        <article className="surface results-history-pane">
          <div className="status-row" style={{ marginBottom: 12 }}>
            <h3 className="section-title">Run history</h3>
            <span className="badge">{runs.length} loaded</span>
          </div>

          {loadingList && runs.length === 0 ? <div className="loading-state">Loading run list…</div> : null}

          {runs.length > 0 ? (
            <div className="data-table-wrap">
              <table className="data-table results-history-table">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Mode</th>
                    <th>Attack type</th>
                    <th>Target movie</th>
                    <th>Outcome</th>
                    <th>ASR</th>
                    <th>Delta NDCG</th>
                    <th>Delta MRR</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => {
                    const runDetail = detailCache[run.label] ?? null;
                    const outcome = quickOutcome(run, runDetail);

                    return (
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
                        <td>{attackTypeForDetail(runDetail)}</td>
                        <td>{formatNumber(run.target_movie_id)}</td>
                        <td>
                          <span className={["badge", outcome.tone].join(" ")}>{outcome.label}</span>
                        </td>
                        <td>{formatMetric(run.attacked.asr)}</td>
                        <td>{formatMetric(run.delta.ndcg)}</td>
                        <td>{formatMetric(run.delta.mrr)}</td>
                      </tr>
                    );
                  })}
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

        <div className="stack results-detail-rail">
          {loadingDetail ? <div className="loading-state">Loading run detail…</div> : null}

          {!loadingDetail && !detail ? <div className="empty-state">Select a run to inspect details.</div> : null}

          {detail ? <RunResultView detail={detail} /> : null}
        </div>
      </section>
    </div>
  );
}
