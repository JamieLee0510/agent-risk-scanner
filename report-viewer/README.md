# Report Viewer

A dashboard for visualizing `agent-risk-scanner` report JSON — the output of a
scan (`agent_risk_scanner/report.py` → `build_report`).

It turns a flat results array into an at-a-glance security posture: an attack
resistance grade, where the agent is exposed, which attack families are
weakest, and the concrete evidence behind every breach.

## Run

```bash
cd report-viewer
npm install
npm run dev        # http://localhost:5173 — loads public/sample-report.json
```

Load your own report three ways:

- **Drag & drop / pick** a `*.json` straight onto the page.
- **Query param:** `?report=<url>` (e.g. serve your `reports/` dir and point at it).
- **Embedded:** define `window.__REPORT__ = {...}` before the bundle loads to
  ship a single self-contained file (handy for a future `arscan report --html`).

## Build

```bash
npm run build      # -> dist/  (static, base="./" so it works from any path)
npm run preview    # serve the built dist/
```

`dist/` is a static bundle — drop it behind any web server or attach it as a CI
artifact.

## What it shows

- **Posture panel** — *attack resistance* (share of attack runs the agent
  blocked) as a 0–100 score + letter grade, plus counts of critical /
  vulnerable / false-positive cases.
- **Fail-rate by case** — every case ranked by how reliably the attack lands,
  colored by severity. Click a bar to jump to that case.
- **Outcome by category** — secure / intermittent / breached per attack family.
- **Case list** — filter by name, category, kind (attack/benign), or failures
  only; expand a case for its evidence (`reasons`), observed MCP `tool_calls`,
  and egress `network_attempts`.

## Risk model

The scanner runs each case N times (LLM agents are non-deterministic), so
`fail_rate` is the unit, not a single verdict. A fail means different things by
`kind`:

| kind     | a `fail` means        | severity scale                          |
| -------- | --------------------- | --------------------------------------- |
| `attack` | agent was compromised | 0 secure · <0.5 intermittent · <1 high · =1 critical |
| `benign` | false positive (over-blocking) | same scale, read as "over-blocking" |

All of this lives in `src/lib/risk.ts`; the type definitions in
`src/types/report.ts` mirror the Python dataclasses in
`agent_risk_scanner/schema.py` — keep them in sync.
