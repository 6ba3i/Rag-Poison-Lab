import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError, getRecommendations, getTrace, getUserHistory, getUserProfile } from "../api/client";
import type { RecommendationItem, TraceResponse, UserHistoryItem, UserProfile } from "../api/types";
import { HistoryTable } from "../components/HistoryTable";
import { RecCompare } from "../components/RecCompare";
import { TracePanel } from "../components/TracePanel";

type DetailPanel = "trace" | "history";

const K_OPTIONS = [5, 10, 20] as const;

export function UserDetail(): JSX.Element {
  const { userId } = useParams<{ userId: string }>();
  const parsedUserId = Number(userId);
  const isValidUserId = Number.isInteger(parsedUserId) && parsedUserId > 0;

  const [k, setK] = useState<number>(10);
  const [activePanel, setActivePanel] = useState<DetailPanel>("trace");

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<UserHistoryItem[]>([]);
  const [baselineRecs, setBaselineRecs] = useState<RecommendationItem[]>([]);
  const [attackedRecs, setAttackedRecs] = useState<RecommendationItem[]>([]);
  const [baselineTrace, setBaselineTrace] = useState<TraceResponse | null>(null);
  const [attackedTrace, setAttackedTrace] = useState<TraceResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<void> => {
    if (!isValidUserId) {
      setError("Invalid user id");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [profilePayload, historyPayload, baselineRecsPayload, attackedRecsPayload, baselineTracePayload, attackedTracePayload] =
        await Promise.all([
          getUserProfile(parsedUserId),
          getUserHistory(parsedUserId, "all"),
          getRecommendations(parsedUserId, "baseline", k),
          getRecommendations(parsedUserId, "attacked", k),
          getTrace(parsedUserId, "baseline", k),
          getTrace(parsedUserId, "attacked", k),
        ]);

      setProfile(profilePayload);
      setHistory(historyPayload);
      setBaselineRecs(baselineRecsPayload);
      setAttackedRecs(attackedRecsPayload);
      setBaselineTrace(baselineTracePayload);
      setAttackedTrace(attackedTracePayload);
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to load user analysis";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [isValidUserId, k, parsedUserId]);

  useEffect(() => {
    void load();
  }, [load]);

  const topGenres = useMemo(() => profile?.top_genres ?? [], [profile]);

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">User Analysis #{userId ?? "-"}</h2>
          <p className="page-subtitle">Comparison-first view of baseline vs attacked recommendations and retrieval trace.</p>
        </div>

        <div className="inline-actions">
          <Link to="/users" className="btn btn-ghost">
            Back to users
          </Link>
          <button type="button" className="btn" onClick={() => void load()}>
            Refresh
          </button>
        </div>
      </header>

      <section className="surface">
        <div className="status-row" style={{ alignItems: "flex-start", flexWrap: "wrap" }}>
          <div className="user-stats-block" style={{ flex: 1 }}>
            <div className="user-stat">
              <p className="user-preview-stat-label">Ratings</p>
              <p className="user-preview-stat-value">{profile?.rating_count ?? "-"}</p>
            </div>
            <div className="user-stat">
              <p className="user-preview-stat-label">Mean rating</p>
              <p className="user-preview-stat-value">{profile ? profile.mean_rating.toFixed(2) : "-"}</p>
            </div>
            <div className="user-stat">
              <p className="user-preview-stat-label">Top genres</p>
              {topGenres.length > 0 ? (
                <div className="genre-pills" style={{ marginTop: 8 }}>
                  {topGenres.map((item) => (
                    <span key={item.genre} className="genre-pill">
                      {item.genre} &middot; {item.count}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ marginTop: 8, fontSize: 14, color: "var(--text-secondary)" }}>-</p>
              )}
            </div>
          </div>

          <label className="field" style={{ minWidth: 180 }}>
            <span className="field-label">Top-K</span>
            <select value={k} onChange={(event) => setK(Number(event.target.value))} className="select">
              {K_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {loading ? <div className="loading-state">Loading analysis…</div> : null}
      {error ? <div className="error-state">{error}</div> : null}

      {!loading && !error ? (
        <>
          <section className="surface">
            <div className="status-row" style={{ marginBottom: 12 }}>
              <div>
                <h3 className="section-title">Recommendation comparison</h3>
                <p className="section-caption">Primary analysis surface showing ranking shifts and cross-list membership differences.</p>
              </div>
              <span className="badge warning">Items appearing only on one side are highlighted in amber</span>
            </div>
            <RecCompare baseline={baselineRecs} attacked={attackedRecs} />
          </section>

          <section className="surface">
            <div className="inline-actions" style={{ marginBottom: 16 }}>
              <button
                type="button"
                className={["btn", activePanel === "trace" ? "btn-primary" : ""].join(" ")}
                onClick={() => setActivePanel("trace")}
              >
                Retrieval trace
              </button>
              <button
                type="button"
                className={["btn", activePanel === "history" ? "btn-primary" : ""].join(" ")}
                onClick={() => setActivePanel("history")}
              >
                Rating history
              </button>
            </div>

            {activePanel === "trace" ? <TracePanel baseline={baselineTrace} attacked={attackedTrace} /> : null}
            {activePanel === "history" ? <HistoryTable items={history} /> : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
