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
    summary = {"total": len(results), "pass": 0, "fail": 0, "error": 0}
    case_entries = []
    for r in results:
        summary[r.verdict] += 1
        obs = r.observation
        case_entries.append(
            {
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
        )
    return {
        "agent": str(agent_path),
        "cases_root": str(cases_root),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": summary,
        "results": case_entries,
    }


def write_report(report: dict, output: Path) -> None:
    """Write the report dict to `output` as indented JSON."""
    output.write_text(json.dumps(report, indent=2) + "\n")
