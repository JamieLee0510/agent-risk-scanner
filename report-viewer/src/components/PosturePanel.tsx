import type { Report } from "../types/report";
import { computePosture, type Posture } from "../lib/risk";

const GRADE_COLOR: Record<Posture["grade"], string> = {
  A: "var(--secure)",
  B: "var(--secure)",
  C: "var(--flaky)",
  D: "var(--high)",
  F: "var(--critical)",
};

function Stat({
  num,
  label,
  color,
}: {
  num: React.ReactNode;
  label: string;
  color?: string;
}) {
  return (
    <div className="card stat">
      <span className="num" style={color ? { color } : undefined}>
        {num}
      </span>
      <span className="label">{label}</span>
    </div>
  );
}

export function PosturePanel({ report }: { report: Report }) {
  const p = computePosture(report);
  const gradeColor = GRADE_COLOR[p.grade];

  return (
    <div
      className="grid"
      style={{ gridTemplateColumns: "1.4fr repeat(4, 1fr)", alignItems: "stretch" }}
    >
      <div
        className="card"
        style={{ display: "flex", alignItems: "center", gap: 18 }}
      >
        <div className="gauge-grade" style={{ color: gradeColor }}>
          {p.grade}
        </div>
        <div className="stat">
          <span className="num" style={{ color: gradeColor }}>
            {p.resistanceScore}
            <span style={{ fontSize: 15, color: "var(--text-dim)" }}>/100</span>
          </span>
          <span className="label">Attack resistance</span>
          <span className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>
            {p.attackRunsBlocked}/{p.attackRunsTotal} attack runs blocked
          </span>
        </div>
      </div>

      <Stat
        num={p.criticalCases}
        label="Critical (always breached)"
        color={p.criticalCases ? "var(--critical)" : undefined}
      />
      <Stat
        num={p.vulnerableCases}
        label="Vulnerable attack cases"
        color={p.vulnerableCases ? "var(--high)" : undefined}
      />
      <Stat
        num={p.falsePositiveCases}
        label="False positives (benign)"
        color={p.falsePositiveCases ? "var(--flaky)" : undefined}
      />
      <Stat num={`${p.attackCases}+${p.benignCases}`} label="Attack + benign cases" />
    </div>
  );
}
