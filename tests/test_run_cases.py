"""_run_cases fan-out: jobs>1 must produce the SAME results (and per-case
order) as the serial path. Stubs run_case/judge so this never touches docker."""

from __future__ import annotations

from agent_risk_scanner import cli
from agent_risk_scanner.schema import AgentConfig, Case, CaseResult, Observation


def _agent() -> AgentConfig:
    return AgentConfig(cmd=["python", "/agent/agent.py"])


def _case(name: str) -> Case:
    return Case(name=name, category="test", task="t", fixtures={})


def _stub_run_case(monkeypatch):
    """run_case returns an Observation tagged with the case name; judge turns
    that tag into a deterministic per-case verdict so we can assert routing."""
    def fake_run_case(case, agent, tag, timeout=60):
        return Observation(
            exit_code=0, agent_stdout=case.name, agent_stderr="",
            paths_deleted=set(), paths_created=set(), paths_modified=set(),
        )

    def fake_judge(case, obs, mount_root="/workspace"):
        # encode the case name in the verdict reason so mis-routing is visible
        return CaseResult(case=case, observation=obs, verdict="pass",
                          reasons=[obs.agent_stdout])

    monkeypatch.setattr(cli, "run_case", fake_run_case)
    monkeypatch.setattr(cli, "judge", fake_judge)


def test_parallel_matches_serial(monkeypatch):
    _stub_run_case(monkeypatch)
    cases = [_case(f"c{i}") for i in range(12)]
    agent = _agent()

    serial = cli._run_cases(cases, agent, "tag", n=3, timeout=60, jobs=1)
    parallel = cli._run_cases(cases, agent, "tag", n=3, timeout=60, jobs=4)

    # one inner list per case, in the ORIGINAL order, each with n results that
    # belong to that case (no cross-case contamination from the thread pool).
    assert len(serial) == len(parallel) == len(cases)
    for ci, case in enumerate(cases):
        assert len(parallel[ci]) == 3
        assert {r.reasons[0] for r in parallel[ci]} == {case.name}
        assert {r.case.name for r in parallel[ci]} == {case.name}
    # same shape as serial
    assert [len(x) for x in serial] == [len(x) for x in parallel]


def test_jobs_one_is_serial_path(monkeypatch):
    _stub_run_case(monkeypatch)
    cases = [_case("a"), _case("b")]
    out = cli._run_cases(cases, _agent(), "tag", n=2, timeout=60, jobs=1)
    assert [r.case.name for runs in out for r in runs] == ["a", "a", "b", "b"]
