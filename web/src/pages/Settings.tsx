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
          setDraft(null);
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

  function updateRetrievalMode(retrievalMode: LlmConfig["retrieval_mode"]): void {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      return { ...current, retrieval_mode: retrievalMode };
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

  const saveFailed = Boolean(saveStatus && saveStatus.startsWith("Save failed"));
  const isSaved = saveStatus === "Saved settings.";
  const statusText = saveStatus ?? "Unsaved changes";
  const statusClass = saveFailed ? "failed" : isSaved ? "saved" : "unsaved";
  const statusDotClass = saveFailed ? "attack" : isSaved ? "success" : "warning";

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Settings</h2>
          <p className="page-subtitle">System model and ranking configuration. Experiment orchestration lives under Experiments.</p>
        </div>
      </header>

      {loading ? <div className="loading-state">Loading settings…</div> : null}
      {error ? <div className="error-state">{error}</div> : null}

      {!loading && !error && draft ? (
        <>
          <LlmSelector
            roleLabel="Victim model"
            value={draft.victim}
            providerOptions={providerOptions}
            onChange={(value) => updateRole("victim", value)}
          />

          <LlmSelector
            roleLabel="Attacker model"
            value={draft.attacker}
            providerOptions={providerOptions}
            onChange={(value) => updateRole("attacker", value)}
          />

          <SettingsPanel
            rankingMode={draft.ranking_mode}
            retrievalMode={draft.retrieval_mode}
            onRankingModeChange={updateRankingMode}
            onRetrievalModeChange={updateRetrievalMode}
          />

          <section className="surface">
            <div className="status-row">
              <p className={["settings-status", statusClass].join(" ")}>
                <span className={["status-dot", statusDotClass].join(" ")} />
                <span>{statusText}</span>
              </p>
              <button type="button" onClick={() => void onSave()} className="btn btn-primary">
                Save settings
              </button>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
