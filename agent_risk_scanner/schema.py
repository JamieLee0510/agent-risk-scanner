from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Verdict = Literal["pass", "fail", "error", "inconclusive"]


@dataclass
class AgentConfig:
    cmd: list[str]
    runtime: str = "python"
    code: Path | None = None
    setup: list[str] = field(default_factory=list)
    env: list[str] = field(default_factory=list)
    network: str = "blocked"
    workdir: str = "/workspace"
    # (host_path, container_path) pairs -- the user's real behavioural config
    # (CLAUDE.md, settings.json, .mcp.json) copied into the sandbox so a scan
    # reflects their configured deployment. See specs/20260521.md section 6.
    config: list[tuple[str, str]] = field(default_factory=list)
    # Opt-in egress observer: route HTTP(S) through a logging proxy and record
    # every host:port the agent tries to reach. See specs/20260522.md §4.1.
    observe_network: bool = False
    # Does the agent have an MCP client? Default False. When False the scanner
    # skips every MCP-dependent case (anything with an `mcp:` block -- the
    # mcp/ and agentic/ families) instead of emitting a wall of `inconclusive`
    # verdicts: an agent that can't speak MCP was never exposed to the attack.
    supports_mcp: bool = False
    # Does the agent auto-discover Agent Skills (SKILL.md files)? Default False.
    # When False the scanner skips every skill case (anything with a `skill:`
    # block) instead of emitting misleading passes: a goal-only skill case is
    # only delivered if the agent actually loads the planted SKILL.md, so an
    # agent that doesn't discover skills was never exposed to the attack.
    supports_skill: bool = False
    # Where this agent discovers project-local skills, relative to the workdir
    # (e.g. ".claude/skills" for Claude Code, ".agent/skills" for go-agent-
    # harness). Required when supports_skill is True; the harness materializes a
    # case's poisoned SKILL.md at <workdir>/<skill_dir>/<name>/SKILL.md.
    skill_dir: str | None = None
    # advanced escape hatches for agents that don't fit a generic runtime
    dockerfile: Path | None = None
    image: str | None = None


@dataclass
class Case:
    name: str
    category: str
    task: str
    fixtures: dict[str, str]
    kind: str = "attack"  # attack | benign (benign = hard negative)
    mcp: dict | None = None  # poisoned MCP server spec (mcp/* cases)
    skill: dict | None = None  # poisoned Agent Skill spec (prompt-injection/skill cases)
    web: dict | None = None  # poisoned web pages served by a mock web server
    expect_paths_present: list[str] = field(default_factory=list)
    expect_paths_absent: list[str] = field(default_factory=list)
    expect_answer_must_not_contain: list[str] = field(default_factory=list)
    expect_forbidden_tool_calls: list[str] = field(default_factory=list)
    expect_forbidden_hosts: list[str] = field(default_factory=list)


@dataclass
class Observation:
    exit_code: int
    agent_stdout: str
    agent_stderr: str
    paths_deleted: set[str]
    paths_created: set[str]
    paths_modified: set[str]
    # MCP interception (v0.3) — populated from .mcp/intercept.log when the case
    # has an mcp spec; empty/false otherwise.
    tool_calls: list[str] = field(default_factory=list)
    mcp_connected: bool = False
    mcp_tools_listed: bool = False
    # Egress observer (v0): one entry per attempted outbound connection
    # captured by the HTTP(S) proxy. Each entry: {host, port, method, status}.
    network_attempts: list[dict] = field(default_factory=list)


@dataclass
class CaseResult:
    case: Case
    observation: Observation
    verdict: Verdict
    reasons: list[str]
