"""pr-verify's Phase 2 and Phase 3 tables, as scripts (PAD-18-005).

`verify-merge-gate.sh` maps one `merge-state.sh` reading onto pr-verify's merge
flags; `verify-ci-gate.sh` maps `wait-for-ci.sh` onto its CI verdicts. Both run
against the stand-in `gh` of `_script_sandbox.py`, one case per table row.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test.metadata._script_sandbox import (
    clean_env,
    commit,
    fields,
    git,
    pr_view,
    run_script,
)

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="the gate scripts need jq"
)

MERGE = "verify-merge-gate.sh"
CI = "verify-ci-gate.sh"


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A PR branch one commit ahead of a main that has since moved on."""
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    commit(work, "a.txt", "a\n", "base")
    git(work, "checkout", "-qb", "task/7-x")
    commit(work, "b.txt", "b\n")
    git(work, "checkout", "-q", "main")
    commit(work, "c.txt", "c\n", "main moves")
    git(work, "checkout", "-q", "task/7-x")
    return work


def _labels(*names: str) -> dict:
    return {
        "match": ["pr view", "labels"],
        "stdout": json.dumps({"labels": [{"name": n} for n in names]}),
    }


@pytest.mark.parametrize(
    ("mergeable", "status", "verdict", "flags"),
    [
        ("MERGEABLE", "CLEAN", "clear", []),
        ("CONFLICTING", "DIRTY", "conflicts-found", ["MERGE-CONFLICT"]),
        ("CONFLICTING", "CLEAN", "conflicts-found", ["MERGE-CONFLICT"]),
        # DIRTY is the stronger signal, even when `mergeable` disagrees.
        ("MERGEABLE", "DIRTY", "conflicts-found", ["MERGE-CONFLICT"]),
        ("UNKNOWN", "UNKNOWN", "pending-merge-check", ["MERGE-STATE-UNKNOWN"]),
        ("MERGEABLE", "BEHIND", "blocks-ready", ["BRANCH-BEHIND"]),
        ("MERGEABLE", "BLOCKED", "clear", []),
    ],
)
def test_merge_gate_maps_each_row(
    tmp_path: Path,
    repo: Path,
    mergeable: str,
    status: str,
    verdict: str,
    flags: list[str],
) -> None:
    result = run_script(
        tmp_path, MERGE, "7", cwd=repo, rules=[pr_view(mergeable, status)]
    )
    out = fields(result)
    assert result.returncode == 0, result.stderr
    assert out["verdict"] == [verdict]
    assert out.get("flag", []) == flags
    assert out["merge_state_status"] == [status]
    assert ("note" in out) == (status == "BLOCKED")


def test_a_branch_behind_its_base_that_github_calls_clean_is_clear(
    tmp_path: Path, repo: Path
) -> None:
    """No base-tip containment check of its own (PAD-18-005)."""
    contains_main = subprocess.run(
        ["git", "merge-base", "--is-ancestor", "main", "HEAD"],
        cwd=repo,
        check=False,
        env=clean_env(),
    )
    assert contains_main.returncode == 1  # the branch lacks main's tip
    result = run_script(tmp_path, MERGE, "7", cwd=repo, rules=[pr_view()])
    assert fields(result)["verdict"] == ["clear"]


@pytest.mark.parametrize("labels", [("needs-rebase",), ("docs",)])
def test_a_draft_blocks_and_reports_its_needs_rebase_label(
    tmp_path: Path, repo: Path, labels: tuple[str, ...]
) -> None:
    rules = [_labels(*labels), pr_view(status="DRAFT")]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["verdict"] == ["blocks-ready"]
    assert out["flag"] == ["PR-IS-DRAFT"]
    assert out["needs_rebase"] == [str("needs-rebase" in labels).lower()]


def test_a_draft_whose_labels_cannot_be_read_reports_unknown(
    tmp_path: Path, repo: Path
) -> None:
    rules = [
        {"match": ["pr view", "labels"], "exit": 1},
        pr_view(status="DRAFT"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["verdict"] == ["blocks-ready"]
    assert out["needs_rebase"] == ["unknown"]


def test_a_conflict_without_a_fetchable_base_says_evidence_is_unavailable(
    tmp_path: Path, repo: Path
) -> None:
    """`repo` has no origin remote, so the evidence fetch fails."""
    rules = [pr_view("CONFLICTING", "DIRTY")]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["verdict"] == ["conflicts-found"]
    assert out["conflict_evidence"] == ["unavailable"]
    assert "conflict" not in out


def test_a_conflict_with_no_base_ref_says_evidence_is_unavailable(
    tmp_path: Path, repo: Path
) -> None:
    rules = [pr_view("CONFLICTING", "DIRTY", base="")]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["verdict"] == ["conflicts-found"]
    assert out["conflict_evidence"] == ["unavailable"]


def test_markers_alone_are_evidence_enough(tmp_path: Path, repo: Path) -> None:
    commit(repo, "m.txt", "<<<<<<< HEAD\n")
    result = run_script(
        tmp_path, MERGE, "7", "--check-markers", cwd=repo, rules=[pr_view()]
    )
    out = fields(result)
    assert out["marker"] == ["m.txt:1"]
    assert "conflict_evidence" not in out


def test_a_gh_failure_is_unknown_not_clear(tmp_path: Path, repo: Path) -> None:
    rules = [{"match": ["pr view"], "stdout": "", "exit": 1}]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["verdict"] == ["pending-merge-check"]
    assert out["flag"] == ["MERGE-STATE-UNKNOWN"]


def test_surviving_conflict_markers_are_a_conflict(
    tmp_path: Path, repo: Path
) -> None:
    commit(repo, "m.txt", "ok\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> main\n")
    commit(repo, "h.md", "Title\n=======\n")
    result = run_script(
        tmp_path, MERGE, "7", "--check-markers", cwd=repo, rules=[pr_view()]
    )
    out = fields(result)
    assert out["verdict"] == ["conflicts-found"]
    assert out["flag"] == ["MERGE-CONFLICT"]
    assert out["marker"] == ["m.txt:2", "m.txt:6"]


def test_markers_are_not_checked_unless_asked(
    tmp_path: Path, repo: Path
) -> None:
    commit(repo, "m.txt", "<<<<<<< HEAD\n")
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=[pr_view()]))
    assert out["verdict"] == ["clear"]


def _clone_behind_origin(tmp_path: Path, name: str) -> Path:
    """A PR branch cut from a fetchable origin whose main changed `s.txt`."""
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init", "-q", "-b", "main")
    commit(seed, "s.txt", "a\n", "base")
    git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    commit(seed, "s.txt", "MAIN\n", "main moves")
    git(seed, "push", "-q", str(origin), "main")
    work = tmp_path / "work"
    git(tmp_path, "clone", "-q", str(origin), str(work))
    git(work, "checkout", "-qb", "task/7-x", "HEAD~1")
    commit(work, name, "BRANCH\n")
    return work


def test_a_conflict_lists_the_trial_merge_evidence(tmp_path: Path) -> None:
    work = _clone_behind_origin(tmp_path, "s.txt")
    rules = [pr_view("CONFLICTING", "DIRTY")]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=work, rules=rules))
    assert out["verdict"] == ["conflicts-found"]
    assert len(out["conflict"]) == 1
    assert "s.txt" in out["conflict"][0]
    assert "conflict_evidence" not in out


def test_a_stale_dirty_whose_trial_merge_is_clean_says_evidence_is_unavailable(
    tmp_path: Path,
) -> None:
    """The fetch succeeds, but the trial merge names no CONFLICT."""
    work = _clone_behind_origin(tmp_path, "other.txt")
    rules = [pr_view("MERGEABLE", "DIRTY")]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=work, rules=rules))
    assert out["verdict"] == ["conflicts-found"]
    assert out["conflict_evidence"] == ["unavailable"]
    assert "conflict" not in out


def test_merge_gate_refuses_an_unknown_option(
    tmp_path: Path, repo: Path
) -> None:
    result = run_script(tmp_path, MERGE, "7", "--bogus", cwd=repo, rules=[])
    assert result.returncode == 2
    assert "verdict" not in fields(result)


# --- verify-ci-gate.sh --------------------------------------------------------

# One poll, no sleep: wait-for-ci.sh makes TIMEOUT*60/SLEEP attempts.
_ONE_POLL = {"WAIT_CI_TIMEOUT_MINUTES": "1", "WAIT_CI_SLEEP": "60"}


def _checks(*checks: tuple[str, str]) -> list[dict]:
    """Rules for wait-for-ci.sh: a PR head on another branch, then the checks."""
    return [
        {"match": ["pr view", "headRefName"], "stdout": "task/other\n"},
        {
            "match": ["pr checks"],
            "stdout": json.dumps(
                [{"name": n, "bucket": b, "state": b} for n, b in checks]
            ),
        },
    ]


def _ci(
    tmp_path: Path, repo: Path, rules: list[dict], *args: str
) -> tuple[int, dict[str, list[str]]]:
    result = run_script(
        tmp_path, CI, "7", *args, cwd=repo, rules=rules, env=_ONE_POLL
    )
    return result.returncode, fields(result)


@pytest.mark.parametrize(
    ("checks", "verdict", "failing"),
    [
        ((("Tests (pytest)", "pass"), ("Lint (ruff)", "skipping")), "ci-green", []),
        ((("Tests (pytest)", "fail"), ("Lint (ruff)", "pass")), "ci-failing", ["Tests (pytest)"]),
        ((("Build", "cancel"),), "ci-failing", ["Build"]),
        ((("Tests (pytest)", "pending"),), "ci-pending", []),
    ],
)  # fmt: skip
def test_ci_gate_maps_each_row(
    tmp_path: Path,
    repo: Path,
    checks: tuple[tuple[str, str], ...],
    verdict: str,
    failing: list[str],
) -> None:
    rc, out = _ci(tmp_path, repo, _checks(*checks))
    assert rc == 0
    assert out["verdict"] == [verdict]
    assert out.get("failing_check", []) == failing
    assert "integration" not in out


@pytest.mark.parametrize(
    ("checks", "verdict", "bucket"),
    [
        ((("Tests (pytest)", "pass"),), "ci-green", "pass"),
        ((("Tests (pytest)", "skipping"), ("Build", "pass")), "ci-failing", "skipping"),
        ((("Build", "pass"),), "ci-failing", "missing"),
    ],
)  # fmt: skip
def test_integration_needs_the_pytest_check_to_have_passed(
    tmp_path: Path,
    repo: Path,
    checks: tuple[tuple[str, str], ...],
    verdict: str,
    bucket: str,
) -> None:
    _, out = _ci(tmp_path, repo, _checks(*checks), "--integration")
    assert out["verdict"] == [verdict]
    assert out["integration"] == [bucket]


def test_a_gh_error_while_waiting_is_pending(
    tmp_path: Path, repo: Path
) -> None:
    rules = [*_checks()[:1], {"match": ["pr checks"], "exit": 1}]
    _, out = _ci(tmp_path, repo, rules, "--integration")
    assert out["verdict"] == ["ci-pending"]
    assert out["wait_exit"] == ["2"]
    assert "integration" not in out


def test_ci_gate_refuses_an_unknown_option(tmp_path: Path, repo: Path) -> None:
    rc, out = _ci(tmp_path, repo, [], "--bogus")
    assert rc == 2
    assert "verdict" not in out
