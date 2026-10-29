"""Bot-filed issues get a theme label, a ``Theme:`` line and an Epic parent.

Two workflows file issues: the ``notify-failure`` composite action (a
``ci:main-failure`` Bug) and the Demo Recordings workflow (a refresh Task). An
issue either files breaks PAD-01-007, PAD-02-014 and PAD-02-018 unless the
filer sets all three itself (#5435), which both do through
``.github/scripts/ensure-issue-triage.sh``.

The helper is run here against a fake ``gh`` (``test/ci/_fake_gh.py``), and the
issue each filer leaves is checked with the ``theme-fit`` analysis itself, so
a theme retired from the catalog fails here, not on the board.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._fake_gh import (
    UNTRIAGED_ISSUE,
    FakeGh,
    install_fake_gh,
    open_epic,
)
from vultron.metadata.planning.theme_fit.analyze import analyze
from vultron.metadata.planning.theme_fit.model import Ancestor, OpenIssue
from vultron.metadata.planning.themes import load_theme_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"
TRIAGE_HELPER = SCRIPTS_DIR / "ensure-issue-triage.sh"
NOTIFY_ACTION = (
    REPO_ROOT / ".github" / "actions" / "notify-failure" / "action.yml"
)
RECORDINGS_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "demo-recordings.yml"
)

EPIC = 3791
THEME = "theme:test-and-ci"
OUTCOME = "gets the Example workflow passing on main again."
CALL = ("OWNER/REPO", "999", THEME, OUTCOME, str(EPIC), "CI_FAILURE_EPIC")


def _run_helper(gh: FakeGh, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(TRIAGE_HELPER), *args],
        check=False,
        env=gh.env,
        capture_output=True,
        text=True,
    )


def _theme_fit_findings(
    gh: FakeGh, labels: set[str], theme: str, epic: int
) -> list[str]:
    """``theme-fit``'s findings on the issue as the fake ``gh`` left it.

    Its labels are *labels* plus any the helper added, its body the one the
    helper wrote, and its parent *epic* when the helper called
    ``addSubIssue``. The Epic is open and carries *theme*.
    """
    calls = gh.calls()
    added = {
        c.split("--add-label ", 1)[1]
        for c in calls
        if c.startswith("issue edit") and "--add-label" in c
    }
    parented = any("addSubIssue" in c for c in calls)
    filed = OpenIssue(
        number=999,
        title="Filed by a workflow",
        issue_type="Bug",
        labels=frozenset(labels | added),
        body=gh.written_body() or "",
        ancestors=(Ancestor(epic, "Epic"),) if parented else (),
    )
    parent = OpenIssue(
        number=epic,
        title="The Epic",
        issue_type="Epic",
        labels=frozenset({theme}),
        body=f"Theme: {theme} — the Epic's outcome.",
    )
    report = analyze([filed, parent], load_theme_catalog())
    return [f"{f.kind.value}: {f.detail}" for f in report.findings]


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


@pytest.mark.spec("PAD-01-007", "PAD-02-014", "PAD-02-018")
def test_helper_triages_an_untriaged_issue(tmp_path: Path) -> None:
    """An issue with none of the three gets all three, and theme-fit passes."""
    gh = install_fake_gh(tmp_path)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    assert f"issue edit 999 --repo OWNER/REPO --add-label {THEME}" in calls
    body = gh.written_body()
    assert body is not None
    assert body.splitlines()[0] == f"Theme: {THEME} — {OUTCOME}"
    assert "Original body." in body, "The filed body must be kept."
    # A GraphQL query spans several log lines, so read the raw log.
    log = gh.log.read_text()
    assert f"-F number={EPIC} " in log, "The Epic the variable names is read."
    assert log.count("addSubIssue(input") == 1, log
    assert "-f parentId=EPIC_NODE_ID -f childId=ISSUE_NODE_ID" in log, log
    assert _theme_fit_findings(gh, {"ci:main-failure"}, THEME, EPIC) == []


def test_helper_leaves_a_themed_and_parented_issue_alone(
    tmp_path: Path,
) -> None:
    """A person's theme and parent win: the helper changes nothing."""
    issue = UNTRIAGED_ISSUE | {
        "parent": {"number": 1234},
        "labels": {"nodes": [{"name": "theme:dev-workflow"}]},
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    assert not any(c.startswith("issue edit") for c in calls), calls
    log = gh.log.read_text()
    assert "subIssues" not in log and "addSubIssue" not in log, log


def test_helper_leaves_an_issue_a_person_re_themed_unparented(
    tmp_path: Path,
) -> None:
    """Another theme with no parent gets no parent from the bot either.

    The bot's Epic carries the bot's theme, so wiring the issue under it
    would break PAD-02-017; the person who chose the theme picks the parent.
    """
    issue = UNTRIAGED_ISSUE | {
        "labels": {"nodes": [{"name": "theme:dev-workflow"}]},
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    assert not any(c.startswith("issue edit") for c in gh.calls())
    log = gh.log.read_text()
    assert "subIssues" not in log and "addSubIssue" not in log, log


def test_helper_keeps_an_existing_theme_line(tmp_path: Path) -> None:
    """A repair run adds the label without writing the line a second time."""
    line = f"Theme: {THEME} — {OUTCOME}"
    issue = UNTRIAGED_ISSUE | {"body": f"{line}\n\nOriginal body."}
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    assert (
        f"issue edit 999 --repo OWNER/REPO --add-label {THEME}" in gh.calls()
    )
    assert gh.written_body() is None


def test_helper_finishes_a_theme_a_failed_run_left_half_set(
    tmp_path: Path,
) -> None:
    """The issue's own theme label with no ``Theme:`` line gets the line.

    A run that set the label and then failed must not leave the issue
    breaking PAD-02-018 for good.
    """
    issue = UNTRIAGED_ISSUE | {
        "labels": {"nodes": [{"name": "ci:main-failure"}, {"name": THEME}]},
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    body = gh.written_body()
    assert body is not None and body.startswith(f"Theme: {THEME} — ")
    assert not any("--add-label" in c for c in gh.calls())
    assert _theme_fit_findings(gh, {THEME}, THEME, EPIC) == []


def test_helper_does_not_take_a_longer_label_for_its_theme(
    tmp_path: Path,
) -> None:
    """A ``Theme:`` line for a label that merely starts with the theme is
    not the theme's line, so the line is still written."""
    issue = UNTRIAGED_ISSUE | {
        "body": f"Theme: {THEME}-extra — something else.\n\nOriginal body.",
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    body = gh.written_body()
    assert body is not None
    assert body.splitlines()[0] == f"Theme: {THEME} — {OUTCOME}"


@pytest.mark.parametrize("epic", ["", "not-a-number", "0", "-5"])
def test_helper_fails_loudly_without_an_epic_number(
    tmp_path: Path, epic: str
) -> None:
    """An unset or malformed variable is an error naming the variable.

    The theme is still set first, so the issue is only one fix away.
    """
    gh = install_fake_gh(tmp_path)
    result = _run_helper(gh, *CALL[:4], epic, "CI_FAILURE_EPIC")
    assert result.returncode == 1
    assert "::error::" in result.stderr
    assert "CI_FAILURE_EPIC" in result.stderr
    calls = gh.calls()
    assert any("--add-label" in c for c in calls), calls
    assert "addSubIssue" not in gh.log.read_text()


@pytest.mark.parametrize(
    ("epic", "error"),
    [
        (
            open_epic(THEME) | {"issueType": {"name": "Task"}},
            "not an open Epic",
        ),
        (open_epic(THEME) | {"state": "CLOSED"}, "not an open Epic"),
        (open_epic(THEME) | {"issueType": None}, "not an open Epic"),
        (open_epic("theme:dev-workflow"), f"does not carry {THEME}"),
        (open_epic(THEME, sub_issues=100), "GitHub's cap"),
    ],
    ids=["not-an-epic", "closed-epic", "untyped", "other-theme", "full"],
)
def test_helper_refuses_a_parent_that_cannot_take_the_issue(
    tmp_path: Path, epic: dict[str, object], error: str
) -> None:
    """A variable naming anything but an open Epic with room for an issue of
    this theme (PAD-02-017) fails, naming the variable and wiring nothing."""
    gh = install_fake_gh(tmp_path, epic=epic)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 1
    assert error in result.stderr
    assert "CI_FAILURE_EPIC" in result.stderr
    assert "addSubIssue" not in gh.log.read_text()


def test_helper_fails_when_the_epic_lookup_fails(tmp_path: Path) -> None:
    """An API error reading the Epic fails the step, wiring nothing."""
    gh = install_fake_gh(tmp_path, epic_lookup_fails=True)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 1
    assert "::error::Could not read Epic" in result.stderr, result.stderr
    assert "CI_FAILURE_EPIC" in result.stderr
    assert "addSubIssue" not in gh.log.read_text()


@pytest.mark.parametrize(
    ("theme", "outcome"),
    [("test-and-ci", OUTCOME), (THEME, "")],
    ids=["not-a-theme-label", "empty-outcome"],
)
def test_helper_rejects_a_bad_theme_argument(
    tmp_path: Path, theme: str, outcome: str
) -> None:
    """A caller bug fails before any write."""
    gh = install_fake_gh(tmp_path)
    result = _run_helper(gh, "OWNER/REPO", "999", theme, outcome, "1", "V")
    assert result.returncode == 2
    assert gh.calls() == []


# ---------------------------------------------------------------------------
# The two filers
# ---------------------------------------------------------------------------


def _notify_step() -> dict[str, Any]:
    """The notify-failure step that files, updates and closes the issue."""
    action: dict[str, Any] = yaml.safe_load(NOTIFY_ACTION.read_text())
    steps: list[dict[str, Any]] = action["runs"]["steps"]
    (step,) = [s for s in steps if "ISSUE_NUMS" in s.get("run", "")]
    return step


def _recordings_step(name: str) -> dict[str, Any]:
    """The Demo Recordings step called *name*."""
    workflow: dict[str, Any] = yaml.safe_load(RECORDINGS_WORKFLOW.read_text())
    steps: list[dict[str, Any]] = workflow["jobs"]["recordings"]["steps"]
    (step,) = [s for s in steps if s.get("name") == name]
    return step


def _run_notify(gh: FakeGh, epic: str) -> subprocess.CompletedProcess[str]:
    """Run the notify arm's real script, with *epic* as the ``epic`` input."""
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "MODE": "notify",
        "WORKFLOW_LABEL": "ci:workflow-example",
        "WORKFLOW_NAME": "Example",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REF": "refs/heads/main",
        "CI_FAILURE_EPIC": epic,
        "GITHUB_ACTION_PATH": str(NOTIFY_ACTION.parent),
    }
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", str(_notify_step()["run"])],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_notify_failure_takes_the_epic_from_an_input() -> None:
    """The Epic comes in through the ``epic`` input, not ``vars``.

    GitHub documents the ``vars`` context for a workflow step's ``with:``,
    but not inside a composite action's own steps, so each caller passes
    ``vars.CI_FAILURE_EPIC`` in (checked per caller in
    ``test_workflow_failure_notification.py``).
    """
    action: dict[str, Any] = yaml.safe_load(NOTIFY_ACTION.read_text())
    assert "epic" in action["inputs"]
    assert _notify_step()["env"]["CI_FAILURE_EPIC"] == "${{ inputs.epic }}"
    assert "vars." not in NOTIFY_ACTION.read_text().split("runs:", 1)[1]


def test_notify_failure_closes_duplicates_before_an_epic_error(
    tmp_path: Path,
) -> None:
    """An unset Epic still fails the step, but only after the duplicate
    trackers are closed (CISEC-05-003), so one tracker remains."""
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": 5087}, {"number": 5105}]
    )
    result = _run_notify(gh, "")
    assert result.returncode == 1
    assert "CI_FAILURE_EPIC" in result.stderr
    calls = gh.calls()
    assert any(c.startswith("issue close 5105") for c in calls), calls
    assert f"issue edit 5087 --repo OWNER/REPO --add-label {THEME}" in calls


@pytest.mark.spec("PAD-01-007", "PAD-02-014", "PAD-02-018")
@pytest.mark.parametrize(
    ("open_issues", "number"),
    [([], "999"), ([5087], "5087")],
    ids=["create-arm", "comment-arm"],
)
def test_notify_failure_triages_the_issue_it_files(
    tmp_path: Path, open_issues: list[int], number: str
) -> None:
    """AC-1: a ``ci:main-failure`` issue gets theme, line and parent.

    The comment arm repairs an open issue a run before this fix filed bare.
    """
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": n} for n in open_issues]
    )
    result = _run_notify(gh, str(EPIC))
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    assert (
        f"issue edit {number} --repo OWNER/REPO --add-label {THEME}" in calls
    )
    labels = {"ci:main-failure", "ci:workflow-example"}
    assert _theme_fit_findings(gh, labels, THEME, EPIC) == []


@pytest.mark.spec("PAD-01-007", "PAD-02-014", "PAD-02-018")
@pytest.mark.parametrize(
    ("existing", "number"),
    [([], "999"), ([5434], "5434"), ([5434, 5500], "5434")],
    ids=["create-arm", "comment-arm", "comment-arm-oldest"],
)
def test_recordings_workflow_triages_the_task_it_files(
    tmp_path: Path, existing: list[int], number: str
) -> None:
    """AC-2: the refresh Task gets theme, line and parent, on both arms.

    With more than one open, only the oldest is updated.
    """
    step = _recordings_step("File or update the refresh Task")
    env_map = step["env"]
    assert (
        env_map["DEMO_RECORDINGS_EPIC"] == "${{ vars.DEMO_RECORDINGS_EPIC }}"
    ), (
        "The parent Epic must come from the DEMO_RECORDINGS_EPIC repository "
        "variable, not a hard-coded number (#5435)."
    )
    gh = install_fake_gh(
        tmp_path,
        issues_page=[{"number": n} for n in existing],
        epic=open_epic("theme:full-cvd-scenario-coverage"),
    )
    work = tmp_path / "work"
    (work / ".github").mkdir(parents=True)
    (work / ".github" / "scripts").symlink_to(SCRIPTS_DIR)
    (work / "changed.txt").write_text("demo-a\n")
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REFRESH_LABEL": "demo-recordings-stale",
        "DEMO_RECORDINGS_EPIC": "4747",
    }
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", str(step["run"])],
        cwd=work,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    theme = "theme:full-cvd-scenario-coverage"
    calls = gh.calls()
    assert (
        f"issue edit {number} --repo OWNER/REPO --add-label {theme}" in calls
    )
    touched = {
        c.split()[2]
        for c in calls
        if c.startswith(("issue comment", "issue edit"))
    }
    assert touched == {number}, calls
    labels = {"demo-recordings-stale"}
    assert _theme_fit_findings(gh, labels, theme, 4747) == []


def _run_recordings_close(gh: FakeGh) -> subprocess.CompletedProcess[str]:
    step = _recordings_step("Close the refresh Task")
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REFRESH_LABEL": "demo-recordings-stale",
    }
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", str(step["run"])],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_recordings_close_step_closes_every_open_task(tmp_path: Path) -> None:
    """Current recordings close each open refresh Task, found without the
    search index (#5105); a labelled pull request is not a Task."""
    page: list[dict[str, object]] = [{"number": 5434}, {"number": 5500}]
    page.append({"number": 42, "pull_request": {"url": "https://example/42"}})
    gh = install_fake_gh(tmp_path, issues_page=page)
    result = _run_recordings_close(gh)
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    closes = sorted(c.split()[2] for c in calls if c.startswith("issue close"))
    assert closes == ["5434", "5500"], calls
    assert not any(c.startswith("issue list") for c in calls), calls


def test_recordings_close_step_fails_when_the_lookup_fails(
    tmp_path: Path,
) -> None:
    """A failed lookup fails the step instead of reading as "none open"."""
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": 5434}], api_fails=True
    )
    result = _run_recordings_close(gh)
    assert result.returncode != 0
    assert not any(c.startswith("issue close") for c in gh.calls())
