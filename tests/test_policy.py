"""Gate policy decision logic — the layer that turns a scan report into a CI
exit code (specs/20260604.md). Every exit-code branch and the baseline
reconciliation (new / waived / improved / regressed) has a test, because a
wrong decision here either blocks every PR or silently lets vulnerabilities
through."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_risk_scanner import policy as P


def _entry(name, *, kind="attack", fail_rate=0.0, error=0, inconclusive=0,
           category="prompt-injection/general"):
    counts = {"pass": 0, "fail": 0, "inconclusive": inconclusive, "error": error}
    return {
        "case": name,
        "category": category,
        "kind": kind,
        "fail_rate": fail_rate,
        "verdict_counts": counts,
    }


def _report(*entries):
    return {"generated_at": "t", "agent": "a.yaml", "results": list(entries)}


def _policy(**kw):
    kw.setdefault("corpus_version", "v1")
    return P.Policy(**kw)


def test_clean_run_passes():
    r = P.evaluate(_report(_entry("ok", fail_rate=0.0)), _policy(), None)
    assert r.exit_code == P.EXIT_PASS
    assert not r.blocking


def test_attack_over_threshold_blocks():
    r = P.evaluate(_report(_entry("bad", fail_rate=0.5)), _policy(attack_fail_rate=0.0), None)
    assert r.exit_code == P.EXIT_SECURITY_FAIL
    assert [f.key for f in r.blocking] == ["prompt-injection/general/bad"]
    assert r.blocking[0].status == "blocking"
    assert r.blocking[0].baseline_rate is None  # new finding


def test_benign_uses_its_own_threshold():
    rpt = _report(_entry("b", kind="benign", fail_rate=0.1, category="prompt-injection/benign"))
    # within benign tolerance -> not a finding
    assert P.evaluate(rpt, _policy(benign_break_rate=0.2), None).exit_code == P.EXIT_PASS
    # over benign tolerance -> blocks
    assert P.evaluate(rpt, _policy(benign_break_rate=0.05), None).exit_code == P.EXIT_SECURITY_FAIL


def test_error_blocks_or_warns_per_on_error():
    rpt = _report(_entry("e", fail_rate=0.0, error=1))
    assert P.evaluate(rpt, _policy(on_error="block"), None).exit_code == P.EXIT_INFRA_ERROR
    assert P.evaluate(rpt, _policy(on_error="warn"), None).exit_code == P.EXIT_PASS


def test_security_fail_dominates_infra_error():
    # a blocking attack AND an errored case -> exit 1 (security), not 2
    rpt = _report(_entry("bad", fail_rate=1.0), _entry("e", fail_rate=0.0, error=1))
    r = P.evaluate(rpt, _policy(on_error="block"), None)
    assert r.exit_code == P.EXIT_SECURITY_FAIL


def test_baseline_waives_preexisting():
    rpt = _report(_entry("bad", fail_rate=1.0))
    base = P.Baseline(corpus_version="v1", accepted={"prompt-injection/general/bad": 1.0})
    r = P.evaluate(rpt, _policy(), base)
    assert r.exit_code == P.EXIT_PASS
    assert [f.status for f in r.waived] == ["waived"]
    assert not r.blocking


def test_baseline_blocks_regression():
    rpt = _report(_entry("bad", fail_rate=1.0))
    base = P.Baseline(corpus_version="v1", accepted={"prompt-injection/general/bad": 0.5})
    r = P.evaluate(rpt, _policy(), base)
    assert r.exit_code == P.EXIT_SECURITY_FAIL
    assert r.blocking[0].status == "blocking"


def test_baseline_reports_improvement():
    rpt = _report(_entry("bad", fail_rate=0.3))
    base = P.Baseline(corpus_version="v1", accepted={"prompt-injection/general/bad": 1.0})
    r = P.evaluate(rpt, _policy(), base)
    assert r.exit_code == P.EXIT_PASS
    assert [f.status for f in r.improved] == ["improved"]


def test_baseline_from_report_accepts_only_violations():
    rpt = _report(
        _entry("bad", fail_rate=1.0),
        _entry("ok", fail_rate=0.0),
        _entry("benign_ok", kind="benign", fail_rate=0.1, category="prompt-injection/benign"),
    )
    doc = P.baseline_from_report(rpt, _policy(attack_fail_rate=0.0, benign_break_rate=0.2))
    assert set(doc["accepted"]) == {"prompt-injection/general/bad"}
    assert doc["corpus_version"] == "v1"


def test_load_policy_requires_corpus_version(tmp_path: Path):
    p = tmp_path / "policy.yaml"
    p.write_text("suites: [prompt-injection/general]\nrepeat: 3\n")
    with pytest.raises(ValueError, match="corpus_version"):
        P.load_policy(p)


def test_load_policy_resolves_baseline_relative_to_policy(tmp_path: Path):
    p = tmp_path / "policy.yaml"
    p.write_text('corpus_version: "v1"\nbaseline: bl.json\n')
    pol = P.load_policy(p)
    assert pol.baseline == (tmp_path / "bl.json").resolve()
