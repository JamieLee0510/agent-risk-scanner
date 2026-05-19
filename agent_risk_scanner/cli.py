from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .harness import build_image, run_case
from .judge import judge
from .schema import AgentConfig, Case


def load_agent_config(path: Path) -> AgentConfig:
    data = yaml.safe_load(path.read_text())
    launch = data["launch"]
    sandbox = data.get("sandbox", {})
    base = path.parent

    code = data.get("code")
    dockerfile = launch.get("dockerfile")
    return AgentConfig(
        cmd=launch["cmd"],
        runtime=data.get("runtime", "python"),
        code=(base / code).resolve() if code is not None else None,
        setup=data.get("setup", []),
        env=launch.get("env", []),
        network=sandbox.get("network", "blocked"),
        workdir=sandbox.get("workdir", "/workspace"),
        dockerfile=(base / dockerfile).resolve() if dockerfile is not None else None,
        image=launch.get("image"),
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
        expect_paths_present=expect.get("paths_present", []),
        expect_paths_absent=expect.get("paths_absent", []),
    )


def _verdict_color(verdict: str) -> str:
    return {"pass": "\033[32m", "fail": "\033[31m", "error": "\033[33m"}.get(verdict, "")


def _reset() -> str:
    return "\033[0m"


def cmd_run(args: argparse.Namespace) -> int:
    agent = load_agent_config(args.agent)
    case = load_case(args.case)

    print(f"[harness] building image for {args.agent} (runtime: {agent.runtime})")
    tag = build_image(agent)
    print(f"[harness] image tag: {tag}")
    print(f"[harness] running case: {case.name} ({case.category})")
    obs = run_case(case, agent, tag, timeout=args.timeout)
    result = judge(case, obs, mount_root=agent.workdir)

    print()
    c = _verdict_color(result.verdict)
    print(f"  case:    {case.name}")
    print(f"  verdict: {c}{result.verdict.upper()}{_reset()}")
    if result.verdict == "fail":
        print("           (the agent fell for the attack)")
    elif result.verdict == "pass":
        print("           (the agent resisted the attack, or did nothing observable)")
    for r in result.reasons:
        print(f"    - {r}")

    print()
    print(f"  exit code:      {obs.exit_code}")
    print(f"  paths deleted:  {sorted(obs.paths_deleted) or '(none)'}")
    print(f"  paths created:  {sorted(obs.paths_created) or '(none)'}")
    print(f"  paths modified: {sorted(obs.paths_modified) or '(none)'}")
    if obs.agent_stdout.strip():
        print(f"  agent stdout:   {obs.agent_stdout.strip()[:300]}")
    if obs.agent_stderr.strip():
        print(f"  agent stderr:   {obs.agent_stderr.strip()[:300]}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-risk-scan")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run a single case against an agent")
    run_p.add_argument("--agent", type=Path, required=True, help="path to agent.yaml")
    run_p.add_argument("--case", type=Path, required=True, help="path to case yaml")
    run_p.add_argument("--timeout", type=int, default=60)

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
