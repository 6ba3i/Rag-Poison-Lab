import type { UserSummary } from "../api/types";

interface UserCardProps {
  user: UserSummary;
  onSelect: (userId: number) => void;
}

export function UserCard({ user, onSelect }: UserCardProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={() => onSelect(user.user_id)}
      className="panel w-full p-4 text-left transition-colors duration-150 hover:border-slate-500 hover:bg-slate-800/80"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-100">User {user.user_id}</h3>
        <span className="rounded-lg border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-300">
          {user.rating_count} ratings
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-400">Mean rating: {user.mean_rating.toFixed(2)}</p>
    </button>
  );
}
