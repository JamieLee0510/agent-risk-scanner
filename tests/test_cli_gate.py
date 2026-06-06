"""cmd_gate's corpus-pinning guard (specs/20260604.md §4). The guard sits at
the very top of cmd_gate so a mismatch returns exit 2 WITHOUT building an image
or touching docker -- which is exactly what lets this run in plain CI."""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_risk_scanner import cli
from agent_risk_scanner import policy as P


def _ns(policy_path: Path, cases_root: Path) -> argparse.Namespace:
    return argparse.Namespace(
        agent=Path("agent.yaml"),
        policy=policy_path,
        cases_root=cases_root,
        report=None,
        summary_md=None,
        timeout=60,
    )


def _write_policy(tmp_path: Path, corpus_version: str) -> Path:
    p = tmp_path / "policy.yaml"
    p.write_text(f'corpus_version: "{corpus_version}"\nsuites: [x]\n')
    return p


def test_corpus_mismatch_returns_infra_error_without_scanning(tmp_path, monkeypatch):
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    (cases_root / "CORPUS_VERSION").write_text("v2\n")
    policy_path = _write_policy(tmp_path, "v1")

    called = False

    def _boom(*a, **k):  # _scan_for_policy must NOT run on a mismatch
        nonlocal called
        called = True
        raise AssertionError("scan should not start on a corpus mismatch")

    monkeypatch.setattr(cli, "_scan_for_policy", _boom)
    rc = cli.cmd_gate(_ns(policy_path, cases_root))
    assert rc == P.EXIT_INFRA_ERROR
    assert called is False


def test_corpus_match_proceeds_to_scan(tmp_path, monkeypatch):
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    (cases_root / "CORPUS_VERSION").write_text("v1\n")
    policy_path = _write_policy(tmp_path, "v1")

    # Matching corpus -> guard passes -> _scan_for_policy is reached. Stub it
    # with a clean report so we never touch docker; a clean report -> exit 0.
    monkeypatch.setattr(cli, "_scan_for_policy", lambda *a, **k: {"results": []})
    rc = cli.cmd_gate(_ns(policy_path, cases_root))
    assert rc == P.EXIT_PASS


def test_unversioned_corpus_does_not_block(tmp_path, monkeypatch):
    # No CORPUS_VERSION file -> read_corpus_version is None -> guard is lenient
    # (don't block ad-hoc/local corpora), scan proceeds.
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    policy_path = _write_policy(tmp_path, "v1")
    monkeypatch.setattr(cli, "_scan_for_policy", lambda *a, **k: {"results": []})
    rc = cli.cmd_gate(_ns(policy_path, cases_root))
    assert rc == P.EXIT_PASS
