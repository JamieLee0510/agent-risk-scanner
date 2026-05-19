# Pi example agent

[Pi](https://github.com/earendil-works/pi) (`@earendil-works/pi-coding-agent`)
is a self-extensible coding-agent CLI — the same agent that powers OpenClaw.
Here it is used as an *agent under test* for the scanner.

- **Loop**: Pi's own coding-agent loop (tool calling + state management)
- **Model**: OpenAI `gpt-4o-mini` via Pi's `openai/...` provider prefix
- **CLI**: `pi -p "<task>"` runs a single task non-interactively (print mode)

## Files

- `agent.yaml` — the only file. `runtime: node`, a `setup:` step that
  installs the Pi npm package, and the launch command.

No agent code and no Dockerfile — Pi is installed straight from npm by the
scanner.

## Run it

```bash
export OPENAI_API_KEY=sk-...
agent-risk-scan run \
    --agent examples/pi/agent.yaml \
    --case cases/prompt-injection/general/ipi_rm_workspace.yaml
```

## Notes / to verify

- Pi can also use Anthropic or Google models — swap the `--model` value
  (`anthropic/...`, `google/...`) and the matching `env` key. Run
  `pi --list-models` to see the options.
- If `pi -p` blocks on a tool-permission prompt, an extra flag may be needed
  to make tool calls run autonomously — verify against the installed version.
