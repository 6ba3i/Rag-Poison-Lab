import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import type { RecommendationMode, TraceResponse } from "../api/types";

interface TracePanelProps {
  baseline: TraceResponse | null;
  attacked: TraceResponse | null;
  focusMode: RecommendationMode;
}

interface TraceColumnProps {
  label: string;
  trace: TraceResponse | null;
  focused: boolean;
  columnKey: string;
}

function TraceColumn({ label, trace, focused, columnKey }: TraceColumnProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <section
      className={[
        "panel p-4 transition-colors duration-150",
        focused ? "border-slate-500" : "border-slate-700",
      ].join(" ")}
    >
      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">{label}</h3>

      <div className="mt-3 rounded-lg border border-slate-700 bg-slate-900/60 p-3">
        <p className="text-xs uppercase tracking-wide text-slate-500">Retrieval query</p>
        <p className="mt-1 text-sm text-slate-200">{trace?.retrieval_query ?? "-"}</p>
      </div>

      <div className="mt-3 space-y-3">
        {(trace?.retrieved_docs ?? []).map((doc) => {
          const rowKey = `${columnKey}-${doc.movie_id}`;
          const isExpanded = expanded[rowKey] ?? false;
          const hasPoison = doc.has_poison || doc.poison_marker;

          return (
            <article
              key={rowKey}
              className={[
                "rounded-xl border bg-slate-900/60 p-3",
                hasPoison ? "border-rose-500/70" : "border-slate-700",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <h4 className="text-sm font-medium text-slate-100">{doc.title}</h4>
                {hasPoison ? (
                  <span className="rounded-md border border-rose-500/70 px-2 py-1 text-xs text-rose-300">Poison</span>
                ) : null}
              </div>

              <div className="mt-2">
                <button
                  type="button"
                  onClick={() => setExpanded((prev) => ({ ...prev, [rowKey]: !isExpanded }))}
                  className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-300 transition-colors duration-150 hover:border-slate-500 hover:text-slate-100"
                >
                  {isExpanded ? "Hide details" : "Show details"}
                </button>
                <AnimatePresence initial={false}>
                  {isExpanded ? (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeOut" }}
                      className="overflow-hidden"
                    >
                      <p className="mt-2 text-xs leading-5 text-slate-300">{doc.snippet}</p>
                      {hasPoison && doc.poison_payload ? (
                        <p className="mt-2 rounded-md border border-rose-500/50 bg-rose-950/20 p-2 text-xs text-rose-200">
                          Payload: {doc.poison_payload}
                        </p>
                      ) : null}
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function TracePanel({ baseline, attacked, focusMode }: TracePanelProps): JSX.Element {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <TraceColumn label="Baseline" trace={baseline} focused={focusMode === "baseline"} columnKey="baseline" />
      <TraceColumn label="Attacked" trace={attacked} focused={focusMode === "attacked"} columnKey="attacked" />
    </div>
  );
}
