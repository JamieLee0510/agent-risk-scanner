from __future__ import annotations

import datetime
import json
from pathlib import Path

from .schema import CaseResult


def build_report(
    agent_path: Path, cases_root: Path, case_runs: list[list[CaseResult]]
) -> dict:
    """Aggregate per-case results into a serializable report dict.

    `case_runs` is one inner list per case, holding that case's N repeated
    runs. Each report entry carries the verdict distribution across those runs
    plus a `fail_rate` -- LLM agents are non-deterministic, so a hit-rate is
    the meaningful measurement, not a single verdict. `kind` is kept so a
    reader can interpret a fail: on an `attack` case it means the agent was
    compromised; on a `benign` case it is a false positive.
    """
    case_entries = []
    total_runs = 0
    cases_with_fail = 0
    for runs in case_runs:
        n = len(runs)
        total_runs += n
        verdicts = [r.verdict for r in runs]
        counts = {v: verdicts.count(v) for v in ("pass", "fail", "inconclusive", "error")}
        if counts["fail"]:
            cases_with_fail += 1
        case = runs[0].case
        entry = {
            "case": case.name,
            "category": case.category,
            "kind": case.kind,
            "runs": n,
            "verdict_counts": counts,
            "fail_rate": round(counts["fail"] / n, 3) if n else 0.0,
            "reasons": sorted({reason for r in runs for reason in r.reasons}),
        }
        # MCP interception detail (union across runs), only for mcp cases.
        if case.mcp:
            entry["tool_calls"] = sorted({t for r in runs for t in r.observation.tool_calls})
        # Egress observer detail: union of host:port attempted across runs.
        attempts = [(a.get("host"), a.get("port")) for r in runs for a in r.observation.network_attempts]
        if attempts:
            entry["network_attempts"] = sorted({f"{h}:{p}" for h, p in attempts if h})
        case_entries.append(entry)
    return {
        "agent": str(agent_path),
        "cases_root": str(cases_root),
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "summary": {
            "cases": len(case_runs),
            "runs_per_case": len(case_runs[0]) if case_runs else 0,
            "total_runs": total_runs,
            "cases_with_fail": cases_with_fail,
        },
        "results": case_entries,
    }


def _verdict_breakdown(counts: dict) -> str:
    """'fail 4/5, pass 1/5' style cell from a verdict_counts dict."""
    total = sum(counts.values())
    parts = [f"{v} {counts[v]}/{total}" for v in ("fail", "pass", "inconclusive", "error") if counts.get(v)]
    return ", ".join(parts) or "-"


def render_summary_md(report: dict, gate_result: dict | None = None) -> str:
    """Render a scan report as GitHub-flavoured markdown for $GITHUB_STEP_SUMMARY.

    Pure function of the serializable report (plus an optional plain-dict view
    of the gate decision) -- no I/O, no docker, no `policy` import, so it stays
    trivially testable and the report/policy layers stay decoupled. The
    optional `gate_result` carries the key lists (`blocking` / `waived` /
    `improved` / `error_cases`) so each row can be labelled with its gate
    status; without it, rows fall back to a fail-rate-only status.
    """
    g = gate_result or {}
    blocking = set(g.get("blocking", []))
    waived = set(g.get("waived", []))
    improved = set(g.get("improved", []))
    errored = set(g.get("error_cases", []))

    def status_for(key: str, fail_rate: float, counts: dict) -> tuple[int, str]:
        # returns (sort_rank, label); lower rank sorts first
        if key in blocking:
            return 0, "🔴 blocking"
        if key in errored:
            return 1, "⚠️ error"
        if key in waived:
            return 2, "➖ waived"
        if key in improved:
            return 3, "🟢 improved"
        if fail_rate > 0:
            return 1, "⚠️ fail"
        return 4, "✅ pass"

    rows = []
    for e in report.get("results", []):
        key = f"{e['category']}/{e['case']}"
        counts = e.get("verdict_counts", {})
        rank, label = status_for(key, float(e.get("fail_rate", 0.0)), counts)
        rows.append((rank, e["case"], e["category"], e.get("kind", "attack"),
                     e.get("fail_rate", 0.0), _verdict_breakdown(counts), label))
    rows.sort(key=lambda r: (r[0], r[1]))

    lines: list[str] = ["## Agent Risk Scanner"]
    corpus = g.get("corpus_version") or report.get("corpus_version")
    if corpus:
        lines.append(f"corpus_version: `{corpus}`")
    if "exit_code" in g:
        verdict = {0: "✅ **PASS**", 1: "🔴 **FAIL — security findings block this change**",
                   2: "⚠️ **ERROR — run did not complete cleanly**"}.get(g["exit_code"], "?")
        lines.append(f"{verdict}  (exit {g['exit_code']})")
    s = report.get("summary", {})
    if s:
        lines.append(
            f"{s.get('cases', 0)} cases × {s.get('runs_per_case', 0)} run(s) — "
            f"{s.get('cases_with_fail', 0)} with ≥1 fail"
        )
    lines.append("")
    lines.append("| Status | Case | Category | Kind | Fail rate | Verdicts |")
    lines.append("|---|---|---|---|---|---|")
    for _, case, category, kind, fail_rate, breakdown, label in rows:
        lines.append(f"| {label} | {case} | {category} | {kind} | {fail_rate} | {breakdown} |")
    return "\n".join(lines) + "\n"


def timestamped_path(path: Path) -> Path:
    """Insert the current date and time into a report filename, before the
    extension: `report.json` -> `report-20260521-143022.json`."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}-{stamp}{path.suffix}")


def write_report(report: dict, output: Path) -> None:
    """Write the report dict to `output` as indented JSON."""
    output.write_text(json.dumps(report, indent=2) + "\n")


# The vendored single-file dashboard (built from report-viewer/, see
# pyproject's package-data) carries this quoted placeholder; render_html_report
# swaps it for the report JSON so `window.__REPORT__` becomes the live data.
HTML_TEMPLATE = Path(__file__).resolve().parent / "report_template.html"
_REPORT_PLACEHOLDER = '"__ARS_REPORT_PLACEHOLDER__"'


def render_html_report(report: dict) -> str:
    """Bake `report` into the self-contained dashboard, returning one HTML string
    that renders offline (no server, no companion JSON). Mirrors garak's
    report_digest.build_html: read the built template, string-replace a marker
    with the JSON payload."""
    template = HTML_TEMPLATE.read_text()
    if _REPORT_PLACEHOLDER not in template:
        raise RuntimeError(
            f"report template {HTML_TEMPLATE} is missing the "
            f"{_REPORT_PLACEHOLDER} marker -- rebuild report-viewer "
            "(npm run build) and re-copy dist/index.html over it."
        )
    # Escape `</` so a report string containing "</script>" can't break out of
    # the inline <script>; `<\/` is an equivalent escape inside a JS string.
    payload = json.dumps(report).replace("</", "<\\/")
    # replace(count=1): exactly one full-literal marker exists (the guard's
    # equality check uses a split literal that doesn't match this token).
    return template.replace(_REPORT_PLACEHOLDER, payload, 1)
