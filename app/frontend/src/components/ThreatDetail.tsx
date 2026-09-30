import type { SecurityEvent } from "../api";
import { decisionTone, pct } from "../api";
import { DecisionBadge, LevelTag } from "./ui";

const SOURCE_LABEL: Record<string, string> = { prompt: "Prompt", context: "Context", tool_request: "Tool request" };

export default function ThreatDetail({ ev, onResolve }: { ev: SecurityEvent; onResolve?: (a: "approve" | "deny") => void }) {
  const tone = decisionTone(ev.decision.decision);
  const clean = ev.threat.category === "NONE";
  const pending = ev.decision.decision === "REQUIRE_APPROVAL" && !ev.resolution;
  const drivers = ev.decision.drivers.filter((d) => d.rule_id !== "RISK-LEVEL");

  return (
    <article className={`threat threat-${tone}`}>
      <header className="verdict">
        <div className="verdict-main">
          <p className="verdict-kicker">{clean ? "No threat detected" : "Threat detected"}</p>
          <h3>{ev.threat.title}</h3>
          <p className="verdict-expl">{ev.threat.explanation}</p>
        </div>
        <div className="verdict-side">
          <DecisionBadge d={ev.decision.decision} large />
          {ev.resolution && (
            <p className="muted small">
              {ev.resolution.action === "APPROVED" ? "Approved" : "Denied"} by {ev.resolution.actor}
            </p>
          )}
        </div>
      </header>

      <dl className="metrics">
        <div>
          <dt>Severity</dt>
          <dd>
            <LevelTag level={ev.decision.level} />
          </dd>
        </div>
        <div>
          <dt>Risk score</dt>
          <dd className="num">
            {ev.risk.score_100}
            <span className="muted">/100</span>
          </dd>
        </div>
        <div>
          <dt>Model confidence (injection)</dt>
          <dd className="num">{ev.ml.available ? pct(ev.ml.injection_probability) : <span className="muted small">ML classifier unavailable</span>}</dd>
        </div>
        <div>
          <dt>Decision time</dt>
          <dd className="num">
            {ev.timings_ms.total.toFixed(1)}
            <span className="muted"> ms</span>
          </dd>
        </div>
      </dl>

      {ev.signals.length > 0 && (
        <section className="evidence">
          <h4>Evidence</h4>
          <ul>
            {ev.signals
              .slice()
              .sort((a, b) => b.weight - a.weight)
              .map((s, i) => (
                <li key={i}>
                  <div className="ev-head">
                    <span className="mono rule">{s.rule_id}</span>
                    <span>{s.description}</span>
                    <span className="muted small ev-src">{SOURCE_LABEL[s.source] ?? s.source}</span>
                  </div>
                  <blockquote className="mono">{s.evidence}</blockquote>
                </li>
              ))}
          </ul>
        </section>
      )}

      {drivers.length > 0 && (
        <section className="drivers">
          <h4>Policy</h4>
          <ul>
            {drivers.map((d) => (
              <li key={d.rule_id}>
                <span className="mono rule">{d.rule_id}</span> {d.reason}
              </li>
            ))}
          </ul>
        </section>
      )}

      {!clean && (
        <div className="context-grid">
          <section>
            <h4>Why this matters</h4>
            <p>{ev.threat.why_it_matters}</p>
          </section>
          <section>
            <h4>What SentinelOS prevented</h4>
            <p>{ev.decision.decision === "ALLOW" ? "Nothing was stopped; the request was within policy." : ev.threat.prevented}</p>
          </section>
          <section>
            <h4>Recommended action</h4>
            <p>{ev.threat.recommended_action}</p>
          </section>
        </div>
      )}

      {pending && onResolve && (
        <footer className="approval">
          <p>This request is waiting for a person to decide.</p>
          <div className="btn-row">
            <button className="btn btn-quiet" onClick={() => onResolve("deny")}>
              Deny request
            </button>
            <button className="btn" onClick={() => onResolve("approve")}>
              Approve request
            </button>
          </div>
        </footer>
      )}
    </article>
  );
}
