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
    green_gate,
    pr_view,
    run_script,
    status_rollup,
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
        # BLOCKED with a green gate is the bypassable kind: a note, no flag.
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
    rules = [green_gate(), pr_view(mergeable, status)]
    result = run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules)
    out = fields(result)
    assert result.returncode == 0, result.stderr
    assert out["verdict"] == [verdict]
    assert out.get("flag", []) == flags
    assert out["merge_state_status"] == [status]
    assert ("note" in out) == (status == "BLOCKED")
    # Only BLOCKED asks about the gate, so only BLOCKED reports it.
    assert ("ci_gate" in out) == (status == "BLOCKED")


@pytest.mark.parametrize(
    ("check_status", "conclusion", "reported"),
    [
        ("COMPLETED", "SUCCESS", "SUCCESS"),
        ("COMPLETED", "FAILURE", "FAILURE"),
        ("COMPLETED", "CANCELLED", "CANCELLED"),
        ("COMPLETED", "TIMED_OUT", "TIMED_OUT"),
        # Still running: no conclusion yet, and the merge waits on it.
        ("IN_PROGRESS", None, "PENDING"),
        ("QUEUED", None, "PENDING"),
    ],
)
def test_a_blocked_pr_splits_on_the_ci_gate(
    tmp_path: Path,
    repo: Path,
    check_status: str,
    conclusion: str | None,
    reported: str,
) -> None:
    """Only a green gate leaves BLOCKED survivable (#5945).

    `main-3 Require CI gate` lists no bypass actor, so any other gate reading
    refuses the merge for every account — pr-verify must not call it clear.
    """
    rules = [
        status_rollup(("CI gate", check_status, conclusion)),
        pr_view(status="BLOCKED"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["ci_gate"] == [reported]
    if reported == "SUCCESS":
        assert out["verdict"] == ["clear"]
        assert "flag" not in out
        assert out["note"] == ["blocked"]
    else:
        assert out["verdict"] == ["blocks-ready"]
        assert out["flag"] == ["CI-GATE-NOT-GREEN"]
        # The note marks the survivable kind, so this one must not carry it.
        assert "note" not in out


def test_a_blocked_pr_with_no_ci_gate_run_blocks(
    tmp_path: Path, repo: Path
) -> None:
    """The case a ruleset hangs on forever: the check never ran (#5942)."""
    rules = [
        status_rollup(("Tests (pytest)", "COMPLETED", "SUCCESS")),
        pr_view(status="BLOCKED"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["ci_gate"] == ["absent"]
    assert out["verdict"] == ["blocks-ready"]
    assert out["flag"] == ["CI-GATE-NOT-GREEN"]


def test_a_blocked_pr_whose_rollup_cannot_be_read_blocks(
    tmp_path: Path, repo: Path
) -> None:
    """A merge gate never clears on missing evidence."""
    rules = [
        {"match": ["pr view", "statusCheckRollup"], "exit": 1},
        pr_view(status="BLOCKED"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["ci_gate"] == ["unknown"]
    assert out["verdict"] == ["blocks-ready"]
    assert out["flag"] == ["CI-GATE-NOT-GREEN"]


@pytest.mark.parametrize(
    ("older", "newer", "reported"),
    [("SUCCESS", "FAILURE", "FAILURE"), ("CANCELLED", "SUCCESS", "SUCCESS")],
)
def test_the_newest_ci_gate_run_is_the_one_that_counts(
    tmp_path: Path, repo: Path, older: str, newer: str, reported: str
) -> None:
    """A superseded run sits beside the live one in the rollup.

    An `edited` event cancels the in-flight gate and starts a fresh one, so the
    head commit carries several `CI gate` runs; GitHub's required-check
    evaluation reads the newest, and so must this (#5971).
    """
    rules = [
        status_rollup(
            ("CI gate", "COMPLETED", older), ("CI gate", "COMPLETED", newer)
        ),
        pr_view(status="BLOCKED"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["ci_gate"] == [reported]


def test_a_red_check_beside_a_green_ci_gate_is_the_gates_business(
    tmp_path: Path, repo: Path
) -> None:
    """The gate judges the other checks, so pr-verify reads only the gate."""
    rules = [
        status_rollup(
            ("Tests (pytest)", "COMPLETED", "FAILURE"),
            ("CI gate", "COMPLETED", "SUCCESS"),
        ),
        pr_view(status="BLOCKED"),
    ]
    out = fields(run_script(tmp_path, MERGE, "7", cwd=repo, rules=rules))
    assert out["ci_gate"] == ["SUCCESS"]
    assert out["verdict"] == ["clear"]
    assert "flag" not in out


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
    tmp_path: Path,
    repo: Path,
    rules: list[dict],
    *args: str,
    parts: int = 1,
) -> tuple[int, dict[str, list[str]]]:
    """Run the gate, telling it how many test parts to expect.

    ``parts`` is pinned per case rather than read off `python-app.yml`: the
    matrix is rebalanced from measured durations, and a table that inherited
    its length would fail on a rebalance that broke nothing.
    """
    env = {**_ONE_POLL, "VERIFY_CI_INTEGRATION_PARTS": str(parts)}
    result = run_script(
        tmp_path, CI, "7", *args, cwd=repo, rules=rules, env=env
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
    ("checks", "parts", "verdict", "bucket"),
    [
        ((("Tests (pytest)", "pass"),), 1, "ci-green", "pass"),
        ((("Tests (pytest)", "skipping"), ("Build", "pass")), 1, "ci-failing", "skipping"),
        ((("Build", "pass"),), 1, "ci-failing", "missing"),
        # The job is a matrix, so each part reports under its own check name
        # (TB-11-002). The gate matches the prefix and needs every part.
        ((("Tests (pytest) core", "pass"), ("Tests (pytest) rest", "pass")), 2, "ci-green", "pass"),
        ((("Tests (pytest) core", "pass"), ("Tests (pytest) rest", "skipping")), 2, "ci-failing", "skipping"),
        # One green part out of four is not a suite that ran: a prefix match
        # with no count would read `all(. == "pass")` over it as a pass.
        ((("Tests (pytest) core", "pass"),), 4, "ci-failing", "incomplete"),
        # A check with no name must not make the match raise, and a check with
        # no bucket must not print `null` as its verdict.
        (((None, "pass"), ("Tests (pytest) core", None)), 1, "ci-failing", "unknown"),
        # Four reports of one part's name are one part. Counting array
        # elements instead of distinct names would call this `pass`.
        ((("Tests (pytest) core", "pass"), ("Tests (pytest) core", "pass")), 2, "ci-failing", "incomplete"),
        # No part count at all: the gate refuses rather than defaulting to 1,
        # which would admit one green part as the whole suite.
        ((("Tests (pytest) core", "pass"),), 0, "ci-failing", "unknown-parts"),
    ],
)  # fmt: skip
def test_integration_needs_every_pytest_check_to_have_passed(
    tmp_path: Path,
    repo: Path,
    checks: tuple[tuple[str, str], ...],
    parts: int,
    verdict: str,
    bucket: str,
) -> None:
    _, out = _ci(
        tmp_path, repo, _checks(*checks), "--integration", parts=parts
    )
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
