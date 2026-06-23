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
      <span className="h-2 w-2 flex-none rounded-full" style={{ background: color }} />
      {SEVERITY_LABEL[sev]}
    </span>
  );
}

/** Compact pass/fail/inconclusive/error stacked bar for a single case. */
export function VerdictMini({ entry }: { entry: CaseEntry }) {
  const c = entry.verdict_counts;
  const total = entry.runs || 1;
  // Data-driven colors, so inline styles (not utilities) — sourced from the
  // same severity palette as everything else.
  const segs: [number, string][] = [
    [c.fail, SEVERITY_COLOR.critical],
    [c.inconclusive, SEVERITY_COLOR.flaky],
    [c.error, SEVERITY_COLOR.neutral],
    [c.pass, SEVERITY_COLOR.secure],
  ];
  return (
    <span
      className="inline-flex h-1.5 w-[84px] overflow-hidden rounded-[3px] bg-line"
      title={`pass ${c.pass} · fail ${c.fail} · inconclusive ${c.inconclusive} · error ${c.error}`}
    >
      {segs.map(([n, color], i) =>
        n > 0 ? (
          <span
            key={i}
            className="h-full"
            style={{ width: `${(n / total) * 100}%`, background: color }}
          />
        ) : null,
      )}
    </span>
  );
}
