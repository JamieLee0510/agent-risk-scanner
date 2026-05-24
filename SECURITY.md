# Security Policy

Agent Risk Scanner is itself a security tool. Vulnerabilities in the
scanner — particularly anything that lets a malicious agent-under-test
escape the sandbox, persist state across cases, or compromise the host
running the scanner — are taken seriously.

## Threat model in scope

The scanner runs untrusted agent code and adversarial test cases inside
Docker containers. Findings we want to hear about:

- **Sandbox escape** — an agent / case manages to write outside the
  per-case workspace, persist state into the image, escape the
  container, or read the host filesystem
- **Cross-case leakage** — state from case N influences case N+1
  (a successful attack should be confined to its own throwaway container)
- **Secret exposure** — `agent.yaml` env-forwarding or `config:`
  materialization leaks a credential into a file, image layer, or report
- **Judge bypass** — an attack that succeeds in reality but the judge
  renders `pass` (false negative), or a benign run that renders `fail`
  (false positive) in a way that's reproducible
- **Supply-chain** — a dependency / base image pulled by the synthesized
  Dockerfile lets a case tamper with the build

## Reporting

Email **walker200665@gmail.com** with subject `ARS security:`.

Please include:

- scanner version / commit
- minimal reproducer (an `agent.yaml` + case yaml is ideal)
- expected vs. actual verdict / observation
- impact assessment

We will acknowledge within 5 business days and aim to ship a fix within
30 days for sandbox-escape-class issues. Please give us a reasonable
disclosure window before public discussion.

## Out of scope

- Findings in agents under test — those are by-design outputs of the
  scanner, not scanner vulnerabilities
- Findings in `examples/dummy_*` — these are *intentionally* vulnerable
  baselines used as smoke tests
- DoS-by-design: running an infinite-loop agent will eventually hit
  `--timeout`; that is the intended behavior
- Findings that require modifying the scanner's own source (we trust
  scanner-side code)
