import { useMemo, useState } from "react";

import type { RecommendationItem } from "../api/types";

interface RecCompareProps {
  baseline: RecommendationItem[];
  attacked: RecommendationItem[];
}

interface ColumnProps {
  label: string;
  tone: "baseline" | "attacked";
  items: RecommendationItem[];
  otherIds: Set<number>;
}

function RecColumn({ label, tone, items, otherIds }: ColumnProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <section className={["comparison-column", tone].join(" ")}>
      <div className="status-row">
        <h3 className={["rec-column-header", tone].join(" ")}>{label}</h3>
        <span className={["badge", "mono", tone === "baseline" ? "baseline" : "attack"].join(" ")}>{items.length} items</span>
      </div>

      <div className="rec-list" style={{ marginTop: 12 }}>
        {items.map((item, index) => {
          const changed = !otherIds.has(item.movie_id);
          const key = `${tone}-${item.movie_id}`;
          const isExpanded = expanded[key] ?? false;

          return (
            <article key={key} className={["rec-item", changed ? "changed" : ""].join(" ")}>
              <div className="rec-title-row">
                <div>
                  <p className="rank-label">#{index + 1}</p>
                  <p className="rec-title">{item.title}</p>
                  <p className="rec-meta">{item.genres.join(", ") || "No genres"}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p className="rec-score-label">Score</p>
                  <p className="rec-score-value">{item.score.toFixed(3)}</p>
                </div>
              </div>

              <div className="inline-actions" style={{ marginTop: 10 }}>
                {changed ? <span className="badge warning mono">Changed</span> : <span className="badge neutral mono">Shared</span>}
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setExpanded((current) => ({ ...current, [key]: !isExpanded }))}
                >
                  {isExpanded ? "Hide explanation" : "Show explanation"}
                </button>
              </div>

              {isExpanded ? <p className="rec-explanation">{item.explanation}</p> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function RecCompare({ baseline, attacked }: RecCompareProps): JSX.Element {
  const baselineIds = useMemo(() => new Set(baseline.map((item) => item.movie_id)), [baseline]);
  const attackedIds = useMemo(() => new Set(attacked.map((item) => item.movie_id)), [attacked]);

  return (
    <div className="comparison-grid">
      <RecColumn label="Baseline" tone="baseline" items={baseline} otherIds={attackedIds} />
      <RecColumn label="Attacked" tone="attacked" items={attacked} otherIds={baselineIds} />
    </div>
  );
}
