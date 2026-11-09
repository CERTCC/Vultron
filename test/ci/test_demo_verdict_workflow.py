"""CI records every scenario at base and head and compares (DEMOCI-11-054).

``demo-verdict.yml`` is the pull-request job that answers whether a change
under ``vultron/demo/`` moves what a scenario records or checks.  Its verdict
is ``compare-demo-runs``'s exit status, so these tests pin the parts of the
job the command cannot police: the two commits it records, the single
directory per side, the opt-out label it reads, and the three ways a job like
this reports a vacuous pass — a swallowed exit status, a summary written only
on success, and an artifact name a re-run can collide with.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import (
    REPO_ROOT as _REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    neutering,
    triggers,
)
from vultron.demo.recordings.compare import (
    DIFFERENT_EXIT_CODE,
    NO_SCENARIOS_EXIT_CODE,
)
from vultron.demo.recordings.topology import (
    COMPOSE_PATH as TOPOLOGY_COMPOSE_PATH,
)
from vultron.metadata.planning.ci_mirror import EXCLUSIONS

_WORKFLOW = WORKFLOWS_DIR / "demo-verdict.yml"
_JOB = "demo-verdict"

#: The exclusion key of the whole workflow in the mirror's registry.
_EXCLUSION_KEY = "demo-verdict.yml"

#: The label DEMOCI-11-063 names.  Spelled out here rather than read from the
#: workflow: a typo in the workflow would otherwise agree with itself, and a
#: label nobody can apply fails nothing.
_OPT_OUT_LABEL = "demo-verdict-change"

#: The expression that reads the label off the event payload.  One occurrence,
#: so neither later step names the label again (CS-22-001).
_LABEL_EXPRESSION = (
    f"contains(github.event.pull_request.labels.*.name, '{_OPT_OUT_LABEL}')"
)

#: The command the job's verdict comes from.
_COMMAND = "compare-demo-runs"


def _workflow() -> dict[str, Any]:
    return load_workflow(_WORKFLOW)


def _job() -> dict[str, Any]:
    job = _workflow()["jobs"][_JOB]
    assert isinstance(job, dict)
    return job


def _steps() -> list[dict[str, Any]]:
    return [s for s in _job()["steps"] if isinstance(s, dict)]


def _step(name: str) -> dict[str, Any]:
    [step] = [s for s in _steps() if s.get("name") == name]
    return step


def _text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


@pytest.mark.spec("DEMOCI-11-054")
def test_it_runs_on_a_pull_request_that_changes_the_demo() -> None:
    on = triggers(_workflow())
    pull_request = on["pull_request"]

    assert pull_request["branches"] == ["main"]
    assert "vultron/demo/**" in pull_request["paths"]
    # `load_topology` reads the compose file for each slot's URL and default
    # case roles, so a change there changes what every scenario records; a
    # filter that missed it would leave the check installed and unreachable
    # on a pull-request shape it exists to police (the #4506 shape).
    assert (
        str(TOPOLOGY_COMPOSE_PATH.relative_to(_REPO_ROOT))
        in (pull_request["paths"])
    )
    # A change to the job itself re-validates the job.
    assert ".github/workflows/demo-verdict.yml" in pull_request["paths"]


@pytest.mark.spec("DEMOCI-11-063")
def test_adding_or_removing_the_label_re_runs_the_job() -> None:
    """The opt-out has to take effect without a hand re-run.

    A ``pull_request`` run on the default types alone would keep a red
    verdict after the label was applied, and a green one after it was
    removed — the second is the one that matters (DEMOCI-11-061).
    """
    types = triggers(_workflow())["pull_request"]["types"]

    assert {"labeled", "unlabeled"} <= set(types)
    # The defaults are not inherited once `types` is given.
    assert {"opened", "synchronize", "reopened"} <= set(types)


@pytest.mark.spec("CISEC-05-001")
def test_it_runs_on_no_event_that_would_need_notify_failure() -> None:
    """Pull requests only, so CISEC-05 does not apply (as `guard-tests.yml`).

    A ``workflow_dispatch`` would also run with no base commit and no labels,
    and the ``CI gate`` keeps only the newest run per workflow, so that empty
    verdict would stand in for the real one.
    """
    assert set(triggers(_workflow())) == {"pull_request"}


@pytest.mark.spec("TB-14-006")
def test_the_job_has_a_named_status_and_a_cap() -> None:
    job = _job()

    # DEMOCI-11-054's "its own named status" is this `name:`.
    assert job["name"] == "Demo verdict unchanged (ledger and checks)"
    assert isinstance(job["timeout-minutes"], int)
    # Above two whole-tree recordings plus two `uv sync` runs, and under the
    # `CI gate`'s 60-minute deadline, which a longer job would outlast.
    assert 15 <= job["timeout-minutes"] <= 45


@pytest.mark.spec("DEMOCI-11-054")
def test_the_two_sides_are_the_merge_base_and_the_head_commit() -> None:
    checkout = _steps()[0]
    worktree = _step("Check out the merge base in a worktree")

    # The head commit itself, not GitHub's synthesized merge commit.
    assert (
        checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha }}"
    )
    # Full history, or `git merge-base` has nothing to resolve against.
    assert checkout["with"]["fetch-depth"] == 0
    # The merge base, not the base branch's tip: a tip that moved ahead would
    # attribute main's own verdict changes to this pull request.
    assert "git merge-base" in worktree["run"]
    assert "git worktree add" in worktree["run"]


@pytest.mark.spec("DEMOCI-11-054")
def test_the_base_side_runs_the_base_commit_s_own_code() -> None:
    """Recorded from the worktree, with that commit's own locked environment.

    Recording the base side with the head's installed code would compare the
    head with itself and report every scenario unchanged.
    """
    step = _step("Record every scenario at the merge base")

    assert step["working-directory"] == "${{ env.BASE_TREE }}"
    assert "uv sync --dev --frozen" in step["run"]
    assert f"{_COMMAND} --write" in step["run"]


@pytest.mark.spec("DEMOCI-11-054")
@pytest.mark.parametrize(
    ("step_name", "variable"),
    [
        ("Record every scenario at the merge base", "$BASE_RUNS"),
        ("Record every scenario at the head", "$HEAD_RUNS"),
    ],
)
def test_each_side_is_written_to_its_own_directory(
    step_name: str, variable: str
) -> None:
    """One directory in both positions compares a side with itself (#5589)."""
    assert f'{_COMMAND} --write "{variable}"' in _step(step_name)["run"]


@pytest.mark.spec("DEMOCI-11-054")
@pytest.mark.parametrize(
    "step_name",
    [
        "Record every scenario at the merge base",
        "Record every scenario at the head",
    ],
)
def test_each_side_records_every_registered_scenario(step_name: str) -> None:
    """No ``--scenario``: the command's default is the whole registry.

    A narrowed side would leave the scenarios it dropped compared by nothing,
    and the comparison cannot tell a narrowed side from an unchanged one.
    """
    assert "--scenario" not in _step(step_name)["run"]


@pytest.mark.spec("DEMOCI-11-063")
def test_the_opt_out_label_is_read_once_from_the_event() -> None:
    """One declaration, so no step can read a different label (CS-22-001)."""
    text = _text()

    assert text.count(_LABEL_EXPRESSION) == 1
    assert _LABEL_EXPRESSION in str(
        _step("Name the scratch paths and read the opt-out label")["env"][
            "ALLOW_DIFFERENCE"
        ]
    )


@pytest.mark.spec("DEMOCI-11-063")
def test_the_label_adds_allow_difference_and_nothing_else() -> None:
    run = _step("Compare the two runs")["run"]

    assert "--allow-difference" in run
    assert 'if [ "$ALLOW_DIFFERENCE" = "true" ]' in run
    # Both sides of the comparison, named by their own variables.
    assert '--base "$BASE_RUNS" --head "$HEAD_RUNS"' in run


@pytest.mark.spec("DEMOCI-11-061")
def test_the_comparison_s_exit_status_is_the_job_s_verdict() -> None:
    """The command decides; the job only propagates.

    ``compare-demo-runs`` already exits 4 on a difference, 3 on an empty
    scenario set (DEMOCI-11-062) and 1 on a crashed recorder, so a job that
    re-derived the verdict from the log would be a second place for the three
    to be confused.
    """
    step = _step("Compare the two runs")

    assert 'exit "$status"' in step["run"]
    # Nothing makes the step unable to fail the run: no `continue-on-error`,
    # no `|| true`, no skipping `if:`.
    assert neutering(step) == []


@pytest.mark.spec("DEMOCI-11-062")
def test_the_recording_steps_cannot_swallow_an_empty_scenario_set() -> None:
    """``--write`` exits 3 on an empty selection, and that must fail the job."""
    for name in (
        "Record every scenario at the merge base",
        "Record every scenario at the head",
    ):
        assert neutering(_step(name)) == [], name


@pytest.mark.spec("DEMOCI-11-064")
def test_the_difference_reaches_the_summary_on_both_arms() -> None:
    """Printed whether the job fails on the difference or admits it.

    On an unlabelled pull request the comparison step failed, so a summary
    step conditioned on success would write nothing on exactly the run whose
    diff a reader needs (DEMOCI-11-061). On a labelled one the comparison
    passed and the diff still has to land (DEMOCI-11-064).
    """
    step = _step("Write the comparison to the job summary")

    assert step["if"] == "${{ !cancelled() }}"
    assert '"$GITHUB_STEP_SUMMARY"' in step["run"]
    assert neutering(step) == []


@pytest.mark.spec("DEMOCI-11-064")
def test_an_oversized_diff_truncates_with_a_pointer() -> None:
    """A step summary over 1 MiB is rejected whole, losing the diff.

    Both limits: a line count alone is cleared by a normalized ledger entry,
    which is one JSON object on one line, so a few hundred lines can carry a
    megabyte; a byte count alone is the other half of the same cap.
    """
    step = _step("Write the comparison to the job summary")
    env = step["env"]

    assert int(env["SUMMARY_LINE_LIMIT"]) > 0
    # Under GitHub's 1 MiB, with room for the surrounding prose.
    assert 0 < int(env["SUMMARY_BYTE_LIMIT"]) < 1024 * 1024
    assert 'head -n "$SUMMARY_LINE_LIMIT"' in step["run"]
    assert 'head -c "$SUMMARY_BYTE_LIMIT"' in step["run"]
    assert "truncated at" in step["run"]
    assert "artifact" in step["run"]


@pytest.mark.spec("DEMOCI-11-061")
def test_the_traces_artifact_name_carries_the_run_attempt() -> None:
    """A re-run uploads beside the earlier attempt under the same name (#4577)."""
    step = _step("Upload both sides' traces")

    assert step["with"]["name"] == (
        "demo-verdict-runs-${{ github.run_attempt }}"
    )
    # Uploaded on a difference the label admitted, too: that run is green, so
    # `failure()` alone would leave the admitted diff with no trace to read.
    assert "steps.compare.outputs.differs == 'true'" in step["if"]
    assert "failure()" in step["if"]


@pytest.mark.spec("PAD-18-022")
def test_the_mirror_leaves_the_job_to_ci_with_a_reason() -> None:
    reason = EXCLUSIONS[_EXCLUSION_KEY]

    assert "CI" in reason
    assert "PAD-18-023" in reason


@pytest.mark.spec("DEMOCI-11-054")
def test_the_head_side_records_the_head_tree() -> None:
    """The head step runs in the checkout, so it declares no directory.

    Its correctness rests on the *absence* of ``working-directory``, which is
    the one thing a test has to say out loud: adding the base worktree's
    directory there makes both sides record the merge base, so the comparison
    reports every scenario unchanged and the job is green forever, with every
    other assertion in this file still passing (the #5589 shape).
    """
    base = _step("Record every scenario at the merge base")
    head = _step("Record every scenario at the head")

    assert "working-directory" not in head
    assert base["working-directory"] != head.get("working-directory")


@pytest.mark.spec("DEMOCI-11-063")
def test_the_differs_signal_matches_what_the_command_prints() -> None:
    """The grep is a prefix of *both* of the command's messages.

    The admitted arm is the one `failure()` does not cover, so if a reword
    left the grep matching only the failing message, a green admitted run
    would upload no traces — the evidence DEMOCI-11-064 asks for.
    """
    run = _step("Compare the two runs")["run"]
    [grep_line] = [
        line for line in run.splitlines() if line.strip().startswith("if grep")
    ]
    pattern = grep_line.split("'")[1].lstrip("^")
    source = (
        _REPO_ROOT / "vultron" / "demo" / "recordings" / "compare.py"
    ).read_text(encoding="utf-8")
    printed = re.findall(r'f"(Differing scenarios[^"]*)"', source)

    # Both arms: the admitted one and the failing one.
    assert len(printed) == 2
    for message in printed:
        assert message.startswith(pattern), (
            f"the job greps {pattern!r}, which {message!r} does not start "
            "with, so the differs signal is false on that arm"
        )


@pytest.mark.spec("DEMOCI-11-062")
def test_the_header_names_the_exit_codes_the_command_uses() -> None:
    """A header that misnames a code misdirects whoever reads a red run."""
    header = _text().split("name: Demo Verdict", 1)[0]

    assert f"exit {DIFFERENT_EXIT_CODE}: a scenario differs" in header
    assert f"exit {NO_SCENARIOS_EXIT_CODE}: the run compared no" in header


@pytest.mark.spec("DEMOCI-11-062")
def test_a_merge_base_without_the_command_fails_on_its_own_code() -> None:
    """Its own code, so the verdict tells "rebase" from "the recorder broke".

    The guard runs before either recording step, or the base pass fails on a
    missing console script instead, with nothing saying why.
    """
    worktree = _step("Check out the merge base in a worktree")
    code = worktree["env"]["STALE_BASE_EXIT_CODE"]

    assert 'exit "$STALE_BASE_EXIT_CODE"' in worktree["run"]
    assert int(code) not in {
        0,
        1,
        2,
        DIFFERENT_EXIT_CODE,
        NO_SCENARIOS_EXIT_CODE,
    }
    names = [s.get("name") for s in _steps()]
    assert names.index("Check out the merge base in a worktree") < names.index(
        "Record every scenario at the merge base"
    )


@pytest.mark.spec("DEMOCI-11-064")
def test_the_traces_artifact_reads_the_declared_paths() -> None:
    """One spelling of each scratch path, not two (CS-22-001).

    A second spelling that drifted would upload an empty artifact while the
    summary tells the reader the whole log is in it.
    """
    step = _step("Upload both sides' traces")
    declared = _step("Name the scratch paths and read the opt-out label")[
        "run"
    ]

    for variable in ("BASE_RUNS", "HEAD_RUNS", "COMPARE_LOG"):
        assert f"{variable}=$RUNNER_TEMP" in declared
        assert "${{ env." + variable + " }}" in step["with"]["path"]
    # `warn`, not `ignore`: a rename has to say so out loud.
    assert step["with"]["if-no-files-found"] == "warn"


@pytest.mark.spec("DEMOCI-11-054")
def test_the_command_the_job_runs_exists() -> None:
    """A renamed console script would leave the job red for the wrong reason."""
    pyproject = (
        Path(_WORKFLOW).resolve().parents[2] / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert f"{_COMMAND}=" in pyproject.replace(" = ", "=")
