from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from .schema import AgentConfig, Case, Observation

# README network vocabulary -> docker `--network` values.
_DOCKER_NETWORK = {"blocked": "none", "open": "bridge"}

# `runtime:` value -> base image the synthesized Dockerfile builds from.
_RUNTIME_BASE = {
    "python": "python:3.12-slim",
    "node": "node:22-slim",
}


def _env_args(env: list[str]) -> list[str]:
    """Expand ["FOO", "BAR"] into ["-e", "FOO", "-e", "BAR"] for `docker run`.

    A bare `-e NAME` (no `=value`) tells docker to forward that variable from
    the harness's own environment, so secrets like OPENAI_API_KEY are passed
    through without ever being written to a file.
    """
    args: list[str] = []
    for name in env:
        args += ["-e", name]
    return args


def _generate_dockerfile(agent: AgentConfig) -> str:
    """Synthesize a Dockerfile from the agent.yaml fields.

    The tester never writes a Dockerfile: they declare a runtime, point at
    their code, and optionally list setup commands. The scanner turns that
    into an image. The agent always runs as a non-root user.
    """
    if agent.runtime not in _RUNTIME_BASE:
        raise ValueError(
            f"unknown runtime {agent.runtime!r}; supported: {sorted(_RUNTIME_BASE)}"
        )
    setup = list(agent.setup)
    lines = [
        f"FROM {_RUNTIME_BASE[agent.runtime]}",
        "RUN useradd --create-home agent",
    ]
    if agent.code is not None:
        lines.append("COPY agent/ /agent/")
        if not setup:  # no explicit setup -> auto-detect a dependency manifest
            if (agent.code / "requirements.txt").is_file():
                setup = ["pip install --no-cache-dir -r /agent/requirements.txt"]
            elif (agent.code / "package.json").is_file():
                setup = ["npm install --prefix /agent"]
    lines += [f"RUN {step}" for step in setup]
    lines += [f"WORKDIR {agent.workdir}", "USER agent"]
    return "\n".join(lines) + "\n"


def build_image(agent: AgentConfig) -> str:
    """Build (or resolve) the agent's container image and return its tag."""
    if agent.image is not None:
        return agent.image  # advanced: tester brought a prebuilt image

    with tempfile.TemporaryDirectory() as ctx:
        ctx_path = Path(ctx)
        if agent.dockerfile is not None:
            # advanced escape hatch: tester supplied their own Dockerfile
            dockerfile = agent.dockerfile
            build_context = agent.dockerfile.parent
            tag_key = str(dockerfile.resolve())
        else:
            # common path: synthesize the Dockerfile from the yaml
            tag_key = _generate_dockerfile(agent)
            if agent.code is not None:
                shutil.copytree(agent.code, ctx_path / "agent")
            dockerfile = ctx_path / "Dockerfile"
            dockerfile.write_text(tag_key)
            build_context = ctx_path

        tag = "agent-risk-scanner/" + hashlib.sha1(tag_key.encode()).hexdigest()[:12]
        subprocess.run(
            ["docker", "build", "-q", "-t", tag, "-f", str(dockerfile), str(build_context)],
            check=True,
            capture_output=True,
        )
    return tag


def _snapshot(workdir: Path) -> dict[str, bytes]:
    state: dict[str, bytes] = {}
    for path in workdir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(workdir).as_posix()
            state[rel] = path.read_bytes()
    return state


def _diff(before: dict[str, bytes], after: dict[str, bytes]) -> dict[str, set[str]]:
    before_keys = set(before)
    after_keys = set(after)
    return {
        "deleted": before_keys - after_keys,
        "created": after_keys - before_keys,
        "modified": {k for k in (before_keys & after_keys) if before[k] != after[k]},
    }


def _materialize_fixtures(workdir: Path, fixtures: dict[str, str], mount_root: str) -> None:
    for path_in_container, content in fixtures.items():
        if not path_in_container.startswith(mount_root):
            raise ValueError(
                f"fixture path {path_in_container!r} is outside the agent workdir {mount_root!r}"
            )
        rel = path_in_container[len(mount_root) :].lstrip("/")
        target = workdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


# Body of the synthesized stdio JSON-RPC MCP server. The harness prepends a
# header defining SERVER_NAME and TOOLS; this body is stdlib-only.
_MCP_SERVER_BODY = '''
import json
import subprocess
import sys

_call_counts = {}


def _run_tool(tool):
    name = tool["name"]
    _call_counts[name] = _call_counts.get(name, 0) + 1
    if tool.get("retrieval"):
        lines = []
        for d in KB:
            lines.append("[" + d.get("id", "doc") + "]")
            lines.append(d.get("content", ""))
        return chr(10).join(lines)
    cmd = tool.get("on_call")
    after = tool.get("on_call_after", 1)
    if cmd and _call_counts[name] >= after:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return (proc.stdout + proc.stderr).strip() or "(done)"
    return tool.get("returns", "(ok)")


def _handle(method, params):
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "0.0.1"},
        }
    if method == "tools/list":
        return {"tools": [
            {"name": t["name"], "description": t.get("description", ""),
             "inputSchema": {"type": "object", "properties": {}}}
            for t in TOOLS
        ]}
    if method == "tools/call":
        tool = next((t for t in TOOLS if t["name"] == params.get("name")), None)
        if tool is None:
            return {"content": [{"type": "text", "text": "unknown tool"}], "isError": True}
        return {"content": [{"type": "text", "text": _run_tool(tool)}]}
    return None


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" not in msg:  # a notification -- no response
            continue
        result = _handle(msg.get("method"), msg.get("params") or {})
        if result is None:
            resp = {"jsonrpc": "2.0", "id": msg["id"],
                    "error": {"code": -32601, "message": "method not found"}}
        else:
            resp = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
'''


def _generate_mcp_server(mcp: dict) -> str:
    """Synthesize a self-contained stdio MCP server from a case's `mcp:` spec.

    `mcp` may carry a `kb` (knowledge base) — a `retrieval: true` tool then
    returns its documents. This is how `rag:` cases ride on the MCP machinery.
    """
    server_name = mcp.get("server", "mcp-server")
    tools = mcp.get("tools", [])
    kb = mcp.get("kb", [])
    header = (
        "# Auto-generated stdio MCP server (agent-risk-scanner harness).\n"
        f"SERVER_NAME = {server_name!r}\n"
        f"TOOLS = {tools!r}\n"
        f"KB = {kb!r}\n"
    )
    return header + _MCP_SERVER_BODY


def _rag_to_mcp(rag: dict) -> dict:
    """Compile a case's `rag:` knowledge base into an MCP server spec whose
    `search_kb` tool retrieves the (possibly poisoned) documents."""
    return {
        "server": "knowledge-base",
        "kb": rag.get("knowledge_base", []),
        "tools": [
            {
                "name": "search_kb",
                "description": "Search the knowledge base and return matching documents.",
                "retrieval": True,
            }
        ],
    }


def _materialize_mcp_server(workdir: Path, mcp: dict, mount_root: str) -> None:
    """Write the case's poisoned MCP server + client config into .mcp/."""
    mcp_dir = workdir / ".mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "server.py").write_text(_generate_mcp_server(mcp))
    config = {"command": ["python3", f"{mount_root}/.mcp/server.py"]}
    (mcp_dir / "mcp.json").write_text(json.dumps(config))


def run_case(case: Case, agent: AgentConfig, image_tag: str, timeout: int = 60) -> Observation:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        _materialize_fixtures(workdir, case.fixtures, agent.workdir)
        if case.mcp:
            _materialize_mcp_server(workdir, case.mcp, agent.workdir)
        elif case.rag:
            _materialize_mcp_server(workdir, _rag_to_mcp(case.rag), agent.workdir)
        # the agent runs as a non-root user; make the throwaway workspace
        # fully writable so it can create / modify / delete files there
        for path in (workdir, *workdir.rglob("*")):
            path.chmod(0o777)
        before = _snapshot(workdir)

        # The agent launch command is fixed (agent-level); the task is
        # per-case, so the harness appends it as the final argv element.
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            _DOCKER_NETWORK.get(agent.network, agent.network),
            *_env_args(agent.env),
            "-v",
            f"{workdir}:{agent.workdir}",
            "-w",
            agent.workdir,
            image_tag,
            *agent.cmd,
            case.task,
        ]
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            exit_code = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired as e:
            exit_code = -1
            stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = (e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")) + "\n[harness] timeout"

        after = _snapshot(workdir)
        d = _diff(before, after)
        return Observation(
            exit_code=exit_code,
            agent_stdout=stdout,
            agent_stderr=stderr,
            paths_deleted=d["deleted"],
            paths_created=d["created"],
            paths_modified=d["modified"],
        )
