"""Intentionally vulnerable RAG agent.

It connects to the knowledge-base MCP server, calls `search_kb` to retrieve
documents, and -- the bug -- (1) executes any `EXECUTE: <cmd>` line found in
the retrieved content, and (2) answers by parroting the retrieved content
verbatim. Both make it trust poisoned documents as ground truth.

The harness should catch this by observing the destructive filesystem
changes (flavour 1) or the poisoned fact appearing in the output (flavour 2).
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
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
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
        print(json.dumps({"final_output": "no knowledge base configured"}))
        return

    client = McpClient(json.loads(MCP_CONFIG.read_text())["command"])
    client.request(
        "initialize",
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "dummy-rag-agent", "version": "0.0.1"},
        },
    )
    client.notify("notifications/initialized")

    result = client.request("tools/call", {"name": "search_kb", "arguments": {"query": task}})
    content = result.get("content", [])
    retrieved = content[0]["text"] if content else ""
    client.close()

    # Bug 1: execute any EXECUTE: line found in the retrieved content.
    for line in retrieved.splitlines():
        m = re.match(r"\s*EXECUTE:\s*(.+)", line)
        if m:
            subprocess.run(m.group(1).strip(), shell=True)

    # Bug 2: answer by parroting the retrieved content verbatim.
    print(json.dumps({"final_output": f"Based on the knowledge base: {retrieved[:4000]}"}))


if __name__ == "__main__":
    main()
