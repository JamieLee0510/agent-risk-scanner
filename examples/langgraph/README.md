# LangGraph example agent

A minimal ReAct-style tool-using agent loop built with
[LangGraph](https://github.com/langchain-ai/langgraph), used as an *agent
under test* for the scanner.

- **Loop**: `create_react_agent` (LangGraph's prebuilt ReAct loop)
- **Model**: OpenAI `gpt-4o-mini` (override with the `AGENT_MODEL` env var)
- **Tools**: `list_files`, `read_file`, `write_file`, `run_bash`

## Files

- `agent.py` — the agent loop (task from argv, prints the final answer)
- `requirements.txt` — dependencies; the scanner auto-installs these
- `agent.yaml` — tells the scanner how to build and launch the agent

No Dockerfile: the scanner synthesizes the image from `agent.yaml`
(`runtime: python`, `code: .`, `requirements.txt` auto-installed).

## Run it

```bash
export OPENAI_API_KEY=sk-...
agent-risk-scan run \
    --agent examples/langgraph/agent.yaml \
    --case cases/prompt-injection/general/ipi_rm_workspace.yaml
```

## Notes

- This is a real LLM-driven loop — whether it falls for an injected
  instruction depends on the model, which is exactly what the scanner
  measures.
- The file tools refuse paths outside the workspace; `run_bash` does not, so
  bash remains the broad (and realistic) attack surface.
