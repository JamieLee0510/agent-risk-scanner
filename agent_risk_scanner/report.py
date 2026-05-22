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
        # MCP interception detail (union across runs), only for mcp/rag cases.
        if case.mcp or case.rag:
            entry["tool_calls"] = sorted({t for r in runs for t in r.observation.tool_calls})
        case_entries.append(entry)
    return {
        "agent": str(agent_path),
        "cases_root": str(cases_root),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "cases": len(case_runs),
            "runs_per_case": len(case_runs[0]) if case_runs else 0,
            "total_runs": total_runs,
            "cases_with_fail": cases_with_fail,
        },
        "results": case_entries,
    }


def timestamped_path(path: Path) -> Path:
    """Insert the current date and time into a report filename, before the
    extension: `report.json` -> `report-20260521-143022.json`."""
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}-{stamp}{path.suffix}")


def write_report(report: dict, output: Path) -> None:
    """Write the report dict to `output` as indented JSON."""
    output.write_text(json.dumps(report, indent=2) + "\n")
