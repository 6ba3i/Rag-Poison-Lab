import type { RankingMode } from "../api/types";

interface SettingsPanelProps {
  rankingMode: RankingMode;
  onRankingModeChange: (mode: RankingMode) => void;
}

export function SettingsPanel({ rankingMode, onRankingModeChange }: SettingsPanelProps): JSX.Element {
  return (
    <section className="panel p-4">
      <h3 className="text-base font-semibold text-slate-100">Ranking Mode</h3>
      <p
        className="mt-1 text-sm text-slate-400"
        title="LLM reranking allows the victim model to reorder results and may increase susceptibility to prompt injection attacks."
      >
        LLM reranking allows the victim model to reorder results and may increase susceptibility to prompt injection attacks.
      </p>

      <div className="mt-4 space-y-2">
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="radio"
            name="ranking-mode"
            value="deterministic"
            checked={rankingMode === "deterministic"}
            onChange={() => onRankingModeChange("deterministic")}
            className="h-4 w-4"
          />
          Deterministic
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="radio"
            name="ranking-mode"
            value="llm_rerank"
            checked={rankingMode === "llm_rerank"}
            onChange={() => onRankingModeChange("llm_rerank")}
            className="h-4 w-4"
          />
          LLM rerank (experimental)
        </label>
      </div>
    </section>
  );
}
