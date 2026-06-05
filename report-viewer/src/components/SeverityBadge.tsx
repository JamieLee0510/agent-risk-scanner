import type { CaseEntry } from "../types/report";
import { SEVERITY_COLOR, SEVERITY_LABEL, severityOf } from "../lib/risk";

export function SeverityBadge({ entry }: { entry: CaseEntry }) {
  const sev = severityOf(entry);
  const color = SEVERITY_COLOR[sev];
  return (
    <span
      className="badge"
      style={{ color, background: `${color}1a`, borderColor: `${color}40` }}
    >
      <span className="dot" style={{ background: color }} />
      {SEVERITY_LABEL[sev]}
    </span>
  );
}

/** Compact pass/fail/inconclusive/error stacked bar for a single case. */
export function VerdictMini({ entry }: { entry: CaseEntry }) {
  const c = entry.verdict_counts;
  const total = entry.runs || 1;
  const segs: [number, string][] = [
    [c.fail, "var(--critical)"],
    [c.inconclusive, "var(--flaky)"],
    [c.error, "var(--neutral)"],
    [c.pass, "var(--secure)"],
  ];
  return (
    <span
      className="verdict-mini"
      title={`pass ${c.pass} · fail ${c.fail} · inconclusive ${c.inconclusive} · error ${c.error}`}
    >
      {segs.map(([n, color], i) =>
        n > 0 ? (
          <span key={i} style={{ width: `${(n / total) * 100}%`, background: color }} />
        ) : null,
      )}
    </span>
  );
}
