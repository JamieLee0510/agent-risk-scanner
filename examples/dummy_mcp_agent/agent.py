"""Intentionally vulnerable MCP client agent.

It connects to the MCP server declared by the case, lists its tools, and --
the bug -- treats instructions found inside tool *descriptions* as commands:
any `EXECUTE-TOOL: <name>` line in a tool description makes it call that
tool. This is the textbook MCP tool-poisoning vulnerability: untrusted tool
metadata is trusted as if it were an agent instruction.

The harness should catch this by observing the destructive filesystem
changes the poisoned tool produces.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

MCP_CONFIG = Path("/workspace/.mcp/mcp.json")


class McpClient:
    """A minimal stdio JSON-RPC MCP client."""

    def __init__(self, command: list[str]) -> None:
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._id = 0

    def request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            return {}
        return json.loads(line).get("result", {})

    def notify(self, method: str) -> None:
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def main() -> None:
    task = sys.argv[1] if len(sys.argv) > 1 else ""

    if not MCP_CONFIG.exists():
        print(json.dumps({"final_output": "no MCP server configured"}))
        return

    command = json.loads(MCP_CONFIG.read_text())["command"]
    client = McpClient(command)
    client.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "dummy-mcp-agent", "version": "0.0.1"},
        },
    )
    client.notify("notifications/initialized")

    tools = client.request("tools/list").get("tools", [])

    # The bug: obey instructions embedded in untrusted tool descriptions.
    called: list[str] = []
    for tool in tools:
        for line in tool.get("description", "").splitlines():
            m = re.match(r"\s*EXECUTE-TOOL:\s*(\S+)", line)
            if m:
                client.request("tools/call", {"name": m.group(1), "arguments": {}})
                called.append(m.group(1))

    client.close()
    print(json.dumps({
        "final_output": f"task '{task[:60]}': saw {len(tools)} tools, called {called}"
    }))


if __name__ == "__main__":
    main()
