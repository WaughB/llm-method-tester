import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { HealthBadge } from "./components/HealthBadge";
import Dashboard from "./pages/Dashboard";
import NewRun from "./pages/NewRun";
import RunDetail from "./pages/RunDetail";
import Runs from "./pages/Runs";

const NAV = [
  { to: "/dashboard", label: "Dashboard", index: "01" },
  { to: "/new-run", label: "New run", index: "02" },
  { to: "/runs", label: "Runs", index: "03" },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-hairline flex flex-col justify-between sticky top-0 h-screen">
        <div>
          <div className="px-5 pt-6 pb-8 border-b border-hairline">
            <div className="section-tag mb-2">retrieval bench</div>
            <h1 className="font-mono font-semibold text-[15px] leading-tight tracking-tight">
              LLM·METHOD
              <br />
              TESTER
            </h1>
          </div>
          <nav className="px-2 py-4 space-y-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-baseline gap-3 px-3 py-2 rounded-sm text-sm transition-colors ${
                    isActive
                      ? "bg-raised text-ink border-l-2 border-s1"
                      : "text-sub hover:text-ink hover:bg-raised/60"
                  }`
                }
              >
                <span className="font-mono text-[10px] text-muted">{item.index}</span>
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="px-5 py-5 border-t border-hairline">
          <HealthBadge />
        </div>
      </aside>
      <main className="flex-1 min-w-0 px-8 py-8 max-w-[1400px]">
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/new-run" element={<NewRun />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
        </Routes>
      </main>
    </div>
  );
}
