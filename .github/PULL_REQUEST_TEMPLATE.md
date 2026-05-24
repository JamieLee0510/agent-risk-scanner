## What

<!-- 1–3 sentences. Link the issue if applicable. -->

## Why

<!-- The user-visible reason. Skip if obvious from the title. -->

## Test plan

- [ ] `pytest -q` green
- [ ] `ruff check agent_risk_scanner tests` clean
- [ ] If touching the harness / judge / schema: tested end-to-end against `examples/dummy_agent` or `examples/langgraph`
- [ ] If adding a case: ran it against the dummy agent for the family and confirmed expected verdict
- [ ] `CHANGELOG.md` updated under `[Unreleased]` (if user-visible)
