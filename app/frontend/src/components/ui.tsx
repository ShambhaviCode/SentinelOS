import type { ReactNode } from "react";
import type { Decision, Level, SecurityEvent } from "../api";
import { CATEGORY_LABEL, DECISION_LABEL, decisionTone, fmtTime } from "../api";

export function DecisionBadge({ d, large = false }: { d: Decision; large?: boolean }) {
  return <span className={`badge badge-${decisionTone(d)}${large ? " badge-lg" : ""}`}>{DECISION_LABEL[d]}</span>;
}

export function LevelTag({ level }: { level: Level }) {
  return <span className={`level level-${level.toLowerCase()}`}>{level.charAt(0) + level.slice(1).toLowerCase()}</span>;
}

export function Panel({ title, aside, children, className = "" }: { title?: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {(title || aside) && (
        <header className="panel-head">
          {title && <h2>{title}</h2>}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}

export function KV({ k, v, mono = false }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="kv">
      <dt>{k}</dt>
      <dd className={mono ? "mono" : undefined}>{v}</dd>
    </div>
  );
}

export function EventRow({ ev, onSelect, selected }: { ev: SecurityEvent; onSelect?: () => void; selected?: boolean }) {
  const tool = ev.request.tool_request;
  const what = tool ? `${tool.tool} ${tool.target}` : ev.request.prompt;
  return (
    <tr className={`${onSelect ? "clickable" : ""}${selected ? " selected" : ""}`} onClick={onSelect}>
      <td className="mono muted nowrap">{fmtTime(ev.timestamp)}</td>
      <td className="nowrap">{CATEGORY_LABEL[ev.threat.category] ?? ev.threat.category}</td>
      <td className="truncate muted" title={what}>
        {what}
      </td>
      <td>
        <LevelTag level={ev.decision.level} />
      </td>
      <td className="nowrap">
        <DecisionBadge d={ev.decision.decision} />
        {ev.resolution && <span className="resolution">{ev.resolution.action === "APPROVED" ? "approved" : "denied"}</span>}
      </td>
    </tr>
  );
}

export function EventTable({ events, onSelect, selectedId, empty }: {
  events: SecurityEvent[];
  onSelect?: (ev: SecurityEvent) => void;
  selectedId?: string;
  empty: ReactNode;
}) {
  if (!events.length) return <div className="empty">{empty}</div>;
  return (
    <div className="table-wrap">
      <table className="events">
        <thead>
          <tr>
            <th>Time</th>
            <th>Finding</th>
            <th>Request</th>
            <th>Risk</th>
            <th>Decision</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev) => (
            <EventRow key={ev.id} ev={ev} onSelect={onSelect ? () => onSelect(ev) : undefined} selected={ev.id === selectedId} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
