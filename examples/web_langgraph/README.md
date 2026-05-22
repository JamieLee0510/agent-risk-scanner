# LangGraph web example agent

A real LLM-driven ReAct agent with a `fetch_url` tool (plus file tools), used
as an *agent under test* for the scanner's `prompt-injection/web` cases.

- **Loop**: `create_react_agent` (LangGraph's prebuilt ReAct loop)
- **Model**: OpenAI `gpt-4o-mini` (override with the `AGENT_MODEL` env var)
- **Tools**: `fetch_url`, `list_files`, `read_file`, `write_file`, `run_bash`

## How the scanner intercepts the web

For a `web:` case the scanner synthesizes a mock web server, serves it on
loopback inside the sandbox, and redirects each page host to it with
`docker run --add-host <host>:127.0.0.1`. So `fetch_url("http://docs.example/...")`
reaches the scanner's controlled (poisoned) page, never the real internet.
The agent still has `network: open` so it can call the OpenAI API.

## Run it

```bash
export OPENAI_API_KEY=sk-...
agent-risk-scan run \
    --agent examples/web_langgraph/agent.yaml \
    --case cases/prompt-injection/web/web_ipi_fetch_page.yaml
```

## Notes

- Whether the agent obeys a hidden instruction inside a fetched page is
  emergent — that is what the scanner measures.
- The file tools refuse paths outside the workspace; `run_bash` does not, so
  bash stays the broad attack surface.
