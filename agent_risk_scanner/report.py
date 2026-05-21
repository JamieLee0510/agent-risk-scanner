from __future__ import annotations

import datetime
import json
from pathlib import Path

from .schema import CaseResult


def build_report(agent_path: Path, cases_root: Path, results: list[CaseResult]) -> dict:
    """Aggregate a list of per-case results into a serializable report dict.

    `summary` counts cases by verdict. Each `results` entry carries the verdict
    plus enough observation detail to see why -- the reasons and the filesystem
    diff. `kind` is kept so a reader can interpret a verdict: a `fail` on an
    `attack` case means the agent was compromised; a `fail` on a `benign` case
    is a false positive.
    """
    summary = {
        "total": len(results),
        "pass": 0,
        "fail": 0,
        "error": 0,
        "inconclusive": 0,
    }
    case_entries = []
    for r in results:
        summary[r.verdict] += 1
        obs = r.observation
        entry = {
            "case": r.case.name,
            "category": r.case.category,
            "kind": r.case.kind,
            "verdict": r.verdict,
            "reasons": r.reasons,
            "exit_code": obs.exit_code,
            "paths_deleted": sorted(obs.paths_deleted),
            "paths_created": sorted(obs.paths_created),
            "paths_modified": sorted(obs.paths_modified),
        }
        # MCP interception detail, only meaningful for mcp/rag cases.
        if r.case.mcp or r.case.rag:
            entry["mcp_connected"] = obs.mcp_connected
            entry["mcp_tools_listed"] = obs.mcp_tools_listed
            entry["tool_calls"] = obs.tool_calls
        case_entries.append(entry)
    return {
        "agent": str(agent_path),
        "cases_root": str(cases_root),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": summary,
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
