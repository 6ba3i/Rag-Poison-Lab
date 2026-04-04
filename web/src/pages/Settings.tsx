import { useEffect, useState } from "react";

import { ApiError, getLlmOptions, getLlmSettings, runExperiment, saveLlmSettings } from "../api/client";
import type {
  ExperimentRunResponse,
  LlmConfig,
  LlmProviderOption,
  LlmRoleConfig,
} from "../api/types";
import { LlmSelector } from "../components/LlmSelector";
import { SettingsPanel } from "../components/SettingsPanel";

export function Settings(): JSX.Element {
  const [providerOptions, setProviderOptions] = useState<LlmProviderOption[]>([]);
  const [draft, setDraft] = useState<LlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [experimentLabel, setExperimentLabel] = useState("");
  const [experimentMode, setExperimentMode] = useState<"single" | "batch" | "full">("single");
  const [experimentOverwrite, setExperimentOverwrite] = useState(false);
  const [experimentStatus, setExperimentStatus] = useState<string | null>(null);
  const [experimentResult, setExperimentResult] = useState<ExperimentRunResponse | null>(null);

  useEffect(() => {
    let canceled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError(null);

      try {
        const [optionsPayload, configPayload] = await Promise.all([getLlmOptions(), getLlmSettings()]);
        if (!canceled) {
          setProviderOptions(optionsPayload.providers);
          setDraft(configPayload);
        }
      } catch (err) {
        if (!canceled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load settings";
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

  function updateRole(role: "victim" | "attacker", value: LlmRoleConfig): void {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return { ...current, [role]: value };
    });
    setSaveStatus(null);
  }

  function updateRankingMode(rankingMode: LlmConfig["ranking_mode"]): void {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return { ...current, ranking_mode: rankingMode };
    });
    setSaveStatus(null);
  }

  async function onSave(): Promise<void> {
    if (!draft) {
      return;
    }

    setSaveStatus(null);
    try {
      const saved = await saveLlmSettings(draft);
      setDraft(saved);
      setSaveStatus("Saved settings.");
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Failed to save settings";
      setSaveStatus(`Save failed: ${message}`);
    }
  }

  async function onRunExperiment(): Promise<void> {
    setExperimentStatus("Running experiment workflow...");
    setExperimentResult(null);
    try {
      const response = await runExperiment({
        label: experimentLabel.trim() === "" ? null : experimentLabel.trim(),
        mode: experimentMode,
        run_profile: experimentMode === "single" ? "single_demo" : "pipeline",
        overwrite: experimentOverwrite,
      });
      setExperimentResult(response);
      setExperimentStatus("Experiment workflow completed.");
    } catch (err) {
      const message = err instanceof ApiError ? err.detail : "Experiment run failed";
      setExperimentStatus(`Experiment run failed: ${message}`);
    }
  }

  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <h2 className="text-lg font-semibold text-slate-100">LLM Settings</h2>
        <p className="mt-1 text-sm text-slate-400">Configure victim and attacker models without restarting the app.</p>
      </section>

      {loading ? <div className="panel p-4 text-sm text-slate-400">Loading settings...</div> : null}
      {error ? <div className="panel p-4 text-sm text-rose-300">{error}</div> : null}

      {!loading && !error && draft ? (
        <>
          <LlmSelector
            roleLabel="Victim LLM"
            value={draft.victim}
            providerOptions={providerOptions}
            onChange={(value) => updateRole("victim", value)}
          />
          <LlmSelector
            roleLabel="Attacker LLM"
            value={draft.attacker}
            providerOptions={providerOptions}
            onChange={(value) => updateRole("attacker", value)}
          />
          <SettingsPanel rankingMode={draft.ranking_mode} onRankingModeChange={updateRankingMode} />

          <section className="panel flex flex-wrap items-center justify-between gap-3 p-4">
            <p className="text-sm text-slate-400">Status: {saveStatus ?? "Unsaved changes"}</p>
            <button
              type="button"
              onClick={() => void onSave()}
              className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition-colors duration-150 hover:border-slate-500 hover:text-slate-100"
            >
              Save settings
            </button>
          </section>

          <section className="panel space-y-3 p-4">
            <h3 className="text-base font-semibold text-slate-100">Experiment Orchestration</h3>
            <p className="text-sm text-slate-400">
              Launch the full workflow through the canonical backend orchestrator (prepare, index, eval, report).
            </p>
            <label className="block text-sm text-slate-300">
              Run label
              <input
                type="text"
                value={experimentLabel}
                onChange={(event) => setExperimentLabel(event.target.value)}
                placeholder="optional"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 outline-none transition-colors duration-150 focus:border-slate-400"
              />
            </label>
            <label className="block text-sm text-slate-300">
              Mode
              <select
                value={experimentMode}
                onChange={(event) => setExperimentMode(event.target.value as "single" | "batch" | "full")}
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-slate-100 outline-none transition-colors duration-150 focus:border-slate-400"
              >
                <option value="single">single</option>
                <option value="batch">batch</option>
                <option value="full">full</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-300">
              <input
                type="checkbox"
                checked={experimentOverwrite}
                onChange={(event) => setExperimentOverwrite(event.target.checked)}
                className="h-4 w-4"
              />
              Allow overwrite if label already exists
            </label>
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm text-slate-400">{experimentStatus ?? "Ready to run."}</p>
              <button
                type="button"
                onClick={() => void onRunExperiment()}
                className="rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-200 transition-colors duration-150 hover:border-slate-500 hover:text-slate-100"
              >
                Run experiment
              </button>
            </div>
            {experimentResult ? (
              <pre className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-950/50 p-3 text-xs text-slate-300">
                {JSON.stringify(experimentResult, null, 2)}
              </pre>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
