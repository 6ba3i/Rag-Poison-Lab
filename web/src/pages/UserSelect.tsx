import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, listUsers } from "../api/client";
import type { UserSummary } from "../api/types";
import { UserCard } from "../components/UserCard";

const DEBOUNCE_MS = 250;

export function UserSelect(): JSX.Element {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    let canceled = false;

    async function run(): Promise<void> {
      setLoading(true);
      setError(null);
      try {
        const payload = await listUsers(debouncedQuery, 50);
        if (!canceled) {
          setUsers(payload);
        }
      } catch (err) {
        if (!canceled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load users";
          setError(message);
          setUsers([]);
        }
      } finally {
        if (!canceled) {
          setLoading(false);
        }
      }
    }

    void run();
    return () => {
      canceled = true;
    };
  }, [debouncedQuery]);

  return (
    <div className="space-y-4">
      <section className="panel p-4">
        <h2 className="text-lg font-semibold text-slate-100">Select User</h2>
        <p className="mt-1 text-sm text-slate-400">Search MovieLens users and open the dashboard.</p>

        <label className="mt-4 block">
          <span className="sr-only">Search users</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by user id"
            className="w-full rounded-xl border border-slate-600 bg-slate-900 px-4 py-2 text-slate-100 outline-none transition-colors duration-150 placeholder:text-slate-500 focus:border-slate-400"
          />
        </label>
      </section>

      {loading ? <div className="panel p-4 text-sm text-slate-400">Loading users...</div> : null}
      {error ? <div className="panel p-4 text-sm text-rose-300">{error}</div> : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {users.map((user) => (
          <UserCard key={user.user_id} user={user} onSelect={(userId) => navigate(`/users/${userId}`)} />
        ))}
      </div>
    </div>
  );
}
