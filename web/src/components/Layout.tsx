import { NavLink, Outlet } from "react-router-dom";

type ThemeMode = "dark" | "light";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview" },
  { to: "/experiments", label: "Experiments" },
  { to: "/users", label: "Users" },
  { to: "/results", label: "Results" },
  { to: "/matrix-results", label: "Matrix Results" },
  { to: "/settings", label: "Settings" },
] as const;

interface LayoutProps {
  theme: ThemeMode;
  onThemeChange: (theme: ThemeMode) => void;
}

function navLinkClass(isActive: boolean): string {
  return ["sidebar-link", isActive ? "active" : ""].join(" ").trim();
}

export function Layout({ theme, onThemeChange }: LayoutProps): JSX.Element {
  const runActive = false;

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="brand-stack">
          <div>
            <h1 className="brand-title">RAG Poison Lab</h1>
            <p className="brand-subtitle">Research console for baseline vs attacked behavior</p>
          </div>

          <div className="theme-panel">
            <p className="caps-label">Appearance</p>
            <div className="theme-toggle" role="group" aria-label="Appearance mode">
              <button
                type="button"
                className={["theme-toggle-option", theme === "dark" ? "active" : ""].join(" ").trim()}
                aria-pressed={theme === "dark"}
                onClick={() => onThemeChange("dark")}
              >
                Dark
              </button>
              <button
                type="button"
                className={["theme-toggle-option", theme === "light" ? "active" : ""].join(" ").trim()}
                aria-pressed={theme === "light"}
                onClick={() => onThemeChange("light")}
              >
                White
              </button>
            </div>
          </div>
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
