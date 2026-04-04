import { NavLink, Outlet } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview" },
  { to: "/experiments", label: "Experiments" },
  { to: "/users", label: "Users" },
  { to: "/results", label: "Results" },
  { to: "/settings", label: "Settings" },
] as const;

function navLinkClass(isActive: boolean): string {
  return ["sidebar-link", isActive ? "active" : ""].join(" ").trim();
}

export function Layout(): JSX.Element {
  const runActive = false;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div>
          <h1 className="brand-title">RAG Poison Lab</h1>
          <p className="brand-subtitle">Research console for baseline vs attacked behavior</p>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => navLinkClass(isActive)}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-status" role="status" aria-live="polite">
          <span className={["status-dot", runActive ? "live" : ""].join(" ").trim()} />
          <span className={["sidebar-status-label", runActive ? "live" : ""].join(" ").trim()}>
            {runActive ? "Run active" : "Idle"}
          </span>
        </div>
      </aside>

      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
