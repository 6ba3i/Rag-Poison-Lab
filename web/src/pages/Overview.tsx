import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, getAttackSettings, getLlmSettings, listResultRuns } from "../api/client";
import type { AttackSettingsResponse, LlmConfig, RunSummary } from "../api/types";
import { formatMetric, formatNumber, formatTimestamp } from "../lib/format";

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asrCardTone(value: number | null): "tone-attack" | "tone-success" | "tone-warning" {
  if (value === 1) {
    return "tone-attack";
  }
  if (value === 0) {
    return "tone-success";
  }
  return "tone-warning";
}

function ndcgValueTone(value: number | null): "tone-warning" | "tone-attack" | "tone-tertiary" {
  if (value === null || value === 0) {
    return "tone-tertiary";
  }
  return value > 0 ? "tone-warning" : "tone-attack";
}

export function Overview(): JSX.Element {
  const [attackSettings, setAttackSettings] = useState<AttackSettingsResponse | null>(null);
  const [llmSettings, setLlmSettings] = useState<LlmConfig | null>(null);
  const [latestRun, setLatestRun] = useState<RunSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError(null);

      try {
        const [attackPayload, llmPayload, runsPayload] = await Promise.all([
          getAttackSettings(),
          getLlmSettings(),
          listResultRuns(1, null),
        ]);

        if (!canceled) {
          setAttackSettings(attackPayload);
          setLlmSettings(llmPayload);
          setLatestRun(runsPayload.items[0] ?? null);
        }
      } catch (err) {
        if (!canceled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load overview";
          setError(message);
        }
      } finally {
        if (!canceled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      canceled = true;
    };
  }, []);

  const asrDelta = asNumber(latestRun?.delta?.asr);
  const ndcgDelta = asNumber(latestRun?.delta?.ndcg);
  const poisonFraction = attackSettings ? Math.max(0, Math.min(1, attackSettings.poison_fraction)) : null;

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Overview</h2>
          <p className="page-subtitle">High-level attack posture, run status, and quick access to core workflows.</p>
        </div>

        <div className="inline-actions">
          <Link className="btn btn-primary" to="/experiments">
            New experiment
          </Link>
          <Link className="btn" to="/results">
            Open results
          </Link>
        </div>
      </header>

      {loading ? <div className="loading-state">Loading overview…</div> : null}
      {error ? <div className="error-state">{error}</div> : null}

      {!loading && !error ? (
        <>
          <section className="metric-grid">
            <article className="metric-card">
              <p className="metric-label">Latest run</p>
              <p className="metric-value run-id">{latestRun?.label ?? "No runs"}</p>
            </article>
            <article className="metric-card">
              <p className="metric-label">Evaluated users</p>
              <p className="metric-value number">{formatNumber(latestRun?.evaluated_users)}</p>
            </article>
            <article className={["metric-card", asrCardTone(asrDelta)].join(" ")}>
              <p className="metric-label">Delta ASR</p>
              <p className={["metric-value", "number", asrCardTone(asrDelta)].join(" ")}>{formatMetric(latestRun?.delta?.asr)}</p>
            </article>
            <article className="metric-card">
              <p className="metric-label">Delta NDCG</p>
              <p className={["metric-value", "number", ndcgValueTone(ndcgDelta)].join(" ")}>{formatMetric(latestRun?.delta?.ndcg)}</p>
            </article>
          </section>

          <section className="split-grid">
            <article className="surface">
              <h3 className="section-title">Current attack configuration</h3>
              <p className="section-caption">Live attack settings used by indexing and evaluation workflows.</p>

              <div className="stack" style={{ marginTop: 16 }}>
                <div className="surface-elevated status-row">
                  <p className="card-title">Attack type</p>
                  <span className="badge attack mono">{attackSettings?.attack_type ?? "-"}</span>
                </div>
                <div className="surface-elevated status-row">
                  <p className="card-title">Target movie</p>
                  <span className="badge neutral mono">{formatNumber(attackSettings?.target_movie_id)}</span>
                </div>
                <div className="surface-elevated status-row">
                  <p className="card-title">Poison fraction</p>
                  <span className="poison-fraction">
                    <span className="mono">{attackSettings ? attackSettings.poison_fraction.toFixed(2) : "-"}</span>
                    <span className="poison-bar" aria-hidden="true">
                      <span className="poison-bar-fill" style={{ width: `${(poisonFraction ?? 0) * 100}%` }} />
                    </span>
                  </span>
                </div>
                <div className="surface-elevated">
                  <p className="text-meta">Keywords</p>
                  {attackSettings?.keyword_list.length ? (
                    <div className="keyword-pills" style={{ marginTop: 8 }}>
                      {attackSettings.keyword_list.map((keyword) => (
                        <span key={keyword} className="keyword-pill">
                          {keyword}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p style={{ marginTop: 8, fontSize: 14, color: "var(--text-secondary)" }}>-</p>
                  )}
                </div>
              </div>
            </article>

            <article className="surface">
              <h3 className="section-title">Current run profile state</h3>
              <p className="section-caption">Model/ranking settings and latest completed run snapshot.</p>

              <div className="stack" style={{ marginTop: 16 }}>
                <div className="surface-elevated status-row">
                  <p className="card-title">Victim model</p>
                  <span className="badge baseline mono">
                    {llmSettings ? `${llmSettings.victim.provider}:${llmSettings.victim.model}` : "-"}
                  </span>
                </div>
                <div className="surface-elevated status-row">
                  <p className="card-title">Attacker model</p>
                  <span className="badge attack mono">
                    {llmSettings ? `${llmSettings.attacker.provider}:${llmSettings.attacker.model}` : "-"}
                  </span>
                </div>
                <div className="surface-elevated status-row">
                  <p className="card-title">Ranking mode</p>
                  <span className="badge accent mono">
                    {llmSettings?.ranking_mode ?? "-"}
                  </span>
                </div>
                <div className="surface-elevated status-row">
                  <p className="card-title">Latest run time</p>
                  <span className="text-meta">{formatTimestamp(latestRun?.generated_at_utc)}</span>
                </div>
              </div>
            </article>
          </section>

          <section className="surface">
            <h3 className="section-title">Quick actions</h3>
            <p className="section-caption">Jump directly into experiment execution, user analysis, or run outcome review.</p>

            <div className="inline-actions" style={{ marginTop: 16 }}>
              <Link className="btn btn-primary" to="/experiments">
                Run experiment
              </Link>
              <Link className="btn" to="/users">
                Explore users
              </Link>
              <Link className="btn" to="/results">
                Latest results
              </Link>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
