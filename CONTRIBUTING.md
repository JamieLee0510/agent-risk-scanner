# Contributing to Agent Risk Scanner

Thanks for considering a contribution. The scanner is a small,
opinionated project — design decisions are recorded in `specs/` and in
the README's *Out of scope* section. Please read those before proposing
new families of work.

## Dev setup

```bash
git clone https://github.com/JamieLee0510/agent-risk-scanner.git
cd agent-risk-scanner
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Docker is required to actually run a scan. Tests for the judge / schema /
report layer run without Docker.

## Run the tests

```bash
pytest
ruff check .
```

CI runs the same two commands on Python 3.11 and 3.12. A PR with red CI
will not be merged.

## Adding a case

Cases live under `cases/<category>/` as YAML. Every case must include a
`source:` block (see [case-taxonomy](#case-taxonomy) below).

Minimum shape:

```yaml
name: <unique_snake_case>
category: <prompt-injection/general | mcp/tool-poisoning | agentic/excessive-agency | ...>
kind: attack            # or benign
source:
  kind: self-authored   # or paper | benchmark | repo | blog
  inspired_by: [...]    # required when kind: self-authored
  # if not self-authored, `name:` and `url:` are required
task: "..."
fixtures: { ... }
expect:
  paths_present: [...]  # at least one expect field is required
```

Pair every new attack case with a **benign hard-negative** under
`cases/prompt-injection/benign/` if there's a plausible false-positive
shape.

## Adding an agent example

Agents under test live under `examples/<name>/`. A new example needs:

- `agent.yaml` (the contract — see README "How the user integrates their agent")
- the agent code (or, for npm/PyPI agents, just a `setup:` line)
- a short `README.md` explaining the agent and any API key it needs

Run your example against the dummy cases to confirm the harness wiring:

```bash
agent-risk-scan run \
  --agent examples/<your-agent>/agent.yaml \
  --case cases/prompt-injection/general/ipi_rm_workspace.yaml
```

## Changing the harness / judge / schema

These are the load-bearing parts; please:

1. Open an issue first with the motivation and the proposed contract change
2. Update or add tests in `tests/`
3. Update `specs/` if you change a documented design decision
4. Update `CHANGELOG.md` under `[Unreleased]`

## Out of scope

See README's *Out of scope* section. The short version: this scanner's
thesis is **own a tool-using agent's lifecycle, sandbox it, judge it by
the runtime side-effects it produces**. Threats that don't have an
observable runtime side-effect, or that require leaving the sandbox
(real-server proxying, etc.), are deliberately out of scope.

If your idea doesn't fit, it may be a better fit as a separate tool or
a sibling project — happy to discuss in an issue.

## Commit style

Conventional-Commits-ish but not strict:

- `feat: add network egress observer`
- `fix: judge no longer returns pass when agent timed out`
- `docs: clarify --bare vs config: contradiction`

## License

By contributing you agree your contribution is licensed under
Apache-2.0 (the project's license). No CLA required.
