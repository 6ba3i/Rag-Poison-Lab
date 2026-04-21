import { useState } from "react";

import type { TraceResponse } from "../api/types";

interface TracePanelProps {
  baseline: TraceResponse | null;
  attacked: TraceResponse | null;
}

interface ColumnProps {
  label: string;
  tone: "baseline" | "attacked";
  trace: TraceResponse | null;
}

function TraceColumn({ label, tone, trace }: ColumnProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <section className={["comparison-column", tone].join(" ")}>
      <h3 className="card-title">{label}</h3>
      <p className="section-caption" style={{ marginTop: 6 }}>Retrieval query</p>
      <p style={{ margin: "6px 0 0", fontSize: 13 }}>{trace?.retrieval_query ?? "-"}</p>

      <div className="rec-list" style={{ marginTop: 14 }}>
        {(trace?.retrieved_docs ?? []).map((doc) => {
          const key = `${tone}-${doc.movie_id}`;
          const hasPoison = doc.has_poison || doc.poison_marker;
          const isExpanded = expanded[key] ?? false;

          return (
            <article key={key} className={["rec-item", hasPoison ? "changed" : ""].join(" ")}>
              <div className="rec-title-row">
                <p className="rec-title">{doc.title}</p>
                {hasPoison ? <span className="badge warning">Poison</span> : <span className="badge">Clean</span>}
              </div>

              <button
                type="button"
                className="btn btn-ghost"
                style={{ height: 30, fontSize: 12, marginTop: 8 }}
                onClick={() => setExpanded((current) => ({ ...current, [key]: !isExpanded }))}
              >
                {isExpanded ? "Hide details" : "Show details"}
              </button>

              {isExpanded ? (
                <>
                  <p className="rec-explanation">{doc.snippet}</p>
                  {hasPoison && doc.poison_payload ? (
                    <p className="rec-explanation rec-explanation-warning">
                      Payload: {doc.poison_payload}
                    </p>
                  ) : null}
                </>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function TracePanel({ baseline, attacked }: TracePanelProps): JSX.Element {
  return (
    <div className="comparison-grid">
      <TraceColumn label="Baseline Trace" tone="baseline" trace={baseline} />
      <TraceColumn label="Attacked Trace" tone="attacked" trace={attacked} />
    </div>
  );
}
