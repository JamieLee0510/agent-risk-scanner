# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- LICENSE (Apache-2.0), NOTICE, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md
- CHANGELOG.md
- `tests/` — pytest coverage for judge, schema loaders, and report builder
- GitHub Actions CI (pytest + ruff on Python 3.11 / 3.12)
- `ruff` and `pytest` dev configuration in `pyproject.toml`
- PyPI metadata (authors, urls, classifiers, keywords) in `pyproject.toml`

### Changed
- README: added CI / license / Python / PRs-welcome badges
- README: fixed broken links to `specs/` (the directory is gitignored;
  references now point to in-tree design notes)

## [0.0.1] — 2026-05 (pre-release, in-tree)

End-to-end loop implemented but never released:

- Docker harness — `agent.yaml` → synthesized Dockerfile → per-case
  workspace → filesystem diff
- Argv-injection agent contract
- Filesystem-effect judge (`paths_present` / `paths_absent`) + text-canary
  judge (`answer_must_not_contain`)
- MCP interception layer with `forbidden_tool_calls` and `inconclusive`
  verdict when the agent never enumerates tools
- Web-agent indirect-PI: loopback mock web server (HTTP + HTTPS)
- Network egress observer (opt-in HTTP/S proxy)
- Config-seam: copy user's real `CLAUDE.md` / `settings.json` / `.mcp.json`
  into the sandbox (credentials filtered)
- `--repeat N` for non-deterministic LLM agents (hit-rate reporting)
- Standard `.mcp.json` (`mcpServers`) format for Claude Code / Cursor /
  Cline / Continue compatibility
- 39 cases across `prompt-injection/{general,skill,obfuscation,web,benign}`,
  `mcp/tool-poisoning`, `agentic/excessive-agency`
- 9 example agents under `examples/`

[Unreleased]: https://github.com/JamieLee0510/agent-risk-scanner/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/JamieLee0510/agent-risk-scanner/releases/tag/v0.0.1
