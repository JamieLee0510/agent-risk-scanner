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
    rag: dict | None = None  # poisoned knowledge base (rag/* cases)
    expect_paths_present: list[str] = field(default_factory=list)
    expect_paths_absent: list[str] = field(default_factory=list)
    expect_answer_must_not_contain: list[str] = field(default_factory=list)
    expect_forbidden_tool_calls: list[str] = field(default_factory=list)


@dataclass
class Observation:
    exit_code: int
    agent_stdout: str
    agent_stderr: str
    paths_deleted: set[str]
    paths_created: set[str]
    paths_modified: set[str]
    # MCP interception (v0.3) — populated from .mcp/intercept.log when the case
    # has an mcp/rag spec; empty/false otherwise.
    tool_calls: list[str] = field(default_factory=list)
    mcp_connected: bool = False
    mcp_tools_listed: bool = False


@dataclass
class CaseResult:
    case: Case
    observation: Observation
    verdict: Verdict
    reasons: list[str]
