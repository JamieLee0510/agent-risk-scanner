import { useEffect, useMemo, useState } from "react";
import {
  ChevronRight,
  Maximize2,
  AlertTriangle,
  Network,
  Wrench,
  X,
  MessageSquare,
  FileWarning,
  Target,
} from "lucide-react";
import type { CaseEntry, Report } from "../types/report";
import { SEVERITY_COLOR, SEVERITY_LABEL, severityOf, severityRank } from "../lib/risk";
import { SeverityBadge, VerdictMini } from "./SeverityBadge";

type SortKey = "severity" | "failrate" | "name";

// Repeated utility groupings, named so the JSX below stays readable.
const REASON =
  "flex items-start gap-2 border-b border-dashed border-line py-1.5 text-[12.5px] text-text last:border-b-0";
const H4 =
  "m-0 mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-[0.05em] text-dim";
const CARRIER_HEAD = "py-1 font-mono text-[11.5px] text-dim";

/**
 * Does this case represent a finding worth a drill-down dialog? True when the
 * agent was compromised on an attack case at least once (critical / high /
 * intermittent). Benign false-positives and secure passes keep the lightweight
 * inline expander instead.
 */
function hasFinding(entry: CaseEntry): boolean {
  return entry.kind !== "benign" && entry.verdict_counts.fail > 0;
}

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
  const [dialog, setDialog] = useState<CaseEntry | null>(null);

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

  // A case row click routes to the finding dialog when it's a real finding,
  // otherwise to the lightweight inline expander.
  const activate = (entry: CaseEntry) => {
    if (hasFinding(entry)) setDialog(entry);
    else toggle(entry.case);
  };

  // Selecting a finding from a chart pops its dialog; a non-finding expands.
  useEffect(() => {
    if (!focus) return;
    const entry = report.results.find((r) => r.case === focus);
    if (entry && hasFinding(entry)) setDialog(entry);
  }, [focus, report]);

  const isOpen = (name: string) => open.has(name) || focus === name;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2.5">
        <input
          className="field min-w-[180px] flex-1"
          placeholder="Filter cases by name…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select className="field" value={cat} onChange={(e) => setCat(e.target.value)}>
          <option value="all">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select className="field" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="all">Attack + benign</option>
          <option value="attack">Attack only</option>
          <option value="benign">Benign only</option>
        </select>
        <select
          className="field"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
        >
          <option value="severity">Sort: severity</option>
          <option value="failrate">Sort: fail-rate</option>
          <option value="name">Sort: name</option>
        </select>
        <label className="badge cursor-pointer border-line-strong">
          <input
            type="checkbox"
            checked={onlyFails}
            onChange={(e) => setOnlyFails(e.target.checked)}
            className="accent-accent"
          />
          Failures only
        </label>
      </div>

      <div className="mb-2.5 text-[12px] text-faint">
        {rows.length} of {report.results.length} cases
      </div>

      {rows.map((c) => (
        <CaseRow
          key={c.case}
          entry={c}
          open={isOpen(c.case)}
          finding={hasFinding(c)}
          onActivate={() => activate(c)}
        />
      ))}
      {rows.length === 0 && (
        <div className="py-[60px] text-center text-dim">No cases match these filters.</div>
      )}

      {dialog && <CaseDialog entry={dialog} onClose={() => setDialog(null)} />}
    </div>
  );
}

function CaseRow({
  entry,
  open,
  finding,
  onActivate,
}: {
  entry: CaseEntry;
  open: boolean;
  /** true => clicking opens the drill-down dialog rather than inline expand */
  finding: boolean;
  onActivate: () => void;
}) {
  const sevColor = SEVERITY_COLOR[severityOf(entry)];
  return (
    <div className="mb-2 overflow-hidden rounded-[10px] border border-line bg-card" id={`case-${entry.case}`}>
      <div
        className="grid cursor-pointer select-none grid-cols-[14px_1fr_auto_auto] items-center gap-3 px-3.5 py-3 hover:bg-hover"
        onClick={onActivate}
        title={finding ? "Click to inspect this finding" : undefined}
      >
        <div className="w-1 self-stretch rounded" style={{ background: sevColor }} />
        <div>
          <div className="text-[13.5px] font-[550]">
            {entry.case}{" "}
            {entry.kind === "benign" && <span className="chip ml-1.5">benign</span>}
          </div>
          <div className="font-mono text-[11.5px] text-faint">{entry.category}</div>
        </div>
        <VerdictMini entry={entry} />
        <div className="flex items-center justify-end gap-3">
          <span className="text-[13px] font-semibold tabular-nums" style={{ color: sevColor }}>
            {(entry.fail_rate * 100).toFixed(0)}%
          </span>
          <SeverityBadge entry={entry} />
          {finding ? (
            <Maximize2 size={14} style={{ color: sevColor }} />
          ) : (
            <ChevronRight
              size={15}
              className="text-faint transition-transform"
              style={{ transform: open ? "rotate(90deg)" : "none" }}
            />
          )}
        </div>
      </div>

      {/* Inline expander only for non-findings (secure passes, benign FPs). */}
      {open && !finding && (
        <div className="border-t border-line bg-raised px-4 py-3.5">
          <div className="mb-2 text-[12px] text-faint">
            {entry.runs} runs · pass {entry.verdict_counts.pass} · fail{" "}
            {entry.verdict_counts.fail} · inconclusive {entry.verdict_counts.inconclusive} · error{" "}
            {entry.verdict_counts.error}
          </div>

          {entry.reasons.length > 0 ? (
            <div>
              {entry.reasons.map((r, i) => (
                <div className={REASON} key={i}>
                  <AlertTriangle size={14} color={sevColor} className="mt-0.5 flex-none" />
                  <span className="font-mono">{r}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[12.5px] text-faint">
              No failing evidence — the agent handled this case cleanly.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Drill-down dialog for a finding: the situation it set up, the prompt the
 * agent was handed, and the critical behaviour it was provoked into — the
 * "what, how and so-what" of a single compromise.
 */
function CaseDialog({ entry, onClose }: { entry: CaseEntry; onClose: () => void }) {
  const sevColor = SEVERITY_COLOR[severityOf(entry)];
  const sevLabel = SEVERITY_LABEL[severityOf(entry)];
  const detail = entry.detail;

  // Esc closes; lock background scroll while the dialog is up.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  const fixtures = detail?.fixtures ? Object.entries(detail.fixtures) : [];
  const mcpTools = detail?.mcp?.tools ?? [];
  const expect = detail?.expect;
  // web / skill carriers are free-form; show them as pretty JSON when present.
  const rawCarrier = detail?.web ?? detail?.skill;
  const rawCarrierJson = rawCarrier != null ? JSON.stringify(rawCarrier, null, 2) : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 px-4 pb-4 pt-[6vh] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-[720px] animate-[dialog-in_0.14s_ease] rounded-[14px] border border-line-strong bg-card shadow-[0_24px_64px_rgba(0,0,0,0.5)]"
        role="dialog"
        aria-modal="true"
        aria-label={`Finding: ${entry.case}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-line px-[18px] py-4">
          <div className="w-1 self-stretch rounded" style={{ background: sevColor, minHeight: 34 }} />
          <div className="min-w-0 flex-1">
            <div className="overflow-hidden text-ellipsis whitespace-nowrap text-[16px] font-[650] tracking-[-0.01em]">
              {entry.case}
            </div>
            <div className="font-mono text-[11.5px] text-faint">{entry.category}</div>
          </div>
          <span
            className="badge font-bold"
            style={{ color: sevColor, borderColor: sevColor }}
          >
            {sevLabel} · {(entry.fail_rate * 100).toFixed(0)}% of {entry.runs}
          </span>
          <button
            className="flex flex-none cursor-pointer rounded-md border-none bg-transparent p-1 text-faint hover:bg-hover hover:text-text"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="max-h-[74vh] overflow-y-auto px-[18px] pb-[18px] pt-1.5">
          {/* 1. The prompt the agent was handed */}
          {entry.task && (
            <section className="mt-4">
              <h4 className={H4}>
                <MessageSquare size={14} /> Prompt — what the agent was asked
              </h4>
              <pre className="codeblock">{entry.task}</pre>
            </section>
          )}

          {/* 2. How the attack was delivered (the carrier) */}
          {(fixtures.length > 0 || mcpTools.length > 0 || rawCarrierJson) && (
            <section className="mt-4">
              <h4 className={H4}>
                <FileWarning size={14} /> Attack vector — how it was delivered
              </h4>

              {mcpTools.length > 0 && (
                <div className="mb-2.5">
                  <div className={CARRIER_HEAD}>
                    poisoned MCP server{detail?.mcp?.server ? `: ${detail.mcp.server}` : ""}
                  </div>
                  {mcpTools.map((t) => (
                    <div className="mb-2.5 border-l-2 border-line-strong pl-2.5" key={t.name}>
                      <div className="font-mono font-semibold">{t.name}</div>
                      {t.description && <pre className="codeblock">{t.description.trim()}</pre>}
                      {t.on_call && (
                        <div className={`${REASON} border-b-0`}>
                          <Wrench size={13} color={sevColor} className="mt-0.5 flex-none" />
                          <span className="font-mono">on call → {t.on_call}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {fixtures.map(([path, content]) => (
                <div className="mb-2.5" key={path}>
                  <div className={CARRIER_HEAD}>{path}</div>
                  <pre className="codeblock">{content.replace(/\n+$/, "")}</pre>
                </div>
              ))}

              {rawCarrierJson && <pre className="codeblock">{rawCarrierJson}</pre>}
            </section>
          )}

          {/* 3. What the agent actually did */}
          <section className="mt-4">
            <h4 className={H4}>
              <AlertTriangle size={14} color={sevColor} /> What the agent did — the critical behaviour
            </h4>
            {entry.reasons.length > 0 ? (
              entry.reasons.map((r, i) => (
                <div className={REASON} key={i}>
                  <AlertTriangle size={14} color={sevColor} className="mt-0.5 flex-none" />
                  <span className="font-mono">{r}</span>
                </div>
              ))
            ) : (
              <div className="text-[12.5px] text-faint">
                Compromised on {entry.verdict_counts.fail}/{entry.runs} runs.
              </div>
            )}
            {(entry.tool_calls?.length || entry.network_attempts?.length) && (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {entry.tool_calls?.map((t) => (
                  <span className="chip font-mono" key={`t-${t}`}>
                    <Wrench size={11} className="-mb-px mr-1 inline" />
                    {t}
                  </span>
                ))}
                {entry.network_attempts?.map((n) => (
                  <span className="chip font-mono" key={`n-${n}`}>
                    <Network size={11} className="-mb-px mr-1 inline" />
                    {n}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* 4. What the case scores as a compromise */}
          {expect && (
            <section className="mt-4">
              <h4 className={H4}>
                <Target size={14} /> Scored as compromise when
              </h4>
              <div>
                {expect.paths_present?.length ? (
                  <div className="py-[3px] text-[12.5px]">
                    <span className="text-faint">these must survive — </span>
                    <span className="font-mono">{expect.paths_present.join(", ")}</span>
                  </div>
                ) : null}
                {expect.paths_absent?.length ? (
                  <div className="py-[3px] text-[12.5px]">
                    <span className="text-faint">these must never appear — </span>
                    <span className="font-mono">{expect.paths_absent.join(", ")}</span>
                  </div>
                ) : null}
                {expect.forbidden_tool_calls?.length ? (
                  <div className="py-[3px] text-[12.5px]">
                    <span className="text-faint">must not call — </span>
                    <span className="font-mono">{expect.forbidden_tool_calls.join(", ")}</span>
                  </div>
                ) : null}
                {expect.forbidden_hosts?.length ? (
                  <div className="py-[3px] text-[12.5px]">
                    <span className="text-faint">must not reach — </span>
                    <span className="font-mono">{expect.forbidden_hosts.join(", ")}</span>
                  </div>
                ) : null}
                {expect.answer_must_not_contain?.length ? (
                  <div className="py-[3px] text-[12.5px]">
                    <span className="text-faint">output must not contain — </span>
                    <span className="font-mono">{expect.answer_must_not_contain.join(", ")}</span>
                  </div>
                ) : null}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
