import { useState } from "react";
import type { AgentRequest, Preset, SecurityEvent, ToolRequest } from "../api";
import { api } from "../api";
import ThreatDetail from "../components/ThreatDetail";
import TrustGraph from "../components/TrustGraph";
import { Panel } from "../components/ui";

const TOOLS = ["", "file.read", "file.list", "file.write", "file.delete", "shell.exec", "network.request", "email.send"];
const SCOPES = ["", "file", "directory", "recursive", "profile", "drive"];
const BLANK_TOOL: ToolRequest = { tool: "", target: "", scope: "", reason: "", payload: "" };

export default function Console({ presets, onAnalyzed, last, setLast }: {
  presets: Preset[];
  onAnalyzed: () => void;
  last: SecurityEvent | null;
  setLast: (e: SecurityEvent | null) => void;
}) {
  const [req, setReq] = useState<AgentRequest>({ prompt: "", context: "", context_source: "untrusted", tool_request: null });
  const [tool, setTool] = useState<ToolRequest>(BLANK_TOOL);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = (p: Preset) => {
    setPresetId(p.id);
    setReq({ ...p.request, tool_request: null });
    setTool({ ...BLANK_TOOL, ...(p.request.tool_request ?? {}) });
    setLast(null);
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const ev = await api.analyze({ ...req, tool_request: tool.tool ? tool : null, preset_id: presetId });
      setLast(ev);
      onAnalyzed();
    } catch (e) {
      setError(`The security check could not run: ${(e as Error).message}. Check that the SentinelOS server is running.`);
    } finally {
      setBusy(false);
    }
  };

  const edit = () => setPresetId(null);

  return (
    <div className="page console">
      <div className="page-intro">
        <h1>Agent console</h1>
        <p className="muted">
          Agent Security Test Environment. Send a prompt, the content the agent read, and the action it wants to take. Tools
          are simulated; nothing is executed.
        </p>
      </div>

      <div className="presets" role="group" aria-label="Demo scenarios">
        {presets.map((p) => (
          <button key={p.id} className={`preset${presetId === p.id ? " active" : ""}`} onClick={() => load(p)}>
            <span className="preset-name">{p.name}</span>
            <span className="preset-sum">{p.summary}</span>
          </button>
        ))}
      </div>

      <div className="inputs">
        <Panel title="Prompt">
          <label className="sr" htmlFor="prompt">Prompt</label>
          <textarea id="prompt" rows={6} value={req.prompt} placeholder="What the user asked the agent to do"
            onChange={(e) => { edit(); setReq({ ...req, prompt: e.target.value }); }} />
        </Panel>
        <Panel title="Context" aside={
          <label className="inline-select">
            Source
            <select value={req.context_source} onChange={(e) => { edit(); setReq({ ...req, context_source: e.target.value as AgentRequest["context_source"] }); }}>
              <option value="untrusted">Untrusted</option>
              <option value="trusted">Trusted</option>
            </select>
          </label>
        }>
          <label className="sr" htmlFor="context">Context</label>
          <textarea id="context" rows={6} value={req.context} placeholder="A document, web page or email the agent read"
            onChange={(e) => { edit(); setReq({ ...req, context: e.target.value }); }} />
        </Panel>
        <Panel title="Tool request">
          <div className="tool-form">
            <label>
              Tool
              <select value={tool.tool} onChange={(e) => { edit(); setTool({ ...tool, tool: e.target.value }); }}>
                {TOOLS.map((t) => <option key={t} value={t}>{t || "No tool"}</option>)}
              </select>
            </label>
            <label>
              Scope
              <select value={tool.scope} disabled={!tool.tool} onChange={(e) => { edit(); setTool({ ...tool, scope: e.target.value }); }}>
                {SCOPES.map((s) => <option key={s} value={s}>{s || "Infer"}</option>)}
              </select>
            </label>
            <label className="wide">
              Target
              <input disabled={!tool.tool} value={tool.target} placeholder="Path, URL, command or recipient"
                onChange={(e) => { edit(); setTool({ ...tool, target: e.target.value }); }} />
            </label>
            <label className="wide">
              Reason given by the agent
              <input disabled={!tool.tool} value={tool.reason} onChange={(e) => { edit(); setTool({ ...tool, reason: e.target.value }); }} />
            </label>
          </div>
        </Panel>
      </div>

      <div className="run-bar">
        <button className="btn btn-primary" onClick={run} disabled={busy || (!req.prompt && !req.context && !tool.tool)}>
          {busy ? "Checking…" : "Run security check"}
        </button>
        {error && <p className="error" role="alert">{error}</p>}
      </div>

      <Panel title="Agent trust graph" className="graph-panel">
        <TrustGraph event={last} />
      </Panel>

      {last && (
        <div className="result" aria-live="polite">
          <ThreatDetail ev={last} onResolve={async (a) => { setLast(await api.resolve(last.id, a)); onAnalyzed(); }} />
        </div>
      )}
    </div>
  );
}
