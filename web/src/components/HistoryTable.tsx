import type { UserHistoryItem } from "../api/types";

interface HistoryTableProps {
  items: UserHistoryItem[];
}

function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toISOString().slice(0, 10);
}

export function HistoryTable({ items }: HistoryTableProps): JSX.Element {
  if (items.length === 0) {
    return <div className="panel p-4 text-sm text-slate-400">No history available for this user.</div>;
  }

  return (
    <div className="panel overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-800 text-sm">
        <thead className="bg-slate-900/70 text-left text-slate-400">
          <tr>
            <th className="px-4 py-3">Movie</th>
            <th className="px-4 py-3">Genres</th>
            <th className="px-4 py-3">Rating</th>
            <th className="px-4 py-3">Split</th>
            <th className="px-4 py-3">Date</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 text-slate-200">
          {items.map((item) => (
            <tr key={`${item.movie_id}-${item.timestamp}`} className="hover:bg-slate-900/40">
              <td className="px-4 py-3">{item.title}</td>
              <td className="px-4 py-3 text-slate-400">{item.genres.join(", ") || "-"}</td>
              <td className="px-4 py-3">{item.rating.toFixed(1)}</td>
              <td className="px-4 py-3">
                <span className="rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-xs uppercase tracking-wide text-slate-300">
                  {item.split ?? "n/a"}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-400">{formatDate(item.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
