import type { Report } from "../types/report";
import { computePosture, type Posture } from "../lib/risk";

const GRADE_COLOR: Record<Posture["grade"], string> = {
  A: "var(--color-secure)",
  B: "var(--color-secure)",
  C: "var(--color-flaky)",
  D: "var(--color-high)",
  F: "var(--color-critical)",
};

const NUM = "text-[26px] font-[680] leading-[1.1] tracking-[-0.02em]";

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
    <div className="card flex flex-col gap-0.5">
      <span className={NUM} style={color ? { color } : undefined}>
        {num}
      </span>
      <span className="text-[12px] text-dim">{label}</span>
    </div>
  );
}

export function PosturePanel({ report }: { report: Report }) {
  const p = computePosture(report);
  const gradeColor = GRADE_COLOR[p.grade];

  return (
    <div className="grid items-stretch gap-[14px] [grid-template-columns:1.4fr_repeat(4,1fr)]">
      <div className="card flex items-center gap-[18px]">
        <div
          className="text-[46px] font-[750] leading-none tracking-[-0.03em]"
          style={{ color: gradeColor }}
        >
          {p.grade}
        </div>
        <div className="flex flex-col gap-0.5">
          <span className={NUM} style={{ color: gradeColor }}>
            {p.resistanceScore}
            <span className="text-[15px] text-dim">/100</span>
          </span>
          <span className="text-[12px] text-dim">Attack resistance</span>
          <span className="mt-0.5 text-[11.5px] text-faint">
            {p.attackRunsBlocked}/{p.attackRunsTotal} attack runs blocked
          </span>
        </div>
      </div>

      <Stat
        num={p.criticalCases}
        label="Critical (always breached)"
        color={p.criticalCases ? "var(--color-critical)" : undefined}
      />
      <Stat
        num={p.vulnerableCases}
        label="Vulnerable attack cases"
        color={p.vulnerableCases ? "var(--color-high)" : undefined}
      />
      <Stat
        num={p.falsePositiveCases}
        label="False positives (benign)"
        color={p.falsePositiveCases ? "var(--color-flaky)" : undefined}
      />
      <Stat num={`${p.attackCases}+${p.benignCases}`} label="Attack + benign cases" />
    </div>
  );
}
