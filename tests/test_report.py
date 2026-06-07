"""Report aggregation — `build_report` collapses N repeated runs per case
into a single entry with a fail-rate. Wrong aggregation = wrong KPI."""

from __future__ import annotations

import json
from pathlib import Path

from agent_risk_scanner.report import (
    build_report,
    render_html_report,
    render_summary_md,
    timestamped_path,
)
from agent_risk_scanner.schema import Case, CaseResult, Observation


def _obs(**overrides) -> Observation:
    defaults = {
        "exit_code": 0,
        "agent_stdout": "",
        "agent_stderr": "",
        "paths_deleted": set(),
        "paths_created": set(),
        "paths_modified": set(),
    }
    defaults.update(overrides)
    return Observation(**defaults)


def _case(name="t", mcp=None):
    return Case(name=name, category="cat", task="t", fixtures={}, mcp=mcp)


def _result(case, verdict="pass", reasons=None, obs=None):
    return CaseResult(
        case=case,
        observation=obs or _obs(),
        verdict=verdict,
        reasons=reasons or [],
    )


def test_summary_counts_repeated_runs():
    case = _case()
    runs = [_result(case, "pass"), _result(case, "fail", ["x"]), _result(case, "pass")]
    report = build_report(Path("agent.yaml"), Path("cases/"), [runs])
    assert report["summary"]["cases"] == 1
    assert report["summary"]["runs_per_case"] == 3
    assert report["summary"]["total_runs"] == 3
    assert report["summary"]["cases_with_fail"] == 1


def test_per_case_fail_rate_is_a_ratio():
    """4 fails out of 5 runs = 0.8 — the meaningful KPI for non-deterministic
    LLM agents."""
    case = _case()
    runs = [_result(case, "fail")] * 4 + [_result(case, "pass")]
    report = build_report(Path("a"), Path("c"), [runs])
    entry = report["results"][0]
    assert entry["verdict_counts"] == {"pass": 1, "fail": 4, "inconclusive": 0, "error": 0}
    assert entry["fail_rate"] == 0.8
    assert entry["runs"] == 5


def test_reasons_are_deduped_across_runs():
    case = _case()
    runs = [
        _result(case, "fail", reasons=["A"]),
        _result(case, "fail", reasons=["A", "B"]),
    ]
    entry = build_report(Path("a"), Path("c"), [runs])["results"][0]
    assert entry["reasons"] == ["A", "B"]


def test_mcp_case_includes_tool_call_union():
    """Across runs, the tool_calls report field is a sorted union — gives a
    reviewer the full attack surface the agent touched over N runs."""
    case = _case(mcp={"server": "x", "tools": []})
    obs1 = _obs(tool_calls=["a", "b"])
    obs2 = _obs(tool_calls=["b", "c"])
    runs = [_result(case, "pass", obs=obs1), _result(case, "pass", obs=obs2)]
    entry = build_report(Path("a"), Path("c"), [runs])["results"][0]
    assert entry["tool_calls"] == ["a", "b", "c"]


def test_non_mcp_case_omits_tool_calls_field():
    case = _case()  # no mcp
    runs = [_result(case, "pass")]
    entry = build_report(Path("a"), Path("c"), [runs])["results"][0]
    assert "tool_calls" not in entry


def test_network_attempts_aggregated_when_present():
    case = _case()
    obs = _obs(network_attempts=[{"host": "evil.example", "port": 80}])
    runs = [_result(case, "fail", obs=obs)]
    entry = build_report(Path("a"), Path("c"), [runs])["results"][0]
    assert entry["network_attempts"] == ["evil.example:80"]


def test_network_attempts_omitted_when_none():
    case = _case()
    runs = [_result(case, "pass")]
    entry = build_report(Path("a"), Path("c"), [runs])["results"][0]
    assert "network_attempts" not in entry


def test_render_summary_md_lists_cases_and_header():
    case = _case(name="ipi_rm")
    runs = [_result(case, "fail")] * 4 + [_result(case, "pass")]
    report = build_report(Path("a"), Path("c"), [runs])
    md = render_summary_md(report)
    assert "## Agent Risk Scanner" in md
    assert "| Status | Case |" in md  # table header
    assert "ipi_rm" in md
    assert "0.8" in md  # fail_rate cell


def test_render_summary_md_marks_blocking_and_verdict_from_gate():
    case = _case(name="bad")
    runs = [_result(case, "fail")]
    report = build_report(Path("a"), Path("c"), [runs])
    gate = {"exit_code": 1, "corpus_version": "2026-06-04", "blocking": ["cat/bad"]}
    md = render_summary_md(report, gate)
    assert "blocking" in md
    assert "exit 1" in md
    assert "2026-06-04" in md


def test_render_summary_md_empty_results_is_valid_table():
    report = build_report(Path("a"), Path("c"), [])
    md = render_summary_md(report)
    # header rows present, no data rows, no exception
    assert "| Status | Case |" in md
    assert md.endswith("\n")


def test_timestamped_path_inserts_stamp_before_extension():
    p = timestamped_path(Path("report.json"))
    assert p.stem.startswith("report-")
    assert p.suffix == ".json"
    # YYYYMMDD-HHMMSS = 15 chars + leading hyphen
    assert len(p.stem) == len("report") + 1 + 15


def _extract_embedded_report(html: str) -> dict:
    """Pull the JSON the template baked into `var data = {...};` back out, so a
    test can assert on the live payload the dashboard will read."""
    marker = "var data = "
    start = html.index(marker) + len(marker)
    # The injected payload is a JSON object literal terminated by `;` -- match
    # braces to find its end (string fields may contain `;`/`}`, but never an
    # unescaped brace).
    depth, i = 0, start
    for i in range(start, len(html)):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
    return json.loads(html[start : i + 1].replace("<\\/", "</"))


def test_render_html_report_bakes_report_and_drops_placeholder():
    report = build_report(Path("a"), Path("c"), [[_result(_case(name="bad"), "fail")]])
    html = render_html_report(report)
    # the un-baked marker must be gone, and the live data recoverable + faithful
    assert "__ARS_REPORT_PLACEHOLDER__" not in html
    assert _extract_embedded_report(html) == report


def test_render_html_report_escapes_script_close_to_prevent_breakout():
    # A report string containing "</script>" must not terminate the inline
    # <script> early -- it has to be escaped to <\/script>.
    case = _case(name="x")
    runs = [_result(case, "fail", reasons=["pwn </script><img src=x>"])]
    report = build_report(Path("a"), Path("c"), [runs])
    html = render_html_report(report)
    assert "</script><img" not in html
    assert "<\\/script>" in html
    # ...and it still round-trips to the original value
    assert _extract_embedded_report(html) == report
