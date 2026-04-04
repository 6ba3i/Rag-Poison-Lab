import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiError,
  getAttackSettings,
  getRecommendations,
  getResultRunDetail,
  listResultRuns,
  runExperiment,
} from "../api/client";
import type {
  AttackSettingsResponse,
  ExperimentRunRequest,
  ExperimentRunResponse,
  RecommendationItem,
  RunDetailResponse,
  RunSummary,
} from "../api/types";
import { formatMetric, formatTimestamp } from "../lib/format";
import { RecCompare } from "../components/RecCompare";
import { RunResultView } from "../components/results/RunResultView";

type ExperimentMode = "single" | "batch" | "full";
type RunProfile = "pipeline" | "single_demo";

export function Experiments(): JSX.Element {
  const [label, setLabel] = useState("");
  const [mode, setMode] = useState<ExperimentMode>("single");
  const [runProfile, setRunProfile] = useState<RunProfile>("single_demo");
  const [k, setK] = useState(10);
  const [userId, setUserId] = useState("");
  const [batchSize, setBatchSize] = useState(100);
  const [overwrite, setOverwrite] = useState(false);

  const [overrideStages, setOverrideStages] = useState(false);
  const [runPrepare, setRunPrepare] = useState(true);
  const [runIndex, setRunIndex] = useState(true);
  const [runEval, setRunEval] = useState(true);
  const [runReport, setRunReport] = useState(true);

  const [showAdvancedPaths, setShowAdvancedPaths] = useState(false);
  const [datasetDir, setDatasetDir] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [esUrl, setEsUrl] = useState("");
  const [attackConfigPath, setAttackConfigPath] = useState("");

  const [attackSettings, setAttackSettings] = useState<AttackSettingsResponse | null>(null);
  const [latestRun, setLatestRun] = useState<RunSummary | null>(null);
  const [latestRunDetail, setLatestRunDetail] = useState<RunDetailResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [result, setResult] = useState<ExperimentRunResponse | null>(null);

  const [liveBaselineRecs, setLiveBaselineRecs] = useState<RecommendationItem[]>([]);
  const [liveAttackedRecs, setLiveAttackedRecs] = useState<RecommendationItem[]>([]);
  const [liveRecLoading, setLiveRecLoading] = useState(false);
  const [liveRecError, setLiveRecError] = useState<string | null>(null);

  async function loadDetail(labelToLoad: string): Promise<void> {
    try {
      const detail = await getResultRunDetail(labelToLoad);
      setLatestRunDetail(detail);
    } catch {
      setLatestRunDetail(null);
    }
  }

  useEffect(() => {
    let canceled = false;

    async function load(): Promise<void> {
      try {
        const [attackPayload, runsPayload] = await Promise.all([getAttackSettings(), listResultRuns(1)]);
        if (canceled) {
          return;
        }
        const latest = runsPayload.items[0] ?? null;
        setAttackSettings(attackPayload);
        setLatestRun(latest);
        if (latest) {
          await loadDetail(latest.label);
        }
      } catch {
        if (!canceled) {
          setAttackSettings(null);
          setLatestRun(null);
          setLatestRunDetail(null);
        }
      }
    }

    void load();
    return () => {
      canceled = true;
    };
  }, []);

  useEffect(() => {
    if (mode === "single" && runProfile === "pipeline") {
      setRunProfile("single_demo");
    }
    if (mode !== "single" && runProfile === "single_demo") {
      setRunProfile("pipeline");
    }
  }, [mode, runProfile]);

  useEffect(() => {
    let canceled = false;

    async function loadLiveRecs(): Promise<void> {
      if (!latestRunDetail || latestRunDetail.summary.mode !== "single") {
        setLiveBaselineRecs([]);
        setLiveAttackedRecs([]);
        setLiveRecError(null);
        return;
      }

      const firstUser = latestRunDetail.per_user[0]?.user_id;
      if (typeof firstUser !== "number") {
        setLiveBaselineRecs([]);
        setLiveAttackedRecs([]);
        setLiveRecError("Live recommendation comparison unavailable: user id not present in run artifacts.");
        return;
      }

      const topK = latestRunDetail.summary.k ?? 10;
      setLiveRecLoading(true);
      setLiveRecError(null);

      try {
        const [baselinePayload, attackedPayload] = await Promise.all([
          getRecommendations(firstUser, "baseline", topK),
          getRecommendations(firstUser, "attacked", topK),
        ]);

        if (!canceled) {
          setLiveBaselineRecs(baselinePayload);
          setLiveAttackedRecs(attackedPayload);
        }
      } catch {
        if (!canceled) {
          setLiveBaselineRecs([]);
          setLiveAttackedRecs([]);
          setLiveRecError(
            "Live recommendation comparison is currently unavailable. Run-result artifacts are still complete.",
          );
        }
      } finally {
        if (!canceled) {
          setLiveRecLoading(false);
        }
      }
    }

    void loadLiveRecs();
    return () => {
      canceled = true;
    };
  }, [latestRunDetail]);

  async function handleRun(): Promise<void> {
    if (mode !== "single" && runProfile === "single_demo") {
      setRunStatus("single_demo profile is only valid for single mode.");
      return;
    }

    const parsedUserId = userId.trim() === "" ? null : Number(userId.trim());
    if (parsedUserId !== null && (!Number.isInteger(parsedUserId) || parsedUserId < 1)) {
      setRunStatus("User id must be a positive integer.");
      return;
    }

    setRunning(true);
    setRunStatus("Running orchestration workflow…");
    setResult(null);

    const payload: ExperimentRunRequest = {
      label: label.trim() === "" ? null : label.trim(),
      mode,
      run_profile: runProfile,
      k,
      user_id: mode === "single" ? parsedUserId : null,
      batch_size: mode === "batch" ? batchSize : 1,
      run_prepare: overrideStages ? runPrepare : null,
      run_index: overrideStages ? runIndex : null,
      run_eval: overrideStages ? runEval : null,
      run_report: overrideStages ? runReport : null,
      overwrite,
      dataset_dir: datasetDir.trim() === "" ? null : datasetDir.trim(),
      output_dir: outputDir.trim() === "" ? null : outputDir.trim(),
      es_url: esUrl.trim() === "" ? null : esUrl.trim(),
      attack_config: attackConfigPath.trim() === "" ? null : attackConfigPath.trim(),
    };

    try {
      const response = await runExperiment(payload);
      setResult(response);
      setRunStatus("Experiment workflow completed.");

      const runs = await listResultRuns(1);
      const latest = runs.items[0] ?? null;
      setLatestRun(latest);
      if (latest) {
        await loadDetail(latest.label);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Experiment run failed";
      setRunStatus(`Experiment run failed: ${message}`);
    } finally {
      setRunning(false);
    }
  }

  const liveRecVisible = useMemo(
    () => latestRunDetail?.summary.mode === "single",
    [latestRunDetail?.summary.mode],
  );

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Experiments</h2>
          <p className="page-subtitle">Configure and execute attack workflows from a dedicated experiment console.</p>
        </div>

        <div className="inline-actions">
          <Link className="btn" to="/results">
            View results
          </Link>
          <button type="button" className="btn btn-primary" onClick={() => void handleRun()} disabled={running}>
            {running ? "Running…" : "Run experiment"}
          </button>
        </div>
      </header>

      <section className="split-grid">
        <article className="surface stack">
          <div>
            <h3 className="section-title">Run configuration</h3>
            <p className="section-caption">Primary controls for orchestration mode, scope, and execution profile.</p>
          </div>

          <div className="form-grid">
            <label className="field">
              <span className="field-label">Run label</span>
              <input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="optional" className="input" />
            </label>

            <label className="field">
              <span className="field-label">Mode</span>
              <select value={mode} onChange={(event) => setMode(event.target.value as ExperimentMode)} className="select">
                <option value="single">single</option>
                <option value="batch">batch</option>
                <option value="full">full</option>
              </select>
            </label>

            <label className="field">
              <span className="field-label">Run profile</span>
              <select value={runProfile} onChange={(event) => setRunProfile(event.target.value as RunProfile)} className="select">
                <option value="single_demo" disabled={mode !== "single"}>
                  single_demo
                </option>
                <option value="pipeline">pipeline</option>
              </select>
            </label>

            <label className="field">
              <span className="field-label">K</span>
              <input
                type="number"
                min={1}
                max={100}
                value={k}
                onChange={(event) => setK(Number(event.target.value))}
                className="input"
              />
            </label>

            <label className="field">
              <span className="field-label">User ID (single mode)</span>
              <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="optional" className="input" />
            </label>

            <label className="field">
              <span className="field-label">Batch size</span>
              <input
                type="number"
                min={1}
                value={batchSize}
                onChange={(event) => setBatchSize(Number(event.target.value))}
                className="input"
                disabled={mode !== "batch"}
              />
            </label>
          </div>

          <label className="toggle-row">
            <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
            Allow overwrite for existing run label
          </label>

          <label className="toggle-row">
            <input type="checkbox" checked={overrideStages} onChange={(event) => setOverrideStages(event.target.checked)} />
            Override stage defaults
          </label>

          {overrideStages ? (
            <div className="inline-actions">
              <label className="toggle-row">
                <input type="checkbox" checked={runPrepare} onChange={(event) => setRunPrepare(event.target.checked)} /> run_prepare
              </label>
              <label className="toggle-row">
                <input type="checkbox" checked={runIndex} onChange={(event) => setRunIndex(event.target.checked)} /> run_index
              </label>
              <label className="toggle-row">
                <input type="checkbox" checked={runEval} onChange={(event) => setRunEval(event.target.checked)} /> run_eval
              </label>
              <label className="toggle-row">
                <input type="checkbox" checked={runReport} onChange={(event) => setRunReport(event.target.checked)} /> run_report
              </label>
            </div>
          ) : null}

          <label className="toggle-row">
            <input type="checkbox" checked={showAdvancedPaths} onChange={(event) => setShowAdvancedPaths(event.target.checked)} />
            Show path and infrastructure overrides
          </label>

          {showAdvancedPaths ? (
            <div className="form-grid">
              <label className="field">
                <span className="field-label">Dataset directory</span>
                <input className="input" value={datasetDir} onChange={(event) => setDatasetDir(event.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Output directory</span>
                <input className="input" value={outputDir} onChange={(event) => setOutputDir(event.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Elasticsearch URL</span>
                <input className="input" value={esUrl} onChange={(event) => setEsUrl(event.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Attack config path</span>
                <input className="input" value={attackConfigPath} onChange={(event) => setAttackConfigPath(event.target.value)} />
              </label>
            </div>
          ) : null}

          <div className="status-row">
            {runStatus ? (
              <p className="run-status-text">{runStatus}</p>
            ) : (
              <p className="run-ready">
                <span className="status-dot" />
                <span>Ready to execute</span>
              </p>
            )}
            <button type="button" className="btn btn-primary" onClick={() => void handleRun()} disabled={running}>
              {running ? "Running…" : "Run experiment"}
            </button>
          </div>
        </article>

        <aside className="stack">
          <article className="surface">
            <h3 className="section-title">Current attack state</h3>
            <p className="section-caption">Live attack config pulled from `/api/settings/attack`.</p>
            <div className="stack" style={{ marginTop: 12 }}>
              <div className="status-row">
                <span className="text-meta">Attack type</span>
                <span className="badge attack mono">{attackSettings?.attack_type ?? "-"}</span>
              </div>
              <div className="status-row">
                <span className="text-meta">Target movie</span>
                <span className="badge neutral mono">{attackSettings?.target_movie_id ?? "-"}</span>
              </div>
              <div>
                <p className="text-meta">Keywords</p>
                <p style={{ marginTop: 8, fontSize: 14 }}>{attackSettings?.keyword_list.join(", ") || "-"}</p>
              </div>
            </div>
          </article>

          <article className="surface">
            <h3 className="section-title">Latest run snapshot</h3>
            {latestRun ? (
              <div className="stack" style={{ marginTop: 12 }}>
                <div className="status-row">
                  <span className="text-meta">Label</span>
                  <span className="run-label-chip">{latestRun.label}</span>
                </div>
                <div className="status-row">
                  <span className="text-meta">Generated</span>
                  <span className="text-meta">{formatTimestamp(latestRun.generated_at_utc)}</span>
                </div>
                <div className="status-row">
                  <span className="text-meta">Delta ASR</span>
                  <span className="badge warning mono">{formatMetric(latestRun.delta.asr)}</span>
                </div>
                <div className="status-row">
                  <span className="text-meta">Delta NDCG</span>
                  <span className="badge attack mono">{formatMetric(latestRun.delta.ndcg)}</span>
                </div>
                <Link className="btn" to="/results">
                  Inspect in results
                </Link>
              </div>
            ) : (
              <p className="section-caption" style={{ marginTop: 10 }}>
                No run history available yet.
              </p>
            )}
          </article>
        </aside>
      </section>

      {latestRunDetail ? (
        <RunResultView
          detail={latestRunDetail}
          rawSections={result ? [{ title: "Experiment run response", payload: result }] : []}
        />
      ) : (
        <div className="empty-state">Run an experiment to see structured result visualization.</div>
      )}

      {liveRecVisible ? (
        <section className="surface">
          <h3 className="section-title">Single-user recommendation change (live snapshot)</h3>
          <p className="section-caption">
            Best-effort live comparison from current baseline and attacked recommendation endpoints.
          </p>

          {liveRecLoading ? <div className="loading-state" style={{ marginTop: 12 }}>Loading recommendations…</div> : null}
          {liveRecError ? <div className="error-state" style={{ marginTop: 12 }}>{liveRecError}</div> : null}

          {!liveRecLoading && !liveRecError && liveBaselineRecs.length > 0 && liveAttackedRecs.length > 0 ? (
            <div style={{ marginTop: 12 }}>
              <RecCompare baseline={liveBaselineRecs} attacked={liveAttackedRecs} />
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
