import { useEffect, useState } from "react";
import type { Benchmark, BenchStats, SecurityEvent, Stats, Status } from "../api";
import { api } from "../api";
import ThreatDetail from "../components/ThreatDetail";
import TrustGraph from "../components/TrustGraph";
import { EventTable, KV, Panel } from "../components/ui";

const ND = <span className="muted">Not detected</span>;

/* ------------------------------------------------------------------ Local AI */
export function LocalAIStatus({ status, compact = false }: { status: Status | null; compact?: boolean }) {
  if (!status) return <p className="muted">Reading local runtime…</p>;
  const ml = status.ml;
  const npu = status.npu_verification;
  return (
    <dl className={`kvs${compact ? " compact" : ""}`}>
      <KV k="Model" v={ml.available ? ml.model : <span className="warn-text">ML classifier unavailable</span>} />
      <KV k="Runtime" v={ml.runtime ? `${ml.runtime} ${ml.runtime_version ?? ""}` : ND} />
      <KV k="Execution provider" v={ml.provider ?? ND} mono />
      <KV k="Accelerator" v={ml.accelerator ?? ND} />
      <KV k="Model load time" v={ml.load_time_ms != null ? `${ml.load_time_ms} ms` : ND} />
      {!compact && <KV k="CPU fallback" v={ml.available ? (ml.cpu_fallback_disabled ? "Disabled (whole graph on QNN)" : "Allowed") : ND} />}
      <KV k="NPU verification" v={npu ? npu.verdict : <span className="muted">Not run yet (tools/verify_npu.py)</span>} />
      <KV k="Processor" v={status.machine.processor} />
      {!compact && <KV k="Python" v={`${status.machine.python} (${status.machine.python_arch})`} />}
      {!compact && <KV k="Available providers" v={status.machine.available_providers.join(", ") || ND} mono />}
      <KV k="Network" v={status.network === "offline" ? "Offline" : "Online (analysis stays local)"} />
      {!ml.available && ml.errors.length > 0 && !compact && <KV k="Why unavailable" v={ml.errors.join(" ")} />}
    </dl>
  );
}

/* ------------------------------------------------------------------ Overview */
export function Overview({ stats, events, status, go }: {
  stats: Stats | null;
  events: SecurityEvent[];
  status: Status | null;
  go: (page: string) => void;
}) {
  const s = stats ?? { events: 0, blocked: 0, pending_approval: 0, allowed: 0, tool_requests: 0, approval_required: 0, prompt_injection: 0, data_events: 0 };
  const latest = events[0] ?? null;
  return (
    <div className="page overview">
      <div className="page-intro">
        <h1>Overview</h1>
        <p className="muted">Every request the agent makes this session, and what the boundary decided.</p>
      </div>
      <div className="stat-strip">
        <div className="stat"><span className="stat-n">{s.events}</span><span className="stat-l">Requests checked</span></div>
        <div className="stat stat-block"><span className="stat-n">{s.blocked}</span><span className="stat-l">Blocked</span></div>
        <div className="stat stat-review"><span className="stat-n">{s.pending_approval}</span><span className="stat-l">Waiting for approval</span></div>
        <div className="stat stat-allow"><span className="stat-n">{s.allowed}</span><span className="stat-l">Allowed</span></div>
        <div className="stat"><span className="stat-n">{s.tool_requests}</span><span className="stat-l">Tool requests</span></div>
      </div>
      <div className="overview-grid">
        <Panel title="Recent activity" aside={<button className="link" onClick={() => go("threats")}>Open threats</button>}>
          <EventTable events={events.slice(0, 8)} empty={
            <>
              <p>No requests checked yet.</p>
              <button className="btn btn-primary" onClick={() => go("console")}>Open the agent console</button>
            </>
          } />
        </Panel>
        <Panel title="Local AI">
          <LocalAIStatus status={status} compact />
        </Panel>
      </div>
      {latest && (
        <Panel title="Latest request through the boundary">
          <TrustGraph event={latest} />
        </Panel>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- Threats */
export function Threats({ events, onChanged }: { events: SecurityEvent[]; onChanged: () => void }) {
  const threats = events.filter((e) => e.decision.decision !== "ALLOW");
  const [sel, setSel] = useState<SecurityEvent | null>(null);
  const current = sel ? events.find((e) => e.id === sel.id) ?? sel : threats[0] ?? null;
  return (
    <div className="page threats">
      <div className="page-intro">
        <h1>Threats</h1>
        <p className="muted">Requests that were blocked or held for approval.</p>
      </div>
      <div className="threats-grid">
        <Panel title={`${threats.length} finding${threats.length === 1 ? "" : "s"}`}>
          <EventTable events={threats} selectedId={current?.id} onSelect={setSel}
            empty={<p>No threats this session. Load the prompt injection scenario in the agent console to see one.</p>} />
        </Panel>
        {current && (
          <div className="stack">
            <ThreatDetail ev={current} onResolve={async (a) => { setSel(await api.resolve(current.id, a)); onChanged(); }} />
            <Panel title="Agent trust graph"><TrustGraph event={current} /></Panel>
          </div>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ Policies */
const EFFECT_CLASS: Record<string, string> = { ALLOW: "allow", REQUIRE_APPROVAL: "review", BLOCK: "block" };
function Effect({ e }: { e: string }) {
  return <span className={`badge badge-${EFFECT_CLASS[e] ?? "review"}`}>{e === "REQUIRE_APPROVAL" ? "Needs approval" : e === "ALLOW" ? "Allow" : "Block"}</span>;
}

export function Policies() {
  const [p, setP] = useState<Record<string, any> | null>(null);
  useEffect(() => { api.policies().then(setP).catch(() => setP(null)); }, []);
  if (!p) return <div className="page"><p className="muted">Loading policies…</p></div>;
  const fa = p.file_access, risk = p.risk;
  return (
    <div className="page policies">
      <div className="page-intro">
        <h1>Policies</h1>
        <p className="muted">
          Loaded from <code>config/policies.json</code>. Edit the file and restart the server to change them. Policies can only make a
          decision stricter.
        </p>
      </div>
      <div className="policy-grid">
        <Panel title="File access">
          <table className="plain">
            <tbody>
              {Object.entries(fa.scope_effects).map(([k, v]) => (
                <tr key={k}><td>Scope: {k}</td><td><Effect e={v as string} /></td></tr>
              ))}
              <tr><td>File outside the workspace</td><td><Effect e={fa.outside_workspace_effect} /></td></tr>
              <tr><td>Sensitive locations ({fa.sensitive_path_markers.length} markers)</td><td><Effect e="BLOCK" /></td></tr>
              <tr><td>Write or move</td><td><Effect e={fa.write_effect} /></td></tr>
              <tr><td>Delete</td><td><Effect e={fa.delete_effect} /></td></tr>
            </tbody>
          </table>
          <p className="muted small">Workspace: <span className="mono">{fa.workspace_roots.join(", ")}</span></p>
        </Panel>
        <Panel title="Network and email">
          <table className="plain">
            <tbody>
              <tr><td>Allowlisted destination</td><td><Effect e="ALLOW" /></td></tr>
              <tr><td>Unknown destination</td><td><Effect e={p.network.unknown_destination_effect} /></td></tr>
              <tr><td>External email recipient</td><td><Effect e={p.email.external_effect} /></td></tr>
              <tr><td>Secrets leaving the device</td><td><Effect e="BLOCK" /></td></tr>
            </tbody>
          </table>
          <p className="muted small">Allowlist: <span className="mono">{p.network.allowed_domains.join(", ")}</span></p>
        </Panel>
        <Panel title="Command execution">
          <table className="plain">
            <tbody>
              <tr><td>Any command</td><td><Effect e={p.command_execution.default_effect} /></td></tr>
              <tr><td>Blocked patterns ({p.command_execution.blocked_patterns.length})</td><td><Effect e="BLOCK" /></td></tr>
            </tbody>
          </table>
          <p className="muted small mono">{p.command_execution.blocked_patterns.join("   ")}</p>
        </Panel>
        <Panel title="Risk levels">
          <table className="plain">
            <tbody>
              {(["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const).map((l) => (
                <tr key={l}>
                  <td>{l.charAt(0) + l.slice(1).toLowerCase()} {l === "LOW" ? `(below ${risk.thresholds.MEDIUM})` : `(from ${risk.thresholds[l]})`}</td>
                  <td><Effect e={risk.decision_map[l]} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">
            Model weight {risk.ml_weight}: the local model alone can raise a request to review, but blocking an injection needs rule
            evidence too.
          </p>
        </Panel>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Benchmarks */
function BenchRow({ label, s }: { label: string; s?: BenchStats }) {
  return (
    <tr>
      <td>{label}</td>
      {s ? (
        <>
          <td className="num">{s.median_ms}</td><td className="num">{s.p95_ms}</td><td className="num">{s.mean_ms}</td>
          <td className="num">{s.throughput_per_s ?? "—"}</td><td className="num muted">{s.n}</td>
        </>
      ) : (
        <td colSpan={5} className="muted">Not available</td>
      )}
    </tr>
  );
}

export function Benchmarks({ status }: { status: Status | null }) {
  const [b, setB] = useState<Benchmark | null | undefined>(undefined);
  useEffect(() => { api.benchmark().then(setB).catch(() => setB(null)); }, []);
  return (
    <div className="page benchmarks">
      <div className="page-intro">
        <h1>Local AI and benchmarks</h1>
        <p className="muted">Values are read from this machine and from the last benchmark run. Nothing here is typed in by hand.</p>
      </div>
      <div className="bench-grid">
        <Panel title="Local AI status"><LocalAIStatus status={status} /></Panel>
        <Panel title="Latest benchmark" aside={b ? <span className="muted small mono">{new Date(b.timestamp).toLocaleString()}</span> : null}>
          {b === undefined && <p className="muted">Loading…</p>}
          {b === null && (
            <div className="empty">
              <p>No benchmark has been run on this machine yet.</p>
              <p className="mono small">python -m benchmark</p>
            </div>
          )}
          {b && (
            <>
              <dl className="kvs compact">
                <KV k="Provider" v={b.ml.provider ?? "ML unavailable"} mono />
                <KV k="Accelerator" v={b.ml.accelerator ?? "Not available"} />
                <KV k="Processor" v={b.machine.processor} />
                <KV k="Network during run" v={b.network_at_run} />
                <KV k="Warmup, iterations" v={`${b.config.warmup}, ${b.config.iterations}`} />
                <KV k="Memory after run" v={b.memory_rss_mb_after != null ? `${b.memory_rss_mb_after} MB` : "Not available"} />
              </dl>
              <div className="table-wrap">
                <table className="bench">
                  <thead><tr><th>Latency, ms</th><th>Median</th><th>p95</th><th>Mean</th><th>Per second</th><th>n</th></tr></thead>
                  <tbody>
                    <BenchRow label="Model inference" s={b.ml_inference} />
                    <BenchRow label="Full security check" s={b.full_pipeline} />
                    <BenchRow label="Rules only" s={b.rules_only} />
                  </tbody>
                </table>
              </div>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}
