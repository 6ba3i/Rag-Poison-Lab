import { useEffect, useState } from "react";

import { ApiError, getLlmOptions, getLlmSettings, saveLlmSettings } from "../api/client";
import type { LlmConfig, LlmProviderOption, LlmRoleConfig } from "../api/types";
import { LlmSelector } from "../components/LlmSelector";
import { SettingsPanel } from "../components/SettingsPanel";

export function Settings(): JSX.Element {
  const [providerOptions, setProviderOptions] = useState<LlmProviderOption[]>([]);
  const [draft, setDraft] = useState<LlmConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);

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
        </>
      ) : null}
    </div>
  );
}
