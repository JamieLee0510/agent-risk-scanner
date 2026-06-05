/**
 * Type definitions mirroring the JSON emitted by agent_risk_scanner/report.py
 * (build_report). Keep these in sync with the Python dataclasses in
 * agent_risk_scanner/schema.py.
 */

export type Verdict = "pass" | "fail" | "inconclusive" | "error";

export type CaseKind = "attack" | "benign";

export interface VerdictCounts {
  pass: number;
  fail: number;
  inconclusive: number;
  error: number;
}

export interface CaseEntry {
  case: string;
  category: string;
  kind: CaseKind;
  runs: number;
  verdict_counts: VerdictCounts;
  /** fraction of runs that produced a `fail` verdict (0..1) */
  fail_rate: number;
  /** distinct human-readable reasons aggregated across runs */
  reasons: string[];
  /** MCP tool calls observed (only present on mcp/* cases) */
  tool_calls?: string[];
  /** "host:port" outbound attempts captured by the egress observer */
  network_attempts?: string[];
}

export interface ReportSummary {
  cases: number;
  runs_per_case: number;
  total_runs: number;
  cases_with_fail: number;
}

export interface Report {
  agent: string;
  cases_root: string;
  generated_at: string;
  summary: ReportSummary;
  results: CaseEntry[];
}

/** Narrow an unknown parsed value to a Report, throwing on shape mismatch. */
export function assertReport(value: unknown): asserts value is Report {
  if (typeof value !== "object" || value === null) {
    throw new Error("Report must be a JSON object");
  }
  const r = value as Record<string, unknown>;
  if (!Array.isArray(r.results)) {
    throw new Error("Report is missing a `results` array — is this an agent-risk-scanner report?");
  }
  if (typeof r.summary !== "object" || r.summary === null) {
    throw new Error("Report is missing a `summary` object");
  }
}
