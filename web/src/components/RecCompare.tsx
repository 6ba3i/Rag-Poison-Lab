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
        <h3 className="card-title">{label}</h3>
        <span className={["badge", tone === "baseline" ? "primary" : "warning"].join(" ")}>{items.length} items</span>
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
                  <p className="rec-title">
                    #{index + 1} {item.title}
                  </p>
                  <p className="rec-meta">{item.genres.join(", ") || "No genres"}</p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p className="text-meta">Score</p>
                  <p style={{ margin: "4px 0 0", fontSize: 14, fontWeight: 600 }}>{item.score.toFixed(3)}</p>
                </div>
              </div>

              <div className="inline-actions" style={{ marginTop: 10 }}>
                {changed ? <span className="badge warning">Changed</span> : <span className="badge">Shared</span>}
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ height: 30, fontSize: 12 }}
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
