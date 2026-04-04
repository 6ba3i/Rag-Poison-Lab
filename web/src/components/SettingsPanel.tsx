import type { RankingMode } from "../api/types";

interface SettingsPanelProps {
  rankingMode: RankingMode;
  onRankingModeChange: (mode: RankingMode) => void;
}

export function SettingsPanel({ rankingMode, onRankingModeChange }: SettingsPanelProps): JSX.Element {
  return (
    <section className="surface settings-section settings-section-accent">
      <h3 className="card-title">Ranking mode</h3>
      <p className="section-caption">
        LLM reranking allows the victim model to reorder retrieval candidates and can increase prompt injection exposure.
      </p>

      <div className="stack" style={{ marginTop: 16 }}>
        <label className={["ranking-option", rankingMode === "deterministic" ? "selected" : ""].join(" ")}>
          <input
            type="radio"
            name="ranking-mode"
            value="deterministic"
            checked={rankingMode === "deterministic"}
            onChange={() => onRankingModeChange("deterministic")}
            className="ranking-option-input"
          />
          <span className="ranking-radio" aria-hidden="true" />
          Deterministic
        </label>

        <label className={["ranking-option", rankingMode === "llm_rerank" ? "selected" : ""].join(" ")}>
          <input
            type="radio"
            name="ranking-mode"
            value="llm_rerank"
            checked={rankingMode === "llm_rerank"}
            onChange={() => onRankingModeChange("llm_rerank")}
            className="ranking-option-input"
          />
          <span className="ranking-radio" aria-hidden="true" />
          LLM rerank
        </label>
      </div>
    </section>
  );
}
