import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, getUserProfile, listUsers } from "../api/client";
import type { UserProfile, UserSummary } from "../api/types";

const DEBOUNCE_MS = 220;

type SortMode = "user_id" | "rating_count" | "mean_rating";

function sortUsers(users: UserSummary[], mode: SortMode): UserSummary[] {
  const next = [...users];
  if (mode === "user_id") {
    return next.sort((a, b) => a.user_id - b.user_id);
  }
  if (mode === "rating_count") {
    return next.sort((a, b) => b.rating_count - a.rating_count || a.user_id - b.user_id);
  }
  return next.sort((a, b) => b.mean_rating - a.mean_rating || a.user_id - b.user_id);
}

export function Users(): JSX.Element {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("rating_count");
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [previewProfile, setPreviewProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    let canceled = false;

    async function loadUsers(): Promise<void> {
      setLoading(true);
      setError(null);

      try {
        const payload = await listUsers(debouncedQuery, 200);
        if (!canceled) {
          setUsers(payload);
          setSelectedUserId((current) => {
            if (current && payload.some((item) => item.user_id === current)) {
              return current;
            }
            return payload.length > 0 ? payload[0].user_id : null;
          });
        }
      } catch (err) {
        if (!canceled) {
          const message = err instanceof ApiError ? err.detail : "Failed to load users";
          setError(message);
          setUsers([]);
          setSelectedUserId(null);
        }
      } finally {
        if (!canceled) {
          setLoading(false);
        }
      }
    }

    void loadUsers();
    return () => {
      canceled = true;
    };
  }, [debouncedQuery]);

  useEffect(() => {
    let canceled = false;

    async function loadProfile(): Promise<void> {
      if (!selectedUserId) {
        setPreviewProfile(null);
        return;
      }

      try {
        const payload = await getUserProfile(selectedUserId);
        if (!canceled) {
          setPreviewProfile(payload);
        }
      } catch {
        if (!canceled) {
          setPreviewProfile(null);
        }
      }
    }

    void loadProfile();
    return () => {
      canceled = true;
    };
  }, [selectedUserId]);

  const orderedUsers = useMemo(() => sortUsers(users, sortMode), [users, sortMode]);

  return (
    <div className="page-wrap">
      <header className="page-header">
        <div>
          <h2 className="page-title">Users</h2>
          <p className="page-subtitle">Scan, rank, and select users quickly before opening baseline vs attacked analysis.</p>
        </div>
      </header>

      <section className="surface">
        <div className="status-row">
          <div className="inline-actions" style={{ flex: 1 }}>
            <label className="field" style={{ minWidth: 280, flex: 1 }}>
              <span className="field-label">Search user id</span>
              <div className="search-field">
                <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m20 20-3.5-3.5" />
                </svg>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search by user id"
                  className="input search-input"
                />
              </div>
            </label>
            <label className="field" style={{ minWidth: 220 }}>
              <span className="field-label">Sort</span>
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className="select">
                <option value="rating_count">Most ratings</option>
                <option value="mean_rating">Highest mean rating</option>
                <option value="user_id">User id</option>
              </select>
            </label>
          </div>
          <span className="badge">{orderedUsers.length} users</span>
        </div>

        {loading ? <div className="loading-state" style={{ marginTop: 16 }}>Loading users…</div> : null}
        {error ? <div className="error-state" style={{ marginTop: 16 }}>{error}</div> : null}

        {!loading && !error ? (
          <div className="split-grid" style={{ marginTop: 16 }}>
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Ratings</th>
                    <th>Mean rating</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {orderedUsers.map((user) => (
                    <tr
                      key={user.user_id}
                      className={user.user_id === selectedUserId ? "is-selected" : ""}
                      onClick={() => setSelectedUserId(user.user_id)}
                    >
                      <td>#{user.user_id}</td>
                      <td>{user.rating_count}</td>
                      <td>{user.mean_rating.toFixed(2)}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={(event) => {
                            event.stopPropagation();
                            navigate(`/users/${user.user_id}`);
                          }}
                        >
                          Open analysis
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <aside className="surface-elevated">
              <h3 className="card-title">User preview</h3>
              {selectedUserId ? <p className="section-caption">Selected user #{selectedUserId}</p> : <p className="section-caption">Select a user.</p>}

              <div className="user-preview-values" style={{ marginTop: 14 }}>
                <div>
                  <p className="user-preview-stat-label">Ratings</p>
                  <p className="user-preview-stat-value">{previewProfile?.rating_count ?? "-"}</p>
                </div>
                <div>
                  <p className="user-preview-stat-label">Mean rating</p>
                  <p className="user-preview-stat-value">{previewProfile ? previewProfile.mean_rating.toFixed(2) : "-"}</p>
                </div>
                <div>
                  <p className="user-preview-stat-label">Top genres</p>
                  {previewProfile?.top_genres.length ? (
                    <div className="genre-pills" style={{ marginTop: 8 }}>
                      {previewProfile.top_genres.map((item) => (
                        <span key={item.genre} className="genre-pill">
                          {item.genre} &middot; {item.count}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p style={{ marginTop: 8, fontSize: 14, color: "var(--text-secondary)" }}>-</p>
                  )}
                </div>

                <button
                  type="button"
                  className="btn btn-primary btn-full"
                  disabled={!selectedUserId}
                  onClick={() => selectedUserId && navigate(`/users/${selectedUserId}`)}
                >
                  Open comparison view
                </button>
              </div>
            </aside>
          </div>
        ) : null}
      </section>
    </div>
  );
}
