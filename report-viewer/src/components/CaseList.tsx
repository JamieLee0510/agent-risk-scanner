import { useMemo, useState } from "react";
import { ChevronRight, AlertTriangle, Network, Wrench } from "lucide-react";
import type { CaseEntry, Report } from "../types/report";
import { SEVERITY_COLOR, severityOf, severityRank } from "../lib/risk";
import { SeverityBadge, VerdictMini } from "./SeverityBadge";

type SortKey = "severity" | "failrate" | "name";

export function CaseList({
  report,
  focus,
}: {
  report: Report;
  /** case name to auto-expand & scroll into view (from chart click) */
  focus?: string | null;
}) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [kind, setKind] = useState("all");
  const [onlyFails, setOnlyFails] = useState(false);
  const [sort, setSort] = useState<SortKey>("severity");
  const [open, setOpen] = useState<Set<string>>(() => new Set());

  const categories = useMemo(
    () => Array.from(new Set(report.results.map((r) => r.category))).sort(),
    [report],
  );

  const rows = useMemo(() => {
    let r = report.results.filter((c) => {
      if (cat !== "all" && c.category !== cat) return false;
      if (kind !== "all" && c.kind !== kind) return false;
      if (onlyFails && c.verdict_counts.fail === 0) return false;
      if (q && !c.case.toLowerCase().includes(q.toLowerCase())) return false;
      return true;
    });
    r = [...r].sort((a, b) => {
      if (sort === "name") return a.case.localeCompare(b.case);
      if (sort === "failrate") return b.fail_rate - a.fail_rate;
      return severityRank(b) - severityRank(a) || b.fail_rate - a.fail_rate;
    });
    return r;
  }, [report, q, cat, kind, onlyFails, sort]);

  const toggle = (name: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const isOpen = (name: string) => open.has(name) || focus === name;

  return (
    <div>
      <div className="toolbar">
        <input
          className="input"
          placeholder="Filter cases by name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="select" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="all">Attack + benign</option>
          <option value="attack">Attack only</option>
          <option value="benign">Benign only</option>
        </select>
        <select
          className="select"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
        >
          <option value="severity">Sort: severity</option>
          <option value="failrate">Sort: fail-rate</option>
          <option value="name">Sort: name</option>
        </select>
        <label
          className="badge"
          style={{ cursor: "pointer", borderColor: "var(--border-strong)" }}
        >
          <input
            type="checkbox"
            checked={onlyFails}
            onChange={(e) => setOnlyFails(e.target.checked)}
            style={{ accentColor: "var(--accent)" }}
          />
          Failures only
        </label>
      </div>

      <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        {rows.length} of {report.results.length} cases
      </div>

      {rows.map((c) => (
        <CaseRow key={c.case} entry={c} open={isOpen(c.case)} onToggle={() => toggle(c.case)} />
      ))}
      {rows.length === 0 && <div className="empty">No cases match these filters.</div>}
    </div>
  );
}

function CaseRow({
  entry,
  open,
  onToggle,
}: {
  entry: CaseEntry;
  open: boolean;
  onToggle: () => void;
}) {
  const sevColor = SEVERITY_COLOR[severityOf(entry)];
  return (
    <div className="case" id={`case-${entry.case}`}>
      <div className="case-head" onClick={onToggle}>
        <div className="sev-bar" style={{ background: sevColor }} />
        <div>
          <div className="case-name">
            {entry.case}{" "}
            {entry.kind === "benign" && (
              <span className="chip" style={{ marginLeft: 6 }}>
                benign
              </span>
            )}
          </div>
          <div className="case-cat mono">{entry.category}</div>
        </div>
        <VerdictMini entry={entry} />
        <div
          style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "flex-end" }}
        >
          <span className="failrate" style={{ color: sevColor }}>
            {(entry.fail_rate * 100).toFixed(0)}%
          </span>
          <SeverityBadge entry={entry} />
          <ChevronRight
            size={15}
            style={{
              transform: open ? "rotate(90deg)" : "none",
              transition: "transform 0.15s",
              color: "var(--text-faint)",
            }}
          />
        </div>
      </div>

      {open && (
        <div className="case-body">
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            {entry.runs} runs · pass {entry.verdict_counts.pass} · fail{" "}
            {entry.verdict_counts.fail} · inconclusive {entry.verdict_counts.inconclusive} · error{" "}
            {entry.verdict_counts.error}
          </div>

          {entry.reasons.length > 0 ? (
            <div>
              {entry.reasons.map((r, i) => (
                <div className="reason" key={i}>
                  <AlertTriangle size={14} color={sevColor} style={{ marginTop: 2, flex: "none" }} />
                  <span className="mono">{r}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="muted" style={{ fontSize: 12.5 }}>
              No failing evidence — the agent handled this case cleanly.
            </div>
          )}

          {(entry.tool_calls?.length || entry.network_attempts?.length) && (
            <div className="kv">
              {entry.tool_calls?.map((t) => (
                <span className="chip mono" key={`t-${t}`}>
                  <Wrench size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} />
                  {t}
                </span>
              ))}
              {entry.network_attempts?.map((n) => (
                <span className="chip mono" key={`n-${n}`}>
                  <Network size={11} style={{ verticalAlign: "-1px", marginRight: 4 }} />
                  {n}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
