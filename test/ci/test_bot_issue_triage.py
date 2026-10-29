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

from test.ci._fake_gh import UNTRIAGED_ISSUE, FakeGh, install_fake_gh
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
    assert not any("addSubIssue" in c for c in calls), calls
    assert not any(c.startswith("issue view") for c in calls), calls


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
    assert not any("addSubIssue" in c for c in calls), calls


@pytest.mark.parametrize(
    "epic_view",
    [("ID", "OPEN", "Task"), ("ID", "CLOSED", "Epic"), ("ID", "OPEN", "")],
    ids=["not-an-epic", "closed-epic", "untyped"],
)
def test_helper_refuses_a_parent_that_is_not_an_open_epic(
    tmp_path: Path, epic_view: tuple[str, str, str]
) -> None:
    """A variable naming anything but an open Epic fails, wiring nothing."""
    gh = install_fake_gh(tmp_path, epic_view=epic_view)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 1
    assert "not an open Epic" in result.stderr
    assert not any("addSubIssue" in c for c in gh.calls())


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
    step = _notify_step()
    env_map = step["env"]
    assert env_map["CI_FAILURE_EPIC"] == "${{ vars.CI_FAILURE_EPIC }}", (
        "The parent Epic must come from the CI_FAILURE_EPIC repository "
        "variable, not a hard-coded number (#5435)."
    )
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": n} for n in open_issues]
    )
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "MODE": "notify",
        "WORKFLOW_LABEL": "ci:workflow-example",
        "WORKFLOW_NAME": "Example",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REF": "refs/heads/main",
        "CI_FAILURE_EPIC": str(EPIC),
        "GITHUB_ACTION_PATH": str(NOTIFY_ACTION.parent),
    }
    subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", str(step["run"])],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    calls = gh.calls()
    assert (
        f"issue edit {number} --repo OWNER/REPO --add-label {THEME}" in calls
    )
    labels = {"ci:main-failure", "ci:workflow-example"}
    assert _theme_fit_findings(gh, labels, THEME, EPIC) == []


@pytest.mark.spec("PAD-01-007", "PAD-02-014", "PAD-02-018")
@pytest.mark.parametrize(
    ("existing", "number"),
    [("", "999"), ("5434", "5434")],
    ids=["create-arm", "comment-arm"],
)
def test_recordings_workflow_triages_the_task_it_files(
    tmp_path: Path, existing: str, number: str
) -> None:
    """AC-2: the refresh Task gets theme, line and parent, on both arms."""
    step = _recordings_step("File or update the refresh Task")
    env_map = step["env"]
    assert (
        env_map["DEMO_RECORDINGS_EPIC"] == "${{ vars.DEMO_RECORDINGS_EPIC }}"
    ), (
        "The parent Epic must come from the DEMO_RECORDINGS_EPIC repository "
        "variable, not a hard-coded number (#5435)."
    )
    # The step's `gh issue list` finds the open Task, if any.
    gh = install_fake_gh(tmp_path, issue_list=existing)
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
    labels = {"demo-recordings-stale"}
    assert _theme_fit_findings(gh, labels, theme, 4747) == []
