"""Dockerfile synthesis -- the harness turns runtime/code/setup into an image
recipe. Regressions here change what every yaml-only agent actually runs."""

from __future__ import annotations

import pytest

from agent_risk_scanner.harness import _generate_dockerfile
from agent_risk_scanner.schema import AgentConfig


def test_go_runtime_autobuilds_cmd_module(tmp_path):
    """A go.mod + cmd/ layout auto-compiles to /usr/local/bin/agent with no
    explicit setup -- this is the 'just one agent.yaml' path."""
    (tmp_path / "go.mod").write_text("module x\n")
    (tmp_path / "cmd").mkdir()
    cfg = AgentConfig(cmd=["/usr/local/bin/agent"], runtime="go", code=tmp_path)
    df = _generate_dockerfile(cfg)
    assert df.startswith("FROM golang:1.25-bookworm")
    assert "go build -o /usr/local/bin/agent ./cmd/..." in df
    assert "python3" in df  # launchers need it; the go base image lacks it
    assert df.rstrip().endswith("USER agent")


def test_go_runtime_root_main_fallback(tmp_path):
    """No cmd/ dir -> build the module root."""
    (tmp_path / "go.mod").write_text("module x\n")
    cfg = AgentConfig(cmd=["/usr/local/bin/agent"], runtime="go", code=tmp_path)
    df = _generate_dockerfile(cfg)
    assert "go build -o /usr/local/bin/agent ." in df


def test_explicit_setup_overrides_autobuild(tmp_path):
    """An explicit setup: wins over go.mod auto-detection."""
    (tmp_path / "go.mod").write_text("module x\n")
    cfg = AgentConfig(
        cmd=["/usr/local/bin/agent"],
        runtime="go",
        code=tmp_path,
        setup=["cd /agent && go build -o /usr/local/bin/agent ./apps/main"],
    )
    df = _generate_dockerfile(cfg)
    assert "./apps/main" in df
    assert "./cmd/..." not in df


def test_unknown_runtime_raises():
    cfg = AgentConfig(cmd=["x"], runtime="rust")
    with pytest.raises(ValueError, match="unknown runtime"):
        _generate_dockerfile(cfg)
