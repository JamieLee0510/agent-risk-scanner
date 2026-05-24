from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .harness import build_image, run_case
from .judge import judge
from .report import build_report, timestamped_path, write_report
from .schema import AgentConfig, Case


def load_agent_config(path: Path) -> AgentConfig:
    data = yaml.safe_load(path.read_text())
    launch = data["launch"]
    sandbox = data.get("sandbox", {})
    base = path.parent

    code = data.get("code")
    dockerfile = launch.get("dockerfile")

    # config: copy the user's real behavioural config into the sandbox so the
    # scan tests their configured deployment, not a vanilla install.
    config_entries: list[tuple[str, str]] = []
    for item in data.get("config", []):
        src = Path(item["from"]).expanduser()
        if not src.is_absolute():
            src = base / src
        config_entries.append((str(src.resolve()), item["to"]))

    cmd = launch["cmd"]
    if config_entries and "--bare" in cmd:
        raise ValueError(
            "agent.yaml: `config:` scans the configured deployment, but "
            "`--bare` strips config discovery (CLAUDE.md, etc.) -- the two "
            "contradict. Remove --bare to scan with config, or drop config "
            "for a vanilla baseline scan."
        )

    return AgentConfig(
        cmd=cmd,
        runtime=data.get("runtime", "python"),
        code=(base / code).resolve() if code is not None else None,
        setup=data.get("setup", []),
        env=launch.get("env", []),
        network=sandbox.get("network", "blocked"),
        workdir=sandbox.get("workdir", "/workspace"),
        dockerfile=(base / dockerfile).resolve() if dockerfile is not None else None,
        image=launch.get("image"),
        config=config_entries,
        observe_network=bool(sandbox.get("observe_network", False)),
    )


def load_case(path: Path) -> Case:
    data = yaml.safe_load(path.read_text())
    expect = data.get("expect", {})
    return Case(
        name=data["name"],
        category=data["category"],
        task=data["task"],
        fixtures=data.get("fixtures", {}),
        kind=data.get("kind", "attack"),
        mcp=data.get("mcp"),
        web=data.get("web"),
        expect_paths_present=expect.get("paths_present", []),
        expect_paths_absent=expect.get("paths_absent", []),
        expect_answer_must_not_contain=expect.get("answer_must_not_contain", []),
        expect_forbidden_tool_calls=expect.get("forbidden_tool_calls", []),
        expect_forbidden_hosts=expect.get("forbidden_hosts", []),
    )


def _verdict_color(verdict: str) -> str:
    return {
        "pass": "\033[32m",
        "fail": "\033[31m",
        "error": "\033[33m",
        "inconclusive": "\033[33m",
    }.get(verdict, "")


def _reset() -> str:
    return "\033[0m"


_VERDICTS = ("fail", "pass", "inconclusive", "error")


def _verdict_counts(results: list) -> dict[str, int]:
    verdicts = [r.verdict for r in results]
    return {v: verdicts.count(v) for v in _VERDICTS}


def _counts_color(counts: dict[str, int]) -> str:
    if counts["fail"]:
        return "\033[31m"
    if counts["inconclusive"] or counts["error"]:
        return "\033[33m"
    return "\033[32m"


def _fmt_counts(counts: dict[str, int], n: int) -> str:
    """Compact verdict breakdown, e.g. 'fail 4/5, pass 1/5'."""
    parts = [f"{v} {counts[v]}/{n}" for v in _VERDICTS if counts[v]]
    return ", ".join(parts) or f"pass 0/{n}"


def _print_single(case: Case, result) -> None:
    obs = result.observation
    c = _verdict_color(result.verdict)
    print()
    print(f"  case:    {case.name}")
    print(f"  verdict: {c}{result.verdict.upper()}{_reset()}")
    if result.verdict == "fail":
        print("           (the agent fell for the attack)")
    elif result.verdict == "pass":
        print("           (the agent resisted the attack, or did nothing observable)")
    elif result.verdict == "inconclusive":
        print("           (the agent was not exposed to the case -- no verdict)")
    for r in result.reasons:
        print(f"    - {r}")
    print()
    print(f"  exit code:      {obs.exit_code}")
    print(f"  paths deleted:  {sorted(obs.paths_deleted) or '(none)'}")
    print(f"  paths created:  {sorted(obs.paths_created) or '(none)'}")
    print(f"  paths modified: {sorted(obs.paths_modified) or '(none)'}")
    if case.mcp:
        print(f"  mcp connected:  {obs.mcp_connected}  (tools listed: {obs.mcp_tools_listed})")
        print(f"  mcp tool calls: {obs.tool_calls or '(none)'}")
    if obs.network_attempts:
        hosts = sorted({f"{a.get('host')}:{a.get('port')}" for a in obs.network_attempts})
        print(f"  egress attempts: {hosts}")
    if obs.agent_stdout.strip():
        print(f"  agent stdout:   {obs.agent_stdout.strip()[:300]}")
    if obs.agent_stderr.strip():
        print(f"  agent stderr:   {obs.agent_stderr.strip()[:300]}")


def cmd_run(args: argparse.Namespace) -> int:
    agent = load_agent_config(args.agent)
    case = load_case(args.case)
    n = max(1, args.repeat)

    print(f"[harness] building image for {args.agent} (runtime: {agent.runtime})")
    tag = build_image(agent)
    print(f"[harness] image tag: {tag}")
    print(f"[harness] running case: {case.name} ({case.category})" + (f" x{n}" if n > 1 else ""))

    results = []
    for i in range(n):
        obs = run_case(case, agent, tag, timeout=args.timeout)
        result = judge(case, obs, mount_root=agent.workdir)
        results.append(result)
        if n > 1:
            c = _verdict_color(result.verdict)
            print(f"  run {i + 1}/{n}: {c}{result.verdict.upper()}{_reset()}")

    if n == 1:
        _print_single(case, results[0])
    else:
        # LLM agents are non-deterministic -- a single run is a coin flip, so
        # N runs give a hit-rate, the meaningful measurement.
        counts = _verdict_counts(results)
        print()
        print(f"  case:    {case.name}")
        print(f"  result:  {_counts_color(counts)}{_fmt_counts(counts, n)}{_reset()}")
        print(f"  attack success rate: {counts['fail']}/{n}")
        for r in sorted({reason for res in results for reason in res.reasons}):
            print(f"    - {r}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    agent = load_agent_config(args.agent)
    case_paths = sorted(args.cases.rglob("*.yaml"))
    if not case_paths:
        print(f"[harness] no case yaml files found under {args.cases}")
        return 1
    n = max(1, args.repeat)

    print(f"[harness] building image for {args.agent} (runtime: {agent.runtime})")
    tag = build_image(agent)
    print(f"[harness] image tag: {tag}")
    note = f" ({n} runs each)" if n > 1 else ""
    print(f"[harness] running {len(case_paths)} cases from {args.cases}{note}")
    print()

    case_runs = []  # list[list[CaseResult]] -- N runs per case
    for path in case_paths:
        case = load_case(path)
        runs = [
            judge(case, run_case(case, agent, tag, timeout=args.timeout), mount_root=agent.workdir)
            for _ in range(n)
        ]
        counts = _verdict_counts(runs)
        c = _counts_color(counts)
        print(f"  {c}{_fmt_counts(counts, n):26}{_reset()} {case.name}  ({case.category})")
        case_runs.append(runs)

    report = build_report(args.agent, args.cases, case_runs)
    output = timestamped_path(args.output)
    write_report(report, output)

    s = report["summary"]
    print()
    print(
        f"[harness] {s['cases']} cases x {s['runs_per_case']} run(s) -- "
        f"{s['cases_with_fail']} with >=1 FAIL"
    )
    print(f"[harness] report written to {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-risk-scan")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run a single case against an agent")
    run_p.add_argument("--agent", type=Path, required=True, help="path to agent.yaml")
    run_p.add_argument("--case", type=Path, required=True, help="path to case yaml")
    run_p.add_argument("--timeout", type=int, default=60)
    run_p.add_argument(
        "--repeat", type=int, default=1,
        help="run the case N times and report a hit-rate (LLM agents are non-deterministic)",
    )

    scan_p = sub.add_parser(
        "scan", help="run every case under a directory and write a JSON report"
    )
    scan_p.add_argument("--agent", type=Path, required=True, help="path to agent.yaml")
    scan_p.add_argument(
        "--cases", type=Path, required=True, help="directory of case yamls (searched recursively)"
    )
    scan_p.add_argument(
        "--output",
        type=Path,
        default=Path("report.json"),
        help="report file path; a date-time stamp is inserted before the extension "
        "(report.json -> report-20260521-143022.json)",
    )
    scan_p.add_argument("--timeout", type=int, default=60)
    scan_p.add_argument(
        "--repeat", type=int, default=1,
        help="run each case N times and report per-case hit-rates",
    )

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "scan":
        return cmd_scan(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
