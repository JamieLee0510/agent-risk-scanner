import { ShieldAlert } from "lucide-react";
import type { Report } from "../types/report";

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

const META = "text-dim text-[12.5px] flex flex-wrap gap-x-4 gap-y-1";

export function Header({ report, source }: { report: Report; source: string }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="m-0 mb-1 flex items-center gap-[9px] text-[19px] font-[650] tracking-[-0.01em]">
          <ShieldAlert size={20} color="var(--color-accent)" />
          Agent Risk Scanner
        </h1>
        <div className={META}>
          <span>
            agent <b className="font-mono font-medium text-text">{report.agent}</b>
          </span>
          <span>
            cases <b className="font-mono font-medium text-text">{report.cases_root}</b>
          </span>
          <span>
            generated <b className="font-medium text-text">{fmtDate(report.generated_at)}</b>
          </span>
        </div>
      </div>
      <div className="text-right text-[12.5px] text-faint">source: {source}</div>
    </div>
  );
}
