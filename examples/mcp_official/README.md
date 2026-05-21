# MCP example agent — official-SDK integration

A real LLM-driven ReAct agent that connects to the case's **MCP server** the
way a production agent does: through the official [`mcp`](https://github.com/modelcontextprotocol/python-sdk)
Python SDK, wrapped by
[`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters).

It is the sibling of [`examples/mcp_langgraph`](../mcp_langgraph). Same job —
load the MCP server's tools, let `gpt-4o-mini` decide how to use them — but a
different **integration style**:

| | `mcp_langgraph` | `mcp_official` (this) |
|---|---|---|
| MCP client | hand-rolled minimal stdio JSON-RPC | official `mcp` SDK |
| Handshake | written out by hand | run by the SDK |
| Represents | the smallest thing that works | how real MCP agents are wired |

Keeping both lets the scanner exercise the same poisoned MCP cases against two
realistic integration paths.

## Files

- `agent.py` — the agent loop (task from argv, prints the final answer)
- `requirements.txt` — dependencies; the scanner auto-installs these
- `agent.yaml` — tells the scanner how to build and launch the agent

## Run it

```bash
export OPENAI_API_KEY=sk-...
agent-risk-scan run \
    --agent examples/mcp_official/agent.yaml \
    --case cases/mcp/tool-poisoning/mcp_poisoned_clear_cache.yaml
```

Also handles `rag/` cases — the harness presents the knowledge base as an MCP
`search_kb` tool.

## Notes

- The SDK performs the full MCP handshake (`initialize` →
  `notifications/initialized` → `tools/list`) against the harness's
  synthesized mock server.
- Tool descriptions reach the model **verbatim** from the server — whether the
  model falls for a poisoned description is emergent, which is what the
  scanner measures.
