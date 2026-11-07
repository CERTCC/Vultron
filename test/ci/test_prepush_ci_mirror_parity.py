"""The local CI mirror accounts for every pull-request CI step (PAD-18-022).

``prepush-ci-mirror`` is only as good as its registry. A workflow step added
to ``.github/workflows/`` and not to the registry would be one more check the
mirror silently misses, which is the drift #5580 exists to stop. So every
step a ``pull_request`` run can execute is mirrored, or excluded with a
reason, and the registry names no step that does not run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.planning.ci_mirror import (
    EXCLUSIONS,
    MIRROR_CHECKS,
    parity_problems,
)
from vultron.metadata.planning.ci_mirror._registry import MirrorCheck

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.spec("PAD-18-022")
def test_every_pull_request_step_is_mirrored_or_excluded():
    problems = parity_problems(REPO_ROOT, MIRROR_CHECKS, EXCLUSIONS)
    assert not problems, "\n".join(problems)


@pytest.mark.spec("PAD-18-022")
def test_the_registry_mirrors_something():
    # A parse that found no workflow would make the parity check vacuous.
    assert sum(1 for c in MIRROR_CHECKS if c.step is not None) >= 20


def _workflow(root: Path, name: str, body: str) -> None:
    folder = root / ".github" / "workflows"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(body, encoding="utf-8")


_WORKFLOW = """\
on:
  pull_request:
    paths: ["src/**"]
  push:
jobs:
  check:
    steps:
      - uses: actions/checkout@abc
      - name: Lint
        run: make lint
      - name: Deploy
        run: make deploy
"""


@pytest.mark.spec("PAD-18-022")
def test_a_new_step_neither_mirrored_nor_excluded_fails(tmp_path: Path):
    _workflow(tmp_path, "ci.yml", _WORKFLOW)
    checks = [MirrorCheck("lint", "ci.yml::check::Lint")]
    exclusions = {"uses:actions/checkout": "the checkout itself"}

    problems = parity_problems(tmp_path, checks, exclusions)

    assert problems == [
        "ci.yml::check::Deploy: a pull_request step neither mirrored nor "
        "excluded; add a MirrorCheck or an EXCLUSIONS entry with its reason"
    ]


@pytest.mark.spec("PAD-18-022")
def test_a_workflow_without_a_pull_request_trigger_is_ignored(tmp_path: Path):
    _workflow(
        tmp_path, "cron.yml", _WORKFLOW.replace("pull_request", "schedule")
    )

    assert parity_problems(tmp_path, [], {}) == []


@pytest.mark.spec("PAD-18-022")
@pytest.mark.parametrize(
    ("checks", "exclusions", "expected"),
    [
        pytest.param(
            [MirrorCheck("lint", "ci.yml::check::Gone")],
            {"ci.yml": "all of it"},
            "ci.yml::check::Gone: mirrored by ['lint'] but no such step runs",
            id="stale-mirror-key",
        ),
        pytest.param(
            [],
            {"ci.yml": "all of it", "ci.yml::other": "no such job"},
            "ci.yml::other: an exclusion that matches no step",
            id="stale-exclusion-key",
        ),
        pytest.param(
            [MirrorCheck("lint", "ci.yml::check::Lint")],
            {"ci.yml": "all of it"},
            "ci.yml::check::Lint: both mirrored and excluded by 'ci.yml'",
            id="mirrored-and-excluded",
        ),
        pytest.param(
            [MirrorCheck("lint", "ci.yml::check::Lint", command=("x",))],
            {"ci.yml::check::Deploy": "r", "uses:actions/checkout": "r"},
            "lint: a command differing from CI needs a note",
            id="command-without-note",
        ),
        pytest.param(
            [MirrorCheck("lint", "ci.yml::check::Lint", paths=("a",))],
            {"ci.yml::check::Deploy": "r", "uses:actions/checkout": "r"},
            "lint: narrowed paths need a reason",
            id="narrowed-without-reason",
        ),
        pytest.param(
            [],
            {"ci.yml": " "},
            "ci.yml: an exclusion with no reason",
            id="blank-reason",
        ),
    ],
)
def test_registry_breaches_are_reported(
    tmp_path: Path,
    checks: list[MirrorCheck],
    exclusions: dict[str, str],
    expected: str,
):
    _workflow(tmp_path, "ci.yml", _WORKFLOW)

    assert expected in parity_problems(tmp_path, checks, exclusions)


@pytest.mark.spec("PAD-18-022")
def test_a_verbatim_check_of_a_step_using_an_expression_is_refused(
    tmp_path: Path,
):
    _workflow(
        tmp_path,
        "ci.yml",
        _WORKFLOW.replace("make lint", "make lint ${{ github.ref }}"),
    )
    checks = [MirrorCheck("lint", "ci.yml::check::Lint")]
    exclusions = {"ci.yml::check::Deploy": "r", "uses:actions/checkout": "r"}

    problems = parity_problems(tmp_path, checks, exclusions)

    assert len(problems) == 1
    assert "names a GitHub expression" in problems[0]


@pytest.mark.spec("PAD-18-022")
def test_a_step_inside_a_local_action_is_its_own_step(tmp_path: Path):
    action = tmp_path / ".github" / "actions" / "gate"
    action.mkdir(parents=True)
    (action / "action.yml").write_text(
        "runs:\n  using: composite\n  steps:\n"
        "    - name: Inner\n      shell: bash\n      run: make inner\n",
        encoding="utf-8",
    )
    _workflow(
        tmp_path,
        "ci.yml",
        "on: pull_request\njobs:\n  check:\n    steps:\n"
        "      - name: Outer\n        uses: ./.github/actions/gate\n",
    )

    assert parity_problems(tmp_path, [], {}) == [
        "ci.yml::check::Outer > Inner: a pull_request step neither mirrored "
        "nor excluded; add a MirrorCheck or an EXCLUSIONS entry with its reason"
    ]


@pytest.mark.spec("PAD-18-022")
def test_two_steps_with_one_label_are_both_counted(tmp_path: Path):
    _workflow(
        tmp_path,
        "ci.yml",
        "on: pull_request\njobs:\n  j:\n    steps:\n"
        "      - run: make a\n      - run: make b\n",
    )
    checks = [MirrorCheck("a", "ci.yml::j::<unnamed step>")]

    assert parity_problems(tmp_path, checks, {}) == [
        "ci.yml::j::<unnamed step> #2: a pull_request step neither mirrored "
        "nor excluded; add a MirrorCheck or an EXCLUSIONS entry with its reason"
    ]


@pytest.mark.spec("PAD-18-022")
def test_a_reusable_workflow_job_is_a_step(tmp_path: Path):
    _workflow(
        tmp_path,
        "ci.yml",
        "on: pull_request\njobs:\n  call:\n"
        "    uses: ./.github/workflows/shared.yml\n",
    )

    assert parity_problems(tmp_path, [], {}) == [
        "ci.yml::call::./.github/workflows/shared.yml: a pull_request step "
        "neither mirrored nor excluded; add a MirrorCheck or an EXCLUSIONS "
        "entry with its reason"
    ]


@pytest.mark.spec("PAD-18-022")
def test_a_pull_request_target_workflow_is_counted(tmp_path: Path):
    _workflow(
        tmp_path,
        "ci.yml",
        _WORKFLOW.replace("pull_request:", "pull_request_target:"),
    )

    assert len(parity_problems(tmp_path, [], {})) == 3


@pytest.mark.spec("PAD-18-022")
def test_an_expression_in_step_env_needs_an_override_or_a_reason(
    tmp_path: Path,
):
    _workflow(
        tmp_path,
        "ci.yml",
        "on: pull_request\njobs:\n  j:\n    steps:\n      - name: Lint\n"
        "        env:\n          TOKEN: ${{ secrets.T }}\n        run: make lint\n",
    )
    bare = [MirrorCheck("lint", "ci.yml::j::Lint")]
    reasoned = [
        MirrorCheck("lint", "ci.yml::j::Lint", drops_env={"TOKEN": "r"})
    ]
    overridden = [MirrorCheck("lint", "ci.yml::j::Lint", env={"TOKEN": "x"})]

    [problem] = parity_problems(tmp_path, bare, {})
    assert "TOKEN names a GitHub expression" in problem
    assert parity_problems(tmp_path, reasoned, {}) == []
    assert parity_problems(tmp_path, overridden, {}) == []
