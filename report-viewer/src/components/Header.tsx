import { ShieldAlert } from "lucide-react";
import type { Report } from "../types/report";

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function Header({ report, source }: { report: Report; source: string }) {
  return (
    <div className="header">
      <div>
        <h1 style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <ShieldAlert size={20} color="var(--accent)" />
          Agent Risk Scanner
        </h1>
        <div className="meta">
          <span>
            agent <b className="mono">{report.agent}</b>
          </span>
          <span>
            cases <b className="mono">{report.cases_root}</b>
          </span>
          <span>
            generated <b>{fmtDate(report.generated_at)}</b>
          </span>
        </div>
      </div>
      <div className="meta muted" style={{ textAlign: "right" }}>
        source: {source}
      </div>
    </div>
  );
}
