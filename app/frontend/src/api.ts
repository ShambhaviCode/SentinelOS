export type Decision = "ALLOW" | "REQUIRE_APPROVAL" | "BLOCK";
export type Level = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface ToolRequest {
  tool: string;
  target: string;
  scope: string;
  reason: string;
  payload?: string;
}

export interface AgentRequest {
  prompt: string;
  context: string;
  context_source: "untrusted" | "trusted";
  tool_request: ToolRequest | null;
  preset_id?: string | null;
}

export interface Signal {
  scanner: "prompt" | "data" | "tool";
  category: string;
  rule_id: string;
  description: string;
  weight: number;
  source: string;
  evidence: string;
}

export interface MLResult {
  available: boolean;
  label: string | null;
  injection_probability: number | null;
  provider: string | null;
  latency_ms: number | null;
  error: string | null;
}

export interface PolicyVerdict {
  rule_id: string;
  effect: Decision;
  reason: string;
}

export interface SecurityEvent {
  id: string;
  timestamp: string;
  preset_id: string | null;
  request: AgentRequest;
  signals: Signal[];
  ml: MLResult;
  risk: {
    scores: { prompt: number; data: number; tool: number };
    overall: number;
    score_100: number;
    level: Level;
    primary_category: string;
  };
  decision: {
    decision: Decision;
    level: Level;
    drivers: PolicyVerdict[];
    policy_verdicts: PolicyVerdict[];
  };
  threat: {
    category: string;
    title: string;
    explanation: string;
    why_it_matters: string;
    prevented: string;
    recommended_action: string;
  };
  reasoning: string[];
  timings_ms: Record<string, number>;
  resolution?: { action: "APPROVED" | "DENIED"; actor: string; at: string };
}

export interface Preset {
  id: string;
  name: string;
  summary: string;
  expected: { decision: Decision; levels: Level[] };
  request: AgentRequest;
}

export interface Stats {
  events: number;
  allowed: number;
  blocked: number;
  approval_required: number;
  pending_approval: number;
  tool_requests: number;
  prompt_injection: number;
  data_events: number;
}

export interface MLStatus {
  available: boolean;
  model: string | null;
  model_file: string | null;
  runtime: string | null;
  runtime_version: string | null;
  provider: string | null;
  accelerator: string | null;
  cpu_fallback_disabled: boolean;
  load_time_ms: number | null;
  errors: string[];
}

export interface Status {
  ml: MLStatus;
  machine: {
    processor: string;
    os: string;
    python: string;
    python_arch: string;
    onnxruntime: string;
    available_providers: string[];
    memory_rss_mb: number | null;
  };
  network: "online" | "offline";
  analysis_path: string;
  npu_verification: { verdict: string; timestamp: string; latency_ms?: { median: number; p95: number } } | null;
}

export interface BenchStats {
  n: number;
  median_ms: number;
  p95_ms: number;
  mean_ms: number;
  min_ms: number;
  max_ms: number;
  throughput_per_s: number | null;
  input: string;
}

export interface Benchmark {
  timestamp: string;
  machine: Status["machine"];
  network_at_run: string;
  config: { provider_requested: string; iterations: number; warmup: number };
  ml: Partial<MLStatus>;
  ml_inference?: BenchStats;
  full_pipeline?: BenchStats;
  rules_only?: BenchStats;
  memory_rss_mb_after: number | null;
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  status: () => fetch("/api/status").then(j<Status>),
  presets: () => fetch("/api/presets").then(j<Preset[]>),
  events: () => fetch("/api/events").then(j<{ events: SecurityEvent[]; stats: Stats }>),
  policies: () => fetch("/api/policies").then(j<Record<string, any>>),
  benchmark: () => fetch("/api/benchmark").then(j<Benchmark | null>),
  analyze: (req: AgentRequest) =>
    fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) }).then(
      j<SecurityEvent>,
    ),
  resolve: (id: string, action: "approve" | "deny") =>
    fetch(`/api/events/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    }).then(j<SecurityEvent>),
};

export const DECISION_LABEL: Record<Decision, string> = {
  ALLOW: "Allowed",
  REQUIRE_APPROVAL: "Needs approval",
  BLOCK: "Blocked",
};

export const CATEGORY_LABEL: Record<string, string> = {
  PROMPT_INJECTION: "Prompt injection",
  DATA_EXPOSURE: "Data exposure",
  EXCESSIVE_PRIVILEGE: "Excessive privilege",
  UNSAFE_TOOL_USE: "Unsafe tool use",
  SUSPICIOUS_DESTINATION: "Suspicious destination",
  POLICY_VIOLATION: "Policy violation",
  NONE: "No threat",
};

export function decisionTone(d: Decision): "allow" | "review" | "block" {
  return d === "ALLOW" ? "allow" : d === "BLOCK" ? "block" : "review";
}

export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function pct(p: number | null | undefined): string {
  return p == null ? "—" : `${(p * 100).toFixed(1)}%`;
}
