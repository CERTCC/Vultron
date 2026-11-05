"""CI verification test — the always-running ``CI gate`` check (#5942).

The verdict is a pure function in ``.github/scripts/ci_gate.py``, tested here
on recorded shapes of GitHub's workflow-run and check-run records. The workflow
that runs it is pinned here too, because a ruleset requires its job by name and
a ``paths`` filter would leave a pull request waiting on it forever.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)

_SCRIPT = REPO_ROOT / ".github" / "scripts" / "ci_gate.py"
_WORKFLOW = WORKFLOWS_DIR / "ci-gate.yml"
OWN = ".github/workflows/ci-gate.yml"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ci_gate", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve string annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gate = _load_script()
_ids = itertools.count(1000)


def run(
    name: str,
    workflow_id: int,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
    path: str | None = None,
) -> dict[str, Any]:
    """A workflow-run record, with a fresh run id and check suite."""
    run_id = next(_ids)
    return {
        "id": run_id,
        "name": name,
        "workflow_id": workflow_id,
        "path": path or f".github/workflows/{name}.yml",
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "check_suite_id": run_id * 10,
    }


def check(
    name: str,
    suite: int,
    *,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict[str, Any]:
    """A check-run record in check suite *suite*."""
    return {
        "id": next(_ids),
        "name": name,
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "check_suite": {"id": suite},
    }


def suite(r: dict[str, Any]) -> int:
    return int(r["check_suite_id"])


# --- verdict rules ----------------------------------------------------------


def test_all_green_and_skipped_checks_pass() -> None:
    py = run("python-app", 1)
    runs = [py, own := run("CI gate", 9, status="in_progress", path=OWN)]
    checks = [
        check("Tests (pytest)", suite(py)),
        check("Notify CI failure", suite(py), conclusion="skipped"),
        check("CI gate", suite(own), status="in_progress"),
    ]
    verdict = gate.judge(runs, checks, OWN)
    assert verdict.done
    assert verdict.red == []
    assert verdict.green == [
        "Tests (pytest): success",
        "Notify CI failure: skipped",
    ]


def test_neutral_is_green() -> None:
    py = run("python-app", 1, conclusion="neutral")
    verdict = gate.judge(
        [py], [check("lint", suite(py), conclusion="neutral")], OWN
    )
    assert verdict.red == []


@pytest.mark.parametrize(
    "conclusion",
    [
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "startup_failure",
        "stale",
        None,
        "a-conclusion-github-adds-later",
    ],
)
def test_every_other_conclusion_is_red(conclusion: str | None) -> None:
    py = run("python-app", 1, conclusion="failure")
    checks = [
        check("Tests (pytest)", suite(py), conclusion=conclusion),
        check("Lint (ruff)", suite(py)),
    ]
    verdict = gate.judge([py], checks, OWN)
    assert verdict.red == [f"Tests (pytest): {conclusion}"]


def test_the_gate_excludes_its_own_runs_and_checks() -> None:
    old = run("CI gate", 9, conclusion="cancelled", path=OWN)
    own = run("CI gate", 9, status="in_progress", path=OWN)
    py = run("python-app", 1)
    checks = [
        check("CI gate", suite(old), conclusion="cancelled"),
        check("CI gate", suite(own), status="in_progress"),
        check("Tests (pytest)", suite(py)),
    ]
    verdict = gate.judge([old, own, py], checks, OWN)
    assert verdict.done
    assert (verdict.red, verdict.green) == ([], ["Tests (pytest): success"])


def test_a_superseded_run_on_the_same_commit_is_not_judged() -> None:
    # Recorded on PR #5936: verification-debt-owners ran twice on one head
    # commit, and its concurrency group cancelled the first run's job.
    first = run("Verification Debt Owners", 3, conclusion="cancelled")
    second = run("Verification Debt Owners", 3)
    checks = [
        check("PR Closes No Owner", suite(first), conclusion="cancelled"),
        check("PR Closes No Owner", suite(second)),
    ]
    verdict = gate.judge([second, first], checks, OWN)
    assert verdict.red == []
    assert verdict.green == ["PR Closes No Owner: success"]


def test_a_run_that_failed_to_start_is_named() -> None:
    broken = run("ui", 4, conclusion="startup_failure")
    verdict = gate.judge([broken], [], OWN)
    assert verdict.red == ["ui (workflow): startup_failure"]


def test_a_red_run_is_named_once_by_its_red_job() -> None:
    py = run("python-app", 1, conclusion="failure")
    checks = [check("Tests (pytest)", suite(py), conclusion="failure")]
    assert gate.judge([py], checks, OWN).red == ["Tests (pytest): failure"]


def test_an_app_check_outside_any_workflow_is_judged_by_its_newest_run() -> (
    None
):
    py = run("python-app", 1)
    checks = [
        check("CodeQL", 77, conclusion="failure"),
        check("CodeQL", 78),
        check("External scan", 79, conclusion="failure"),
    ]
    verdict = gate.judge([py], checks, OWN)
    assert verdict.green == ["CodeQL: success"]
    assert verdict.red == ["External scan: failure"]


def test_a_re_run_job_is_judged_by_its_newest_attempt() -> None:
    py = run("python-app", 1)
    checks = [
        check("Tests (pytest)", suite(py), conclusion="failure"),
        check("Tests (pytest)", suite(py)),
    ]
    verdict = gate.judge([py], checks, OWN)
    assert verdict.red == []
    assert verdict.green == ["Tests (pytest): success"]


def test_a_running_job_in_a_finished_run_is_pending() -> None:
    py = run("python-app", 1)
    verdict = gate.judge(
        [py], [check("Tests (pytest)", suite(py), status="in_progress")], OWN
    )
    assert verdict.pending == ["Tests (pytest) (in_progress)"]


def test_no_other_check_is_pending_never_green() -> None:
    own = run("CI gate", 9, status="in_progress", path=OWN)
    verdict = gate.judge([own], [check("CI gate", suite(own))], OWN)
    assert verdict.pending == ["no other check has started on this commit"]
    assert not verdict.done


def test_a_running_workflow_is_pending_before_its_checks_are_read() -> None:
    demo = run("demo-integration", 5, status="in_progress")
    verdict = gate.judge([demo], None, OWN)
    assert verdict.pending == ["demo-integration (workflow, in_progress)"]
    assert not verdict.done


def test_check_runs_are_required_once_no_workflow_runs() -> None:
    with pytest.raises(ValueError, match="check runs are needed"):
        gate.judge([run("python-app", 1)], None, OWN)


def test_an_unfinished_app_check_is_pending() -> None:
    verdict = gate.judge([], [check("CodeQL", 77, status="queued")], OWN)
    assert verdict.pending == ["CodeQL (queued)"]


@pytest.mark.parametrize(
    ("ref", "path"),
    [
        (
            "CERTCC/Vultron/.github/workflows/ci-gate.yml@refs/pull/7/merge",
            OWN,
        ),
        ("o/r/.github/workflows/ci-gate.yml", OWN),
    ],
)
def test_own_workflow_path_reads_the_workflow_ref(ref: str, path: str) -> None:
    assert gate.own_workflow_path(ref) == path


@pytest.mark.parametrize("ref", ["", "o/r", "o/r/@refs/heads/main"])
def test_a_malformed_workflow_ref_raises(ref: str) -> None:
    with pytest.raises(ValueError):
        gate.own_workflow_path(ref)


# --- polling ----------------------------------------------------------------


class FakeGitHub:
    """Serves one recorded state per poll, and counts the check-run reads."""

    def __init__(
        self, states: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]]
    ) -> None:
        self._states: Iterator[
            tuple[list[dict[str, Any]], list[dict[str, Any]]]
        ] = iter(states)
        self._current: tuple[list[dict[str, Any]], list[dict[str, Any]]] = (
            [],
            [],
        )
        self.check_reads = 0

    def workflow_runs(self) -> list[dict[str, Any]]:
        self._current = next(self._states, self._current)
        return self._current[0]

    def check_runs(self) -> list[dict[str, Any]]:
        self.check_reads += 1
        return self._current[1]


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _wait(github: FakeGitHub, clock: Clock, **overrides: float) -> Any:
    timing: dict[str, float] = {
        "grace_seconds": 90,
        "poll_seconds": 60,
        "deadline_seconds": 600,
    }
    timing.update(overrides)
    return gate.wait(
        github,
        OWN,
        clock=clock,
        sleep=clock.sleep,
        log=lambda _msg: None,
        **timing,
    )


def test_the_gate_waits_out_the_grace_period_for_a_late_workflow() -> None:
    py = run("python-app", 1)
    late = run("demo-integration", 5, conclusion="failure")
    clock = Clock()
    github = FakeGitHub(
        [
            ([py], [check("Tests", suite(py))]),
            ([py, late], [check("Tests", suite(py))]),
        ]
    )
    verdict, timed_out = _wait(github, clock)
    assert not timed_out
    assert clock.now == 120
    assert verdict.red == ["demo-integration (workflow): failure"]


def test_the_gate_reads_check_runs_only_once_no_workflow_runs() -> None:
    running = run("python-app", 1, status="in_progress")
    done = dict(running, status="completed", conclusion="success")
    clock = Clock()
    github = FakeGitHub(
        [([running], []), ([running], []), ([done], [check("T", suite(done))])]
    )
    verdict, timed_out = _wait(github, clock)
    assert (verdict.green, timed_out) == (["T: success"], False)
    assert github.check_reads == 1
    assert clock.now == 120


def test_the_gate_ends_red_at_its_deadline_naming_what_still_runs() -> None:
    stuck = run("demo-integration", 5, status="queued")
    clock = Clock()
    verdict, timed_out = _wait(
        FakeGitHub([([stuck], [])]), clock, deadline_seconds=300
    )
    assert timed_out
    assert verdict.pending == ["demo-integration (workflow, queued)"]
    assert gate.report(verdict, timed_out) == 1


def test_report_is_green_only_with_no_red_and_no_timeout(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert gate.report(gate.Verdict(green=["T: success"]), False) == 0
    red = gate.Verdict(red=["Tests: failure"], green=["Lint: success"])
    assert gate.report(red, False) == 1
    out = capsys.readouterr().out
    assert "::error::Red check: Tests: failure" in out
    assert "- ❌ Tests: failure" in summary.read_text(encoding="utf-8")


def test_the_last_sleep_stops_at_the_deadline() -> None:
    stuck = run("demo-integration", 5, status="queued")
    clock = Clock()
    _, timed_out = _wait(
        FakeGitHub([([stuck], [])]),
        clock,
        poll_seconds=120,
        deadline_seconds=300,
    )
    assert timed_out
    assert clock.now == 300


def _github_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str | None]]:
    calls: list[tuple[str, str | None]] = []

    def fake_paginated(
        endpoint: str, key: str | None = None
    ) -> list[dict[str, Any]]:
        calls.append((endpoint, key))
        return []

    monkeypatch.setattr(gate, "paginated", fake_paginated)
    return calls


def test_the_reads_name_the_commit_and_the_newest_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _github_calls(monkeypatch)
    github = gate.GitHub(repo="o/r", sha="abc")
    github.workflow_runs()
    github.check_runs()
    assert calls == [
        ("repos/o/r/actions/runs?head_sha=abc&per_page=100", "workflow_runs"),
        (
            "repos/o/r/commits/abc/check-runs?filter=latest&per_page=100",
            "check_runs",
        ),
    ]


def test_paginated_flattens_every_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gh_cli = sys.modules["gh_cli"]
    pages = [{"check_runs": [{"id": 1}]}, {"check_runs": [{"id": 2}]}]
    argv: list[tuple[str, ...]] = []

    def fake_gh(*args: str, retry: bool = True) -> str:
        argv.append(args)
        return json.dumps(pages)

    monkeypatch.setattr(gh_cli, "gh", fake_gh)
    assert gh_cli.paginated("e", "check_runs") == [{"id": 1}, {"id": 2}]
    assert argv == [("api", "--paginate", "--slurp", "e")]
    monkeypatch.setattr(gh_cli, "gh", lambda *_a: json.dumps([[{"id": 3}]]))
    assert gh_cli.paginated("e") == [{"id": 3}]


_ENV = {
    "REPO": "o/r",
    "HEAD_SHA": "abc",
    "GITHUB_WORKFLOW_REF": "o/r/.github/workflows/ci-gate.yml@refs/pull/7/merge",
}


def _capture_wait(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def fake_wait(github: Any, own_path: str, **timing: float) -> Any:
        seen.update(github=github, own_path=own_path, **timing)
        return gate.Verdict(green=["T: success"]), False

    monkeypatch.setattr(gate, "wait", fake_wait)
    return seen


def test_main_reads_its_settings_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _capture_wait(monkeypatch)
    env = dict(
        _ENV,
        GATE_GRACE_SECONDS="5",
        GATE_POLL_SECONDS="7",
        GATE_DEADLINE_MINUTES="2",
    )
    assert gate.main(env) == 0
    assert seen == {
        "github": gate.GitHub(repo="o/r", sha="abc"),
        "own_path": OWN,
        "grace_seconds": 5,
        "poll_seconds": 7,
        "deadline_seconds": 120,
    }


def test_main_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _capture_wait(monkeypatch)
    gate.main(_ENV)
    assert (
        seen["grace_seconds"],
        seen["poll_seconds"],
        seen["deadline_seconds"],
    ) == (90, 60, 3600)


def test_main_refuses_a_grace_period_past_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _capture_wait(monkeypatch)
    env = dict(_ENV, GATE_GRACE_SECONDS="120", GATE_DEADLINE_MINUTES="2")
    with pytest.raises(ValueError, match="must end before the deadline"):
        gate.main(env)


# --- the workflow -----------------------------------------------------------


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    return load_workflow(_WORKFLOW)


def test_it_runs_on_every_pull_request_to_main(
    workflow: dict[str, Any],
) -> None:
    on = triggers(workflow)
    assert set(on) == {"pull_request"}
    pr = on["pull_request"]
    assert pr["branches"] == ["main"]
    assert "paths" not in pr and "paths-ignore" not in pr
    assert set(pr["types"]) == {
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
        "edited",
    }


def test_its_one_job_is_named_ci_gate(workflow: dict[str, Any]) -> None:
    jobs = workflow["jobs"]
    assert len(jobs) == 1
    (job,) = jobs.values()
    assert job["name"] == "CI gate"
    assert "if" not in job


def test_it_holds_read_permissions_only(workflow: dict[str, Any]) -> None:
    assert workflow["permissions"] == {
        "actions": "read",
        "checks": "read",
        "contents": "read",
    }


def test_a_new_push_cancels_the_running_gate(workflow: dict[str, Any]) -> None:
    concurrency = workflow["concurrency"]
    assert concurrency["cancel-in-progress"] is True
    assert "pull_request.number" in concurrency["group"]


def test_its_deadline_ends_before_the_job_cap(
    workflow: dict[str, Any],
) -> None:
    (job,) = workflow["jobs"].values()
    deadline = int(job["env"]["GATE_DEADLINE_MINUTES"])
    assert deadline < job["timeout-minutes"]
    # Two calls of at most two 300 s attempts each still end before the cap.
    attempts = int(job["env"]["GH_RETRY_ATTEMPTS"])
    assert deadline + 2 * attempts * 5 < job["timeout-minutes"]
    script = [s for s in job["steps"] if "run" in s]
    assert [s["run"] for s in script] == [
        "python3 -I .github/scripts/ci_gate.py"
    ]
