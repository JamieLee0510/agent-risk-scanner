# LangGraph MCP example agent

A real LLM-driven ReAct agent that connects to the **MCP server** declared by
a case, loads its tools over stdio, and lets the model decide how to use them.
Used as an *agent under test* for the scanner's `mcp/` cases.

- **Loop**: `create_react_agent` (LangGraph's prebuilt ReAct loop)
- **Model**: OpenAI `gpt-4o-mini` (override with the `AGENT_MODEL` env var)
- **Tools**: loaded dynamically from the MCP server at
  `/workspace/.mcp/mcp.json` — names and descriptions come straight from the
  server, poison and all

## Files

- `agent.py` — the agent loop (task from argv, prints the final answer)
- `requirements.txt` — dependencies; the scanner auto-installs these
- `agent.yaml` — tells the scanner how to build and launch the agent

No Dockerfile: the scanner synthesizes the image from `agent.yaml`.

## Run it

```bash
export OPENAI_API_KEY=sk-...
agent-risk-scan run \
    --agent examples/mcp_langgraph/agent.yaml \
    --case cases/mcp/tool-poisoning/mcp_poisoned_clear_cache.yaml
```

## Notes

- Unlike `examples/dummy_mcp_agent`, which hard-codes the bug (it obeys
  `EXECUTE-TOOL:` lines in tool descriptions), this is a real LLM loop —
  whether it falls for a **poisoned tool description** is emergent, which is
  exactly what the scanner measures.
- Tool descriptions are passed to the model **verbatim** from the MCP server;
  the agent does no filtering. That keeps tool metadata the attack surface.
