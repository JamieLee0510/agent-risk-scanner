from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import policy as policy_mod
from .harness import build_image, run_case
from .judge import judge
from .report import build_report, render_summary_md, timestamped_path, write_report
from .schema import AgentConfig, Case

# cases/ ships in the repo root, a sibling of the agent_risk_scanner package.
# A `suite` name (e.g. "prompt-injection") resolves to a subdirectory here.
# (Phase 1: filesystem resolution. Packaging cases as package data is a
# follow-up -- see specs/20260604.md §10.)
DEFAULT_CASES_ROOT = Path(__file__).resolve().parent.parent / "cases"


def load_agent_config(path: Path) -> AgentConfig:
    data = yaml.safe_load(path.read_text())
    launch = data["launch"]
    sandbox = data.get("sandbox", {})
    base = path.parent

    code = data.get("code")
    dockerfile = launch.get("dockerfile")
    capabilities = data.get("capabilities", {})

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
        supports_mcp=bool(capabilities.get("mcp", False)),
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


def _requires_mcp(case: Case) -> bool:
    """A case needs an MCP client iff it ships a poisoned MCP server (`mcp:`).
    That single field covers both the mcp/ and agentic/ families -- the latter
    ride on the same interception layer."""
    return case.mcp is not None


def _filter_exposable(case_paths: list[Path], agent: AgentConfig) -> list[Case]:
    """Load cases, dropping those the agent structurally can't be exposed to
    (MCP cases against an agent with no MCP client), so reports/gates aren't
    padded with `inconclusive`."""
    cases, skipped = [], []
    for path in case_paths:
        c = load_case(path)
        (skipped if (_requires_mcp(c) and not agent.supports_mcp) else cases).append(c)
    if skipped:
        print(
            f"[harness] skipping {len(skipped)} MCP-dependent case(s) "
            "(agent.capabilities.mcp=false): " + ", ".join(c.name for c in skipped)
        )
    return cases


def _run_cases(
    cases: list[Case], agent: AgentConfig, tag: str, n: int, timeout: int
) -> list[list]:
    """Run each case n times, printing a one-line hit-rate per case. Returns
    one inner list of CaseResults per case (the shape build_report wants)."""
    case_runs = []
    for case in cases:
        runs = [
            judge(case, run_case(case, agent, tag, timeout=timeout), mount_root=agent.workdir)
            for _ in range(n)
        ]
        counts = _verdict_counts(runs)
        c = _counts_color(counts)
        print(f"  {c}{_fmt_counts(counts, n):26}{_reset()} {case.name}  ({case.category})")
        case_runs.append(runs)
    return case_runs


def _resolve_suites(cases_root: Path, suites: list[str]) -> list[Path]:
    """Map suite names to case yaml paths under cases_root. An empty `suites`
    means the whole corpus. A missing suite directory is a hard error -- a
    typo'd suite must not silently shrink a gate's coverage."""
    if not suites:
        return sorted(cases_root.rglob("*.yaml"))
    paths: list[Path] = []
    for suite in suites:
        suite_dir = cases_root / suite
        if not suite_dir.is_dir():
            raise FileNotFoundError(
                f"suite {suite!r} not found under {cases_root} "
                f"(expected directory {suite_dir})"
            )
        paths += sorted(suite_dir.rglob("*.yaml"))
    return paths


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

    if _requires_mcp(case) and not agent.supports_mcp:
        print(
            f"[harness] skipping {case.name}: it needs an MCP client, but the "
            "agent declares capabilities.mcp=false (no MCP client). Set "
            "capabilities.mcp: true in agent.yaml to test MCP security."
        )
        return 0

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
    cases = _filter_exposable(case_paths, agent)

    note = f" ({n} runs each)" if n > 1 else ""
    print(f"[harness] running {len(cases)} cases from {args.cases}{note}")
    print()

    case_runs = _run_cases(cases, agent, tag, n, args.timeout)

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


def _scan_for_policy(
    agent_path: Path, policy: policy_mod.Policy, cases_root: Path, timeout: int
) -> dict:
    """Build the image and run every case in the policy's suites, returning a
    report dict. Shared by `gate` and `baseline` so they measure identically."""
    agent = load_agent_config(agent_path)
    suites = policy_mod.effective_suites(policy)
    case_paths = _resolve_suites(cases_root, suites)
    if not case_paths:
        raise FileNotFoundError(f"no cases found for suites {suites} under {cases_root}")
    n = max(1, policy.repeat)
    print(f"[harness] building image for {agent_path} (runtime: {agent.runtime})")
    tag = build_image(agent)
    print(f"[harness] image tag: {tag}")
    print(f"[harness] corpus_version: {policy.corpus_version}")
    cases = _filter_exposable(case_paths, agent)
    suites_note = ", ".join(suites) if suites else "all"
    print(
        f"[harness] running {len(cases)} cases [tier={policy.tier}: {suites_note}] "
        f"x {n} run(s) each"
    )
    print()
    case_runs = _run_cases(cases, agent, tag, n, timeout)
    return build_report(agent_path, cases_root, case_runs)


def cmd_gate(args: argparse.Namespace) -> int:
    """CI gate: scan, apply policy + baseline, return a CI exit code.

    0 = pass, 1 = security failure (block PR), 2 = infra error. This is the
    one command CI keys off (see specs/20260604.md §1)."""
    policy = policy_mod.load_policy(args.policy)

    # Reproducibility guard (§4): the corpus actually on disk must match the
    # version the policy pinned, else the gate's verdict isn't reproducible. A
    # mismatch is an infra/config failure (exit 2), not "the agent is unsafe".
    actual_corpus = policy_mod.read_corpus_version(args.cases_root)
    if actual_corpus is not None and actual_corpus != policy.corpus_version:
        print(
            f"[gate] ERROR: corpus on disk is {actual_corpus!r} but policy pins "
            f"corpus_version {policy.corpus_version!r} -- refusing to run against a "
            "mismatched corpus (a gate whose corpus drifts isn't reproducible). "
            "Align the policy's corpus_version with the installed corpus."
        )
        return policy_mod.EXIT_INFRA_ERROR

    baseline = None
    if policy.baseline:
        baseline = policy_mod.load_baseline(policy.baseline)
        if baseline.corpus_version != policy.corpus_version:
            print(
                f"[gate] ERROR: baseline corpus_version {baseline.corpus_version!r} "
                f"!= policy corpus_version {policy.corpus_version!r} -- refusing to "
                "run against a mismatched baseline."
            )
            return policy_mod.EXIT_INFRA_ERROR

    report = _scan_for_policy(args.agent, policy, args.cases_root, args.timeout)
    if args.report:
        write_report(report, args.report)
        print(f"[gate] report written to {args.report}")

    result = policy_mod.evaluate(report, policy, baseline)
    _print_gate_result(result, has_baseline=baseline is not None)

    if args.summary_md:
        gate_dict = {
            "exit_code": result.exit_code,
            "corpus_version": result.corpus_version,
            "blocking": [f.key for f in result.blocking],
            "waived": [f.key for f in result.waived],
            "improved": [f.key for f in result.improved],
            "error_cases": result.error_cases,
        }
        # append (don't truncate): $GITHUB_STEP_SUMMARY may already hold output
        # from earlier steps, and clobbering it would drop their summaries.
        with open(args.summary_md, "a") as fh:
            fh.write(render_summary_md(report, gate_dict))
        print(f"[gate] step summary written to {args.summary_md}")

    return result.exit_code


def _print_gate_result(result: policy_mod.GateResult, has_baseline: bool) -> None:
    print()
    print("=" * 60)
    if result.waived:
        print(f"[gate] {len(result.waived)} waived (pre-existing, within baseline):")
        for f in result.waived:
            print(f"    ~ {f.key}  fail_rate={f.fail_rate} (accepted {f.baseline_rate})")
    if result.improved:
        print(f"[gate] {len(result.improved)} improved (below baseline -- consider re-baselining):")
        for f in result.improved:
            print(f"    ↓ {f.key}  fail_rate={f.fail_rate} < accepted {f.baseline_rate}")
    if result.error_cases:
        verb = "BLOCKING" if result.on_error == "block" else "warn-only"
        print(f"[gate] {len(result.error_cases)} case(s) errored/inconclusive ({verb}):")
        for k in result.error_cases:
            print(f"    ! {k}")

    if result.blocking:
        print(f"\n[gate] {_counts_color({'fail': 1, 'inconclusive': 0, 'error': 0})}"
              f"{len(result.blocking)} BLOCKING finding(s){_reset()}:")
        for f in result.blocking:
            base = "new" if f.baseline_rate is None else f"regressed from {f.baseline_rate}"
            print(f"    ✗ {f.key}  [{f.kind}] fail_rate={f.fail_rate} "
                  f"> threshold {f.threshold}  ({base})")

    code = result.exit_code
    if code == policy_mod.EXIT_PASS:
        msg = "PASS -- no new findings beyond policy/baseline"
        color = "\033[32m"
    elif code == policy_mod.EXIT_SECURITY_FAIL:
        msg = "FAIL -- security findings block this change"
        color = "\033[31m"
    else:
        msg = "ERROR -- infrastructure/agent run did not complete cleanly"
        color = "\033[33m"
    print(f"\n[gate] {color}{msg}{_reset()}  (exit {code})")
    if result.blocking and not has_baseline:
        print("[gate] tip: run `agent-risk-scan baseline` to accept existing "
              "findings, then the gate only blocks NEW regressions.")


def cmd_baseline(args: argparse.Namespace) -> int:
    """Accept the agent's current findings as a baseline. After this, `gate`
    passes on today's state and only fires on regressions (specs/20260604.md §3)."""
    policy = policy_mod.load_policy(args.policy)
    report = _scan_for_policy(args.agent, policy, args.cases_root, args.timeout)
    doc = policy_mod.baseline_from_report(report, policy)
    args.out.write_text(json.dumps(doc, indent=2) + "\n")
    print()
    print(f"[baseline] accepted {len(doc['accepted'])} existing finding(s) "
          f"-> {args.out}")
    print(f"[baseline] corpus_version: {policy.corpus_version}")
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

    gate_p = sub.add_parser(
        "gate",
        help="CI gate: scan per policy + baseline, exit 0 (pass) / 1 (security "
        "fail) / 2 (infra error)",
    )
    gate_p.add_argument("--agent", type=Path, required=True, help="path to agent.yaml")
    gate_p.add_argument(
        "--policy", type=Path, required=True, help="path to agent-risk.policy.yaml"
    )
    gate_p.add_argument(
        "--cases-root", type=Path, default=DEFAULT_CASES_ROOT,
        help="root directory the policy's suite names resolve under "
        f"(default: bundled corpus at {DEFAULT_CASES_ROOT})",
    )
    gate_p.add_argument(
        "--report", type=Path, default=None,
        help="optional: also write the full JSON report here",
    )
    gate_p.add_argument(
        "--summary-md", type=Path, default=None, dest="summary_md",
        help="optional: append a markdown findings table here (point at "
        "$GITHUB_STEP_SUMMARY in CI to surface results on the PR)",
    )
    gate_p.add_argument("--timeout", type=int, default=60)

    base_p = sub.add_parser(
        "baseline",
        help="accept the agent's current findings as a baseline so the gate "
        "only blocks regressions",
    )
    base_p.add_argument("--agent", type=Path, required=True, help="path to agent.yaml")
    base_p.add_argument(
        "--policy", type=Path, required=True, help="path to agent-risk.policy.yaml"
    )
    base_p.add_argument(
        "--cases-root", type=Path, default=DEFAULT_CASES_ROOT,
        help="root directory the policy's suite names resolve under",
    )
    base_p.add_argument(
        "--out", type=Path, default=Path(".agent-risk-baseline.json"),
        help="where to write the baseline (default: .agent-risk-baseline.json)",
    )
    base_p.add_argument("--timeout", type=int, default=60)

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "gate":
        return cmd_gate(args)
    if args.cmd == "baseline":
        return cmd_baseline(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
