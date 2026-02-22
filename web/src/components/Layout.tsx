import { AnimatePresence, motion } from "framer-motion";
import { NavLink, Outlet, useLocation } from "react-router-dom";

function navClass(isActive: boolean): string {
  return [
    "rounded-xl border px-3 py-2 text-sm transition-colors duration-150",
    isActive
      ? "border-slate-500 bg-slate-700/40 text-slate-100"
      : "border-slate-700 bg-slate-900/40 text-slate-300 hover:border-slate-500 hover:text-slate-100",
  ].join(" ");
}

export function Layout(): JSX.Element {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="panel flex items-center justify-between px-5 py-4">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">RAGPoison UI</h1>
            <p className="text-xs text-slate-400">MovieLens RAG poisoning defense demo</p>
          </div>
          <nav className="flex items-center gap-2">
            <NavLink to="/" className={({ isActive }) => navClass(isActive)}>
              Users
            </NavLink>
            <NavLink to="/settings" className={({ isActive }) => navClass(isActive)}>
              Settings
            </NavLink>
          </nav>
        </header>

        <AnimatePresence mode="wait" initial={false}>
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="pb-4"
          >
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>
    </div>
  );
}
