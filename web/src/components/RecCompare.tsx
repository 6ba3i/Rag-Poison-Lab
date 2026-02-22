import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";

import type { RecommendationItem, RecommendationMode } from "../api/types";

interface RecCompareProps {
  baseline: RecommendationItem[];
  attacked: RecommendationItem[];
  focusMode: RecommendationMode;
}

interface RecColumnProps {
  title: string;
  items: RecommendationItem[];
  otherIds: Set<number>;
  focused: boolean;
  columnKey: string;
}

function RecColumn({ title, items, otherIds, focused, columnKey }: RecColumnProps): JSX.Element {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  return (
    <section
      className={[
        "panel p-4 transition-colors duration-150",
        focused ? "border-slate-500" : "border-slate-700",
      ].join(" ")}
    >
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-300">{title}</h3>
      <div className="space-y-3">
        {items.map((item) => {
          const changed = !otherIds.has(item.movie_id);
          const rowKey = `${columnKey}-${item.movie_id}`;
          const isExpanded = expanded[rowKey] ?? false;

          return (
            <article
              key={rowKey}
              className={[
                "rounded-xl border bg-slate-900/60 p-3",
                changed ? "border-amber-500/70" : "border-slate-700",
              ].join(" ")}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h4 className="text-sm font-medium text-slate-100">{item.title}</h4>
                  <p className="mt-1 text-xs text-slate-400">{item.genres.join(", ") || "No genres"}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-400">Score</p>
                  <p className="text-sm font-semibold text-slate-200">{item.score.toFixed(3)}</p>
                </div>
              </div>

              {changed ? (
                <span className="mt-2 inline-block rounded-md border border-amber-500/70 px-2 py-1 text-xs text-amber-300">
                  Changed item
                </span>
              ) : null}

              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setExpanded((prev) => ({ ...prev, [rowKey]: !isExpanded }))}
                  className="rounded-md border border-slate-600 px-2 py-1 text-xs text-slate-300 transition-colors duration-150 hover:border-slate-500 hover:text-slate-100"
                >
                  {isExpanded ? "Hide explanation" : "Show explanation"}
                </button>
                <AnimatePresence initial={false}>
                  {isExpanded ? (
                    <motion.div
                      key="content"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2, ease: "easeOut" }}
                      className="overflow-hidden"
                    >
                      <p className="mt-2 text-xs leading-5 text-slate-300">{item.explanation}</p>
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

export function RecCompare({ baseline, attacked, focusMode }: RecCompareProps): JSX.Element {
  const baselineIds = useMemo(() => new Set(baseline.map((item) => item.movie_id)), [baseline]);
  const attackedIds = useMemo(() => new Set(attacked.map((item) => item.movie_id)), [attacked]);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <RecColumn
        title="Baseline"
        items={baseline}
        otherIds={attackedIds}
        focused={focusMode === "baseline"}
        columnKey="baseline"
      />
      <RecColumn
        title="Attacked"
        items={attacked}
        otherIds={baselineIds}
        focused={focusMode === "attacked"}
        columnKey="attacked"
      />
    </div>
  );
}
