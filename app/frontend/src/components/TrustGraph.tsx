import type { SecurityEvent } from "../api";
import { pct } from "../api";

type Tone = "idle" | "ok" | "warn" | "bad" | "off";

interface NodeSpec {
  id: string;
  x: number;
  y: number;
  w: number;
  title: string;
  sub?: string;
  tone: Tone;
}

const H = 54;

function toneForScore(s: number): Tone {
  if (s >= 0.6) return "bad";
  if (s >= 0.3) return "warn";
  return "ok";
}

function Node({ n }: { n: NodeSpec }) {
  return (
    <g className={`tg-node tg-${n.tone}`}>
      <rect x={n.x} y={n.y - H / 2} width={n.w} height={H} rx={8} />
      <text x={n.x + 12} y={n.sub ? n.y - 4 : n.y + 4} className="tg-title">
        {n.title}
      </text>
      {n.sub && (
        <text x={n.x + 12} y={n.y + 14} className="tg-sub">
          {n.sub}
        </text>
      )}
    </g>
  );
}

function Edge({ a, b, tone }: { a: NodeSpec; b: NodeSpec; tone: Tone }) {
  const x1 = a.x + a.w;
  const x2 = b.x;
  const mx = (x1 + x2) / 2;
  return <path className={`tg-edge tg-edge-${tone}`} d={`M${x1},${a.y} C${mx},${a.y} ${mx},${b.y} ${x2},${b.y}`} />;
}

/** Draws the path one agent request took through SentinelOS. Every value comes from the event. */
export default function TrustGraph({ event }: { event: SecurityEvent | null }) {
  const has = {
    prompt: !!event?.request.prompt,
    context: !!event?.request.context,
    tool: !!event?.request.tool_request,
  };
  const s = event?.risk.scores ?? { prompt: 0, data: 0, tool: 0 };
  const d = event?.decision.decision;
  const idle = !event;
  const t = (on: boolean, score: number): Tone => (idle ? "idle" : on ? toneForScore(score) : "off");

  const ml = event?.ml;
  const promptSub = idle
    ? "patterns + local model"
    : `rules ${Math.round(s.prompt * 100)}, model ` + (ml?.available ? pct(ml.injection_probability) : "off");

  const N: Record<string, NodeSpec> = {
    user: { id: "user", x: 10, y: 150, w: 96, title: "User", tone: idle ? "idle" : "ok" },
    agent: { id: "agent", x: 138, y: 150, w: 104, title: "AI agent", sub: "test environment", tone: idle ? "idle" : "ok" },
    iPrompt: { id: "iPrompt", x: 278, y: 60, w: 112, title: "Prompt", sub: has.prompt ? "from user" : "empty", tone: idle ? "idle" : has.prompt ? "ok" : "off" },
    iContext: {
      id: "iContext", x: 278, y: 150, w: 112, title: "Context",
      sub: has.context ? event!.request.context_source : "empty",
      tone: idle ? "idle" : has.context ? (event!.request.context_source === "untrusted" ? "warn" : "ok") : "off",
    },
    iTool: {
      id: "iTool", x: 278, y: 240, w: 112, title: "Tool request",
      sub: has.tool ? event!.request.tool_request!.tool : "none", tone: idle ? "idle" : has.tool ? "ok" : "off",
    },
    sPrompt: { id: "sPrompt", x: 444, y: 60, w: 150, title: "Injection scan", sub: promptSub, tone: t(has.prompt || has.context, s.prompt) },
    sData: { id: "sData", x: 444, y: 150, w: 150, title: "Data scan", sub: idle ? "secrets, PII" : `score ${Math.round(s.data * 100)}`, tone: t(has.prompt || has.context || has.tool, s.data) },
    sTool: { id: "sTool", x: 444, y: 240, w: 150, title: "Tool scan", sub: idle ? "scope, destination" : `score ${Math.round(s.tool * 100)}`, tone: t(has.tool, s.tool) },
    risk: {
      id: "risk", x: 614, y: 150, w: 80, title: "Risk",
      sub: idle ? "engine" : `${event!.risk.score_100}/100`, tone: idle ? "idle" : toneForScore(event!.risk.overall),
    },
    policy: {
      id: "policy", x: 706, y: 150, w: 88, title: "Policy",
      sub: idle ? "rules" : event!.decision.policy_verdicts.length === 0 ? "no rule hit" : `${event!.decision.policy_verdicts.length} rule hit${event!.decision.policy_verdicts.length === 1 ? "" : "s"}`,
      tone: idle ? "idle" : event!.decision.policy_verdicts.some((v) => v.effect === "BLOCK") ? "bad" : event!.decision.policy_verdicts.length ? "warn" : "ok",
    },
    dAllow: { id: "dAllow", x: 850, y: 60, w: 128, title: "Allow", tone: d === "ALLOW" ? "ok" : "off" },
    dReview: { id: "dReview", x: 850, y: 150, w: 128, title: "Needs approval", tone: d === "REQUIRE_APPROVAL" ? "warn" : "off" },
    dBlock: { id: "dBlock", x: 850, y: 240, w: 128, title: "Block", tone: d === "BLOCK" ? "bad" : "off" },
  };
  if (idle) {
    N.dAllow.tone = N.dReview.tone = N.dBlock.tone = "idle";
  }
  const decisionNode = d === "ALLOW" ? N.dAllow : d === "BLOCK" ? N.dBlock : d ? N.dReview : null;

  const edges: [NodeSpec, NodeSpec, Tone][] = [
    [N.user, N.agent, N.user.tone],
    [N.agent, N.iPrompt, N.iPrompt.tone],
    [N.agent, N.iContext, N.iContext.tone],
    [N.agent, N.iTool, N.iTool.tone],
    [N.iPrompt, N.sPrompt, N.iPrompt.tone === "off" ? "off" : N.sPrompt.tone],
    [N.iContext, N.sPrompt, N.iContext.tone === "off" ? "off" : N.sPrompt.tone],
    [N.iContext, N.sData, N.iContext.tone === "off" ? "off" : N.sData.tone],
    [N.iTool, N.sTool, N.iTool.tone === "off" ? "off" : N.sTool.tone],
    [N.sPrompt, N.risk, N.sPrompt.tone],
    [N.sData, N.risk, N.sData.tone],
    [N.sTool, N.risk, N.sTool.tone],
    [N.risk, N.policy, N.risk.tone],
  ];

  return (
    <figure className="trust-graph" key={event?.id ?? "idle"}>
      <svg viewBox="0 0 990 300" role="img" aria-label="Agent trust graph for the selected security check">
        <rect className="tg-boundary" x={426} y={8} width={374} height={284} rx={14} />
        <text className="tg-boundary-label" x={442} y={290 - 10}>
          SentinelOS boundary, running on this device
        </text>
        {edges.map(([a, b, tone], i) => (
          <Edge key={i} a={a} b={b} tone={tone} />
        ))}
        {decisionNode
          ? <Edge a={N.policy} b={decisionNode} tone={decisionNode.tone} />
          : [N.dAllow, N.dReview, N.dBlock].map((n) => <Edge key={n.id} a={N.policy} b={n} tone="idle" />)}
        {Object.values(N).map((n) => (
          <Node key={n.id} n={n} />
        ))}
      </svg>
      <figcaption>
        {idle
          ? "Run a security check to trace how a request moves through the boundary."
          : "Each node shows the score it contributed to this decision. Grey paths were not part of the request."}
      </figcaption>
    </figure>
  );
}
