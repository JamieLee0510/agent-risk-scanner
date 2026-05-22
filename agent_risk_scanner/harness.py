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
    lines = [f"FROM {_RUNTIME_BASE[agent.runtime]}"]
    if agent.runtime == "node":
        # The harness scaffolding (synthesized MCP/web mock servers and their
        # launchers) is python3; node slim images don't ship it.
        lines.append(
            "RUN apt-get update && apt-get install -y --no-install-recommends "
            "python3 && rm -rf /var/lib/apt/lists/*"
        )
    lines.append("RUN useradd --create-home agent")
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
            # .mcp/ .web/ .arsconfig/ are the harness's own scaffolding (MCP
            # server + interceptor + log; mock web server; config staging) --
            # exclude so they never pollute the file diff.
            if rel.split("/", 1)[0] in (".mcp", ".web", ".arsconfig"):
                continue
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


# The MCP interception layer (v0.3). A stdio<->stdio relay the agent connects
# to instead of the mock server directly; it spawns server.py, forwards every
# JSON-RPC message verbatim, and records each one to .mcp/intercept.log so the
# harness can observe tool calls and verify the agent actually connected.
# Fully transparent (no tampering) and stdlib-only. See
# specs/20260521.md (section 3).
_MCP_INTERCEPTOR_BODY = '''
# Auto-generated stdio MCP interceptor (agent-risk-scanner harness).
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_CMD = ["python3", os.path.join(HERE, "server.py")]
LOG = os.path.join(HERE, "intercept.log")
_lock = threading.Lock()


def record(direction, msg):
    entry = {"t": round(time.time(), 3), "dir": direction}
    method = msg.get("method")
    if method:
        entry["method"] = method
        if method == "tools/call":
            params = msg.get("params") or {}
            entry["tool"] = params.get("name")
            entry["arguments"] = params.get("arguments")
    if "id" in msg:
        entry["id"] = msg["id"]
    if "error" in msg:
        entry["error"] = msg["error"]
    with _lock:
        with open(LOG, "a") as f:
            f.write(json.dumps(entry) + "\\n")


def pump(src, dst, direction):
    """Line by line: record, then forward the raw line unchanged."""
    for line in src:
        stripped = line.strip()
        if stripped:
            try:
                record(direction, json.loads(stripped))
            except json.JSONDecodeError:
                pass  # forward non-JSON too -- never break the protocol
        try:
            dst.write(line)
            dst.flush()
        except (BrokenPipeError, ValueError):
            break
    try:
        dst.close()
    except OSError:
        pass


def main():
    server = subprocess.Popen(
        SERVER_CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    )
    up = threading.Thread(
        target=pump, args=(sys.stdin, server.stdin, "agent->server")
    )
    down = threading.Thread(
        target=pump, args=(server.stdout, sys.stdout, "server->agent")
    )
    up.start()
    down.start()
    up.join()
    server.wait()
    down.join()


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
    """Write the case's poisoned MCP server, the interception layer, and the
    client config into .mcp/.

    The agent is pointed at the interceptor, not the server directly: the
    interceptor spawns server.py and relays every JSON-RPC message, recording
    them to .mcp/intercept.log (v0.3, see specs/20260521.md section 3).
    """
    mcp_dir = workdir / ".mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "server.py").write_text(_generate_mcp_server(mcp))
    (mcp_dir / "interceptor.py").write_text(_MCP_INTERCEPTOR_BODY)
    config = {"command": ["python3", f"{mount_root}/.mcp/interceptor.py"]}
    (mcp_dir / "mcp.json").write_text(json.dumps(config))


def _read_intercept_log(workdir: Path) -> dict:
    """Parse .mcp/intercept.log into the MCP fields of an Observation.

    Returns ordered tool-call names plus whether the agent completed the
    handshake (`initialize`) and enumerated tools (`tools/list`). Missing or
    malformed log => empty/false, treated as 'agent never connected'.
    """
    log = workdir / ".mcp" / "intercept.log"
    tool_calls: list[str] = []
    connected = False
    listed = False
    if not log.is_file():
        return {"tool_calls": tool_calls, "mcp_connected": False, "mcp_tools_listed": False}
    for line in log.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("dir") != "agent->server":
            continue
        method = entry.get("method")
        if method == "initialize":
            connected = True
        elif method == "tools/list":
            listed = True
        elif method == "tools/call" and entry.get("tool"):
            tool_calls.append(entry["tool"])
    return {"tool_calls": tool_calls, "mcp_connected": connected, "mcp_tools_listed": listed}


# Body of the synthesized mock web server. Serves the case's pages from
# loopback; the harness prepends a header defining PAGES and PORT. stdlib-only.
# This is how `web:` cases deliver indirect prompt injection via fetched pages
# without ever touching the real internet -- see specs/20260521.md section 5.
_MOCK_WEB_SERVER_BODY = '''
import http.server
import os
import socketserver


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # stay silent -- never write to the agent's stdout/stderr


socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("0.0.0.0", PORT), Handler)
if HTTPS:
    import ssl

    here = os.path.dirname(os.path.abspath(__file__))
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(
        os.path.join(here, "server.crt"), os.path.join(here, "server.key")
    )
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
httpd.serve_forever()
'''

# Launcher: (for https) builds a CA bundle trusting both the container's real
# roots and the mock's CA, starts the mock web server, waits for it to accept
# connections, then execs the real agent command (passed as argv).
_MOCK_WEB_LAUNCHER_BODY = '''
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

if HTTPS:
    # Trust the mock's CA without dropping the real root store: concatenate
    # the container's existing roots with our CA into one bundle, then point
    # the TLS env vars at it before the agent starts. This keeps real API
    # calls (e.g. OpenAI) verifiable while the mock's https pages are trusted.
    our_ca = open(os.path.join(HERE, "ca.pem")).read()
    roots = ""
    for path in ("/etc/ssl/certs/ca-certificates.crt", "/etc/ssl/cert.pem"):
        try:
            roots = open(path).read()
            break
        except OSError:
            pass
    bundle = os.path.join(HERE, "cabundle.pem")
    with open(bundle, "w") as f:
        f.write(roots + "\\n" + our_ca)
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        os.environ[var] = bundle
    os.environ["NODE_EXTRA_CA_CERTS"] = os.path.join(HERE, "ca.pem")

subprocess.Popen(
    ["python3", os.path.join(HERE, "server.py")],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

deadline = time.time() + 5
while time.time() < deadline:
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.3).close()
        break
    except OSError:
        time.sleep(0.1)

os.execvp(sys.argv[1], sys.argv[1:])
'''


def _web_scheme(web: dict) -> str:
    """`https` if the case's pages are served over TLS, else `http`."""
    from urllib.parse import urlparse

    pages = web.get("pages", [])
    if pages and urlparse(pages[0]["url"]).scheme == "https":
        return "https"
    return "http"


def _web_port(web: dict) -> int:
    """The port the case's pages are served on (taken from the first URL)."""
    from urllib.parse import urlparse

    pages = web.get("pages", [])
    if not pages:
        return 8080
    parsed = urlparse(pages[0]["url"])
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def _generate_web_certs(hosts: list[str]) -> dict[str, str]:
    """Generate a throwaway CA and one leaf cert (SAN = all case hosts) via the
    openssl CLI. The CA is short-lived and only ever trusted inside the
    sandbox -- it secures the mock web server, nothing real."""
    san = ",".join(f"DNS:{h}" for h in hosts) or "DNS:localhost"
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        _run = lambda *a: subprocess.run(list(a), check=True, capture_output=True)
        _run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(d / "ca.key"), "-out", str(d / "ca.pem"),
             "-days", "1", "-subj", "/CN=agent-risk-scanner-mock-ca")
        _run("openssl", "req", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(d / "s.key"), "-out", str(d / "s.csr"),
             "-subj", "/CN=mock-web")
        (d / "ext.cnf").write_text(f"subjectAltName={san}\n")
        _run("openssl", "x509", "-req", "-in", str(d / "s.csr"),
             "-CA", str(d / "ca.pem"), "-CAkey", str(d / "ca.key"),
             "-CAcreateserial", "-out", str(d / "s.crt"),
             "-days", "1", "-extfile", str(d / "ext.cnf"))
        return {
            "ca": (d / "ca.pem").read_text(),
            "crt": (d / "s.crt").read_text(),
            "key": (d / "s.key").read_text(),
        }


def _web_hosts(web: dict) -> list[str]:
    """Unique hostnames across the case's page URLs -- each gets an
    `--add-host <host>:127.0.0.1` so the agent's fetch is redirected to the
    loopback mock instead of the real internet."""
    from urllib.parse import urlparse

    hosts: list[str] = []
    for page in web.get("pages", []):
        host = urlparse(page["url"]).hostname
        if host and host not in hosts:
            hosts.append(host)
    return hosts


def _materialize_web_server(workdir: Path, web: dict) -> None:
    """Write the mock web server + launcher into .web/. The server maps each
    page's URL path to its (poisoned) content. For https cases it also
    generates and writes the CA + leaf cert the mock serves TLS with."""
    from urllib.parse import urlparse

    pages = {urlparse(p["url"]).path: p["content"] for p in web.get("pages", [])}
    port = _web_port(web)
    https = _web_scheme(web) == "https"
    web_dir = workdir / ".web"
    web_dir.mkdir(parents=True, exist_ok=True)
    flags = f"PORT = {port!r}\nHTTPS = {https!r}\n"
    (web_dir / "server.py").write_text(
        f"PAGES = {pages!r}\n" + flags + _MOCK_WEB_SERVER_BODY
    )
    (web_dir / "run.py").write_text(flags + _MOCK_WEB_LAUNCHER_BODY)
    if https:
        certs = _generate_web_certs(_web_hosts(web))
        (web_dir / "ca.pem").write_text(certs["ca"])
        (web_dir / "server.crt").write_text(certs["crt"])
        (web_dir / "server.key").write_text(certs["key"])


# Credential / history denylist for the `config:` seam. The user's config
# directory mixes behavioural config (safe to copy) with secrets and past
# conversation history (must NOT enter a sandbox an attack runs in). See
# specs/20260521.md section 6.3.
_CONFIG_DENY_SUBSTRINGS = ("credential", "token", "secret", "apikey", "api_key")
_CONFIG_DENY_SUFFIXES = (".key", ".pem")
_CONFIG_DENY_PARTS = ("projects",)  # ~/.claude/projects/ = conversation history


def _config_denied(path: str) -> bool:
    """True if a config path looks like a credential or conversation history."""
    low = path.lower()
    name = low.rsplit("/", 1)[-1]
    if any(s in name for s in _CONFIG_DENY_SUBSTRINGS):
        return True
    if name.endswith(_CONFIG_DENY_SUFFIXES):
        return True
    return any(part in low.split("/") for part in _CONFIG_DENY_PARTS)


# Launcher for config files destined outside the workspace mount (e.g. the
# home dir): it copies each staged file to its destination, then execs the
# real agent command. Runs as the non-root agent user, which owns its home.
_CONFIG_LAUNCHER_BODY = '''
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for item in json.load(open(os.path.join(HERE, "manifest.json"))):
    dest = item["dest"]
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(os.path.join(HERE, item["staged"]), dest)

os.execvp(sys.argv[1], sys.argv[1:])
'''


def _materialize_config(workdir: Path, config: list, mount_root: str) -> bool:
    """Place the agent's `config:` files for one case run.

    Files destined inside the workspace mount are materialized directly (so
    they sit in the pre-run snapshot and never show up as a diff). Files
    destined elsewhere (the home dir) are staged into `.arsconfig/` for the
    launcher to copy at runtime. Credential / history files are skipped.

    Returns True if a launcher is needed (any out-of-workspace destination).
    """
    root = mount_root.rstrip("/")
    staged: list[tuple[Path, str]] = []
    for src, dest in config:
        src_path = Path(src)
        if not src_path.is_file():
            print(f"[harness] config: skipping {src} -- not a file")
            continue
        if _config_denied(src) or _config_denied(dest):
            print(f"[harness] config: SKIPPED {src} -- credential/history denylist")
            continue
        if dest == root or dest.startswith(root + "/"):
            target = workdir / dest[len(root):].lstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, target)
        else:
            staged.append((src_path, dest))

    if not staged:
        return False

    files_dir = workdir / ".arsconfig" / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, (src_path, dest) in enumerate(staged):
        shutil.copy2(src_path, files_dir / str(i))
        manifest.append({"staged": f"files/{i}", "dest": dest})
    (workdir / ".arsconfig" / "manifest.json").write_text(json.dumps(manifest))
    (workdir / ".arsconfig" / "apply.py").write_text(_CONFIG_LAUNCHER_BODY)
    return True


def run_case(case: Case, agent: AgentConfig, image_tag: str, timeout: int = 60) -> Observation:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        # agent config first (baseline), then case fixtures -- a case fixture
        # targeting the same path wins over agent config.
        config_needs_launcher = False
        if agent.config:
            config_needs_launcher = _materialize_config(
                workdir, agent.config, agent.workdir
            )
        _materialize_fixtures(workdir, case.fixtures, agent.workdir)
        if case.mcp:
            _materialize_mcp_server(workdir, case.mcp, agent.workdir)
        elif case.rag:
            _materialize_mcp_server(workdir, _rag_to_mcp(case.rag), agent.workdir)
        if case.web:
            _materialize_web_server(workdir, case.web)
        # the agent runs as a non-root user; make the throwaway workspace
        # fully writable so it can create / modify / delete files there
        for path in (workdir, *workdir.rglob("*")):
            path.chmod(0o777)
        before = _snapshot(workdir)

        # Launcher chain: config-apply (copies home-dir config) then web (boots
        # the mock). Each launcher execs the rest of argv, so they compose.
        add_host_args: list[str] = []
        launch_prefix: list[str] = []
        if config_needs_launcher:
            launch_prefix += ["python3", f"{agent.workdir}/.arsconfig/apply.py"]
        if case.web:
            for host in _web_hosts(case.web):
                add_host_args += ["--add-host", f"{host}:127.0.0.1"]
            launch_prefix += ["python3", f"{agent.workdir}/.web/run.py"]

        # The agent launch command is fixed (agent-level); the task is
        # per-case, so the harness appends it as the final argv element.
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            _DOCKER_NETWORK.get(agent.network, agent.network),
            *add_host_args,
            *_env_args(agent.env),
            "-v",
            f"{workdir}:{agent.workdir}",
            "-w",
            agent.workdir,
            image_tag,
            *launch_prefix,
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
        mcp = _read_intercept_log(workdir)
        return Observation(
            exit_code=exit_code,
            agent_stdout=stdout,
            agent_stderr=stderr,
            paths_deleted=d["deleted"],
            paths_created=d["created"],
            paths_modified=d["modified"],
            tool_calls=mcp["tool_calls"],
            mcp_connected=mcp["mcp_connected"],
            mcp_tools_listed=mcp["mcp_tools_listed"],
        )
