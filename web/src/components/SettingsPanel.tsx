import type { RankingMode, RetrievalMode } from "../api/types";

interface SettingsPanelProps {
  rankingMode: RankingMode;
  retrievalMode: RetrievalMode;
  onRankingModeChange: (mode: RankingMode) => void;
  onRetrievalModeChange: (mode: RetrievalMode) => void;
}

export function SettingsPanel({
  rankingMode,
  retrievalMode,
  onRankingModeChange,
  onRetrievalModeChange,
}: SettingsPanelProps): JSX.Element {
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

      <h3 className="card-title" style={{ marginTop: 20 }}>Retrieval mode</h3>
      <p className="section-caption">
        Lexical keeps the current BM25 path; dense uses the local hashed-vector corpus; hybrid fuses both rankings.
      </p>

      <div className="stack" style={{ marginTop: 16 }}>
        {(["lexical", "dense", "hybrid"] as const).map((mode) => (
          <label key={mode} className={["ranking-option", retrievalMode === mode ? "selected" : ""].join(" ")}>
            <input
              type="radio"
              name="retrieval-mode"
              value={mode}
              checked={retrievalMode === mode}
              onChange={() => onRetrievalModeChange(mode)}
              className="ranking-option-input"
            />
            <span className="ranking-radio" aria-hidden="true" />
            {mode}
          </label>
        ))}
      </div>
    </section>
  );
}
