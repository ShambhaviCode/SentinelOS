import { useCallback, useEffect, useState } from "react";
import type { Preset, SecurityEvent, Stats, Status } from "./api";
import { api } from "./api";
import Console from "./pages/Console";
import { Benchmarks, Overview, Policies, Threats } from "./pages/Pages";

const NAV = [
  { id: "overview", label: "Overview" },
  { id: "console", label: "Agent console" },
  { id: "threats", label: "Threats" },
  { id: "policies", label: "Policies" },
  { id: "benchmarks", label: "Benchmarks" },
];

function Mark() {
  return (
    <svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true">
      <path d="M16 2 4 7v8c0 7 5 12.5 12 15 7-2.5 12-8 12-15V7z" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="M16 9v14M10 16h12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function App() {
  const [page, setPage] = useState(() => location.hash.slice(1) || "overview");
  const [status, setStatus] = useState<Status | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [last, setLast] = useState<SecurityEvent | null>(null);
  const [offlineServer, setOfflineServer] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await api.events();
      setEvents(r.events);
      setStats(r.stats);
      setOfflineServer(false);
    } catch {
      setOfflineServer(true);
    }
  }, []);

  useEffect(() => {
    api.status().then(setStatus).catch(() => setOfflineServer(true));
    api.presets().then(setPresets).catch(() => undefined);
    refresh();
    const t = setInterval(() => {
      refresh();
      api.status().then(setStatus).catch(() => undefined);
    }, 8000);
    return () => clearInterval(t);
  }, [refresh]);

  const go = (p: string) => {
    setPage(p);
    history.replaceState(null, "", `#${p}`);
  };

  const ml = status?.ml;
  const accel = ml?.available ? (ml.accelerator?.startsWith("NPU") ? "NPU" : ml.accelerator) : null;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Mark />
          <div>
            <div className="brand-name">SentinelOS</div>
            <div className="brand-sub">Local AI security</div>
          </div>
        </div>
        <nav>
          {NAV.map((n) => (
            <button key={n.id} className={`nav-item${page === n.id ? " active" : ""}`} onClick={() => go(n.id)}
              aria-current={page === n.id ? "page" : undefined}>
              {n.label}
              {n.id === "threats" && stats && stats.pending_approval > 0 && <span className="nav-count">{stats.pending_approval}</span>}
            </button>
          ))}
        </nav>
        <p className="sidebar-foot">Synthetic demo data only.</p>
      </aside>

      <div className="main">
        <header className="topbar">
          <p className="topbar-title">Security boundary for AI agents</p>
          <div className="chips" aria-label="System status">
            <span className={`chip ${offlineServer ? "chip-bad" : "chip-ok"}`}>
              <i />{offlineServer ? "Server unreachable" : "Protected"}
            </span>
            <span className="chip chip-ok"><i />Local analysis</span>
            <span className={`chip ${ml?.available ? "chip-ok" : "chip-warn"}`}>
              <i />{ml?.available ? `Model on ${accel}` : "Rules only"}
            </span>
            <span className={`chip ${status?.network === "offline" ? "chip-ok" : "chip-neutral"}`}>
              <i />{status ? (status.network === "offline" ? "Offline" : "Online") : "Network…"}
            </span>
          </div>
        </header>

        <main>
          {page === "overview" && <Overview stats={stats} events={events} status={status} go={go} />}
          {page === "console" && <Console presets={presets} onAnalyzed={refresh} last={last} setLast={setLast} />}
          {page === "threats" && <Threats events={events} onChanged={refresh} />}
          {page === "policies" && <Policies />}
          {page === "benchmarks" && <Benchmarks status={status} />}
        </main>
      </div>
    </div>
  );
}
