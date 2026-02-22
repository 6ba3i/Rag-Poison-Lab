import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import {
  ApiError,
  getRecommendations,
  getTrace,
  getUserHistory,
  getUserProfile,
} from "../api/client";
import type {
  RecommendationItem,
  RecommendationMode,
  TraceResponse,
  UserHistoryItem,
  UserProfile,
} from "../api/types";
import { HistoryTable } from "../components/HistoryTable";
import { RecCompare } from "../components/RecCompare";
import { TracePanel } from "../components/TracePanel";

type DashboardTab = "history" | "recommendations" | "trace";

const K_OPTIONS = [5, 10, 20] as const;

export function Dashboard(): JSX.Element {
  const { userId } = useParams<{ userId: string }>();
  const parsedUserId = Number(userId);

  const [tab, setTab] = useState<DashboardTab>("history");
  const [focusMode, setFocusMode] = useState<RecommendationMode>("baseline");
  const [k, setK] = useState<number>(10);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<UserHistoryItem[]>([]);
  const [baselineRecs, setBaselineRecs] = useState<RecommendationItem[]>([]);
  const [attackedRecs, setAttackedRecs] = useState<RecommendationItem[]>([]);
  const [baselineTrace, setBaselineTrace] = useState<TraceResponse | null>(null);
  const [attackedTrace, setAttackedTrace] = useState<TraceResponse | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const validUserId = Number.isInteger(parsedUserId) && parsedUserId > 0;

  const loadDashboard = useCallback(async (): Promise<void> => {
    if (!validUserId) {
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
      const message = err instanceof ApiError ? err.detail : "Failed to load dashboard data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [k, parsedUserId, validUserId]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const genresSummary = useMemo(() => {
    if (!profile || profile.top_genres.length === 0) {
      return "-";
    }
    return profile.top_genres.map((entry) => `${entry.genre} (${entry.count})`).join(", ");
  }, [profile]);

  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-100">User Dashboard</h2>
            <p className="text-sm text-slate-400">User ID: {userId ?? "unknown"}</p>
          </div>

          <button
            type="button"
            onClick={() => void loadDashboard()}
            className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition-colors duration-150 hover:border-slate-500 hover:text-slate-100"
          >
            Refresh
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Attack mode focus</p>
            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setFocusMode("baseline")}
                className={[
                  "rounded-lg border px-3 py-1.5 text-xs transition-colors duration-150",
                  focusMode === "baseline"
                    ? "border-slate-400 bg-slate-700/60 text-slate-100"
                    : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500",
                ].join(" ")}
              >
                Baseline
              </button>
              <button
                type="button"
                onClick={() => setFocusMode("attacked")}
                className={[
                  "rounded-lg border px-3 py-1.5 text-xs transition-colors duration-150",
                  focusMode === "attacked"
                    ? "border-slate-400 bg-slate-700/60 text-slate-100"
                    : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500",
                ].join(" ")}
              >
                Attacked
              </button>
            </div>
          </div>

          <label className="rounded-xl border border-slate-700 bg-slate-900/60 p-3 text-sm text-slate-300">
            <span className="text-xs uppercase tracking-wide text-slate-500">K Selector</span>
            <select
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 outline-none transition-colors duration-150 focus:border-slate-400"
            >
              {K_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Top genres</p>
            <p className="mt-2 text-sm text-slate-300">{genresSummary}</p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {(["history", "recommendations", "trace"] as const).map((tabName) => (
            <button
              key={tabName}
              type="button"
              onClick={() => setTab(tabName)}
              className={[
                "rounded-lg border px-3 py-2 text-sm capitalize transition-colors duration-150",
                tab === tabName
                  ? "border-slate-400 bg-slate-700/60 text-slate-100"
                  : "border-slate-700 bg-slate-900 text-slate-300 hover:border-slate-500",
              ].join(" ")}
            >
              {tabName}
            </button>
          ))}
        </div>
      </section>

      {loading ? <div className="panel p-4 text-sm text-slate-400">Loading dashboard...</div> : null}
      {error ? <div className="panel p-4 text-sm text-rose-300">{error}</div> : null}

      {!loading && !error && tab === "history" ? (
        <div className="space-y-4">
          <section className="panel p-4">
            <h3 className="text-base font-semibold text-slate-100">Profile</h3>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Ratings</p>
                <p className="mt-1 text-sm text-slate-200">{profile?.rating_count ?? 0}</p>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Mean rating</p>
                <p className="mt-1 text-sm text-slate-200">{profile ? profile.mean_rating.toFixed(2) : "0.00"}</p>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/60 p-3">
                <p className="text-xs uppercase tracking-wide text-slate-500">Recent movies</p>
                <p className="mt-1 text-sm text-slate-200">{profile?.recent_movie_ids.slice(0, 5).join(", ") || "-"}</p>
              </div>
            </div>
          </section>
          <HistoryTable items={history} />
        </div>
      ) : null}

      {!loading && !error && tab === "recommendations" ? (
        <RecCompare baseline={baselineRecs} attacked={attackedRecs} focusMode={focusMode} />
      ) : null}

      {!loading && !error && tab === "trace" ? (
        <TracePanel baseline={baselineTrace} attacked={attackedTrace} focusMode={focusMode} />
      ) : null}
    </div>
  );
}
