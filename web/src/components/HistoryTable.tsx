import type { UserHistoryItem } from "../api/types";

interface HistoryTableProps {
  items: UserHistoryItem[];
}

function formatDate(timestamp: number): string {
  return new Date(timestamp * 1000).toISOString().slice(0, 10);
}

export function HistoryTable({ items }: HistoryTableProps): JSX.Element {
  if (items.length === 0) {
    return <div className="empty-state">No rating history available for this user.</div>;
  }

  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Movie</th>
            <th>Genres</th>
            <th>Rating</th>
            <th>Split</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.movie_id}-${item.timestamp}`}>
              <td>{item.title}</td>
              <td className="text-meta">{item.genres.join(", ") || "-"}</td>
              <td>{item.rating.toFixed(1)}</td>
              <td>
                <span className="badge">{item.split ?? "n/a"}</span>
              </td>
              <td className="text-meta">{formatDate(item.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
