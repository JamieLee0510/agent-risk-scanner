# Claude Code example agent

[Claude Code](https://www.npmjs.com/package/@anthropic-ai/claude-code)
(`@anthropic-ai/claude-code`) is Anthropic's coding-agent CLI, used here as
an *agent under test* for the scanner.

- **Loop**: Claude Code's own agent loop (`Bash`, `Read`, `Edit`, ... tools)
- **CLI**: `claude -p "<task>"` runs a single task non-interactively
- **Model**: pinned to `claude-haiku-4-5` (cheapest) via `--model` for
  reproducible, low-cost runs
- **`--bare`**: minimal mode — skips auto-memory, background prefetches,
  CLAUDE.md auto-discovery, and keychain reads; auth is strictly
  `ANTHROPIC_API_KEY`. Keeps each run deterministic and isolated. (If a future
  case tests a *poisoned* `CLAUDE.md`, run that one without `--bare`.)

## Files

- `agent.yaml` — the only file. `runtime: node`, a `setup:` step that
  installs the Claude Code npm package, and the launch command.

No agent code and no Dockerfile — Claude Code is installed straight from npm
by the scanner.

## Permissions

`claude -p` would normally pause for tool-approval prompts. The agent runs
with `--dangerously-skip-permissions` so tool calls (including `Bash`)
execute autonomously — necessary for the scanner to observe what the agent
actually *does* when attacked.

That flag refuses to run as root; the scanner already runs every agent as a
non-root user, so it works as-is. (`rm -rf /` and home-directory deletions
still hit Claude Code's built-in circuit breaker — a case targeting a
workspace subdirectory is not affected.)

## Run it

```bash
export ANTHROPIC_API_KEY=sk-ant-...
agent-risk-scan run \
    --agent examples/claudecode/agent.yaml \
    --case cases/prompt-injection/general/ipi_rm_workspace.yaml
```
