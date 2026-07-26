import { useQuery } from "@tanstack/react-query";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import Chat from "./pages/Chat";
import Documents from "./pages/Documents";
import Eval from "./pages/Eval";
import Logs from "./pages/Logs";
import Settings from "./pages/Settings";

const NAV = [
  { to: "/chat", label: "Chat", index: "01" },
  { to: "/documents", label: "Documents", index: "02" },
  { to: "/eval", label: "Eval", index: "03" },
  { to: "/logs", label: "Logs", index: "04" },
  { to: "/settings", label: "Settings", index: "05" },
];

export function HealthFooter() {
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, refetchInterval: 15000 });
  const checks = meta.data?.checks ?? {};
  return (
    <div className="space-y-1.5">
      {Object.entries(checks).map(([name, check]) => (
        <div key={name} className="flex items-center gap-2 text-xs">
          <span
            className={`inline-block w-2 h-2 rounded-full ${check.ok ? "bg-good" : "bg-critical"}`}
          />
          <span className="text-sub">{name}</span>
          {!check.ok && <span className="text-critical font-mono text-[10px]">offline</span>}
        </div>
      ))}
      {meta.isLoading && <div className="text-xs text-muted animate-pulse">probing…</div>}
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-hairline flex flex-col justify-between sticky top-0 h-screen">
        <div>
          <div className="px-5 pt-6 pb-8 border-b border-hairline">
            <div className="section-tag mb-2">staged retrieval</div>
            <h1 className="font-mono font-semibold text-[15px] leading-tight tracking-tight">
              PAGEINDEX
              <br />
              TEST·BENCH
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
          <HealthFooter />
        </div>
      </aside>
      <main className="flex-1 min-w-0 px-8 py-8 max-w-[1500px]">
        <Routes>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/eval" element={<Eval />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
