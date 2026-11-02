"""Bot-filed issues get a theme label and a ``Theme:`` line, and no parent.

Two workflows file issues: the ``notify-failure`` composite action (a
``ci:main-failure`` Bug) and the Demo Recordings workflow (a refresh Task).
Each gives its issue one ``theme:`` label (PAD-02-014) and a ``Theme:`` line
(PAD-02-018) through ``.github/scripts/ensure-issue-triage.sh``, and sets no
parent: the issue starts untriaged (PAD-01-007), and ``theme-fit`` lists it
for routing instead of reporting a finding (PAD-02-026 to PAD-02-029,
#5450).

The helper is run here against a fake ``gh`` (``test/ci/_fake_gh.py``), and the
issue each filer leaves is checked with the ``theme-fit`` analysis itself, so
a theme retired from the catalog fails here, not on the board.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._fake_gh import UNTHEMED_ISSUE, FakeGh, install_fake_gh
from vultron.metadata.planning.theme_fit.analyze import analyze
from vultron.metadata.planning.theme_fit.model import OpenIssue
from vultron.metadata.planning.themes import load_theme_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
GITHUB_DIR = REPO_ROOT / ".github"
SCRIPTS_DIR = GITHUB_DIR / "scripts"
TRIAGE_HELPER = SCRIPTS_DIR / "ensure-issue-triage.sh"
NOTIFY_ACTION = GITHUB_DIR / "actions" / "notify-failure" / "action.yml"
RECORDINGS_WORKFLOW = GITHUB_DIR / "workflows" / "demo-recordings.yml"

THEME = "theme:test-and-ci"
OUTCOME = "gets the Example workflow passing on main again."
CALL = ("OWNER/REPO", "999", THEME, OUTCOME)
# The repository variables #5435 used to name each filer's Epic (#5450).
RETIRED_EPIC_VARIABLES = ("CI_FAILURE_EPIC", "DEMO_RECORDINGS_EPIC")


def _run_helper(gh: FakeGh, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(TRIAGE_HELPER), *args],
        check=False,
        env=gh.env,
        capture_output=True,
        text=True,
    )


def _assert_no_parent_set(gh: FakeGh) -> None:
    """No ``gh`` call the fake saw could give the issue a parent."""
    log = gh.log.read_text()
    for marker in ("addSubIssue", "parent", "--add-sub-issue", "sub_issues"):
        assert marker not in log, f"{marker!r} in gh calls:\n{log}"


def _assert_untriaged_and_clean(gh: FakeGh, labels: set[str]) -> None:
    """``theme-fit`` lists the issue as the fake left it as untriaged only.

    Its labels are *labels* plus any the helper added, its body the one the
    helper wrote, and it has no parent. AC-1 and AC-3 (#5450): exactly one
    theme, a ``Theme:`` line, no finding, and listed for routing.
    """
    added = {
        c.split("--add-label ", 1)[1]
        for c in gh.calls()
        if c.startswith("issue edit") and "--add-label" in c
    }
    filed = OpenIssue(
        number=999,
        title="Filed by a workflow",
        issue_type="Bug",
        labels=frozenset(labels | added),
        body=gh.written_body() or "",
    )
    assert len(filed.themes) == 1, filed.themes
    report = analyze([filed], load_theme_catalog())
    findings = [f"{f.kind.value}: {f.detail}" for f in report.findings]
    assert findings == []
    assert [u.number for u in report.untriaged] == [999]


# ---------------------------------------------------------------------------
# The helper
# ---------------------------------------------------------------------------


@pytest.mark.spec("PAD-02-026", "PAD-02-027")
def test_helper_themes_an_unthemed_issue_and_sets_no_parent(
    tmp_path: Path,
) -> None:
    """An issue with neither gets both, and no parent."""
    gh = install_fake_gh(tmp_path)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    assert (
        f"issue edit 999 --repo OWNER/REPO --add-label {THEME}" in gh.calls()
    )
    body = gh.written_body()
    assert body is not None
    assert body.splitlines()[0] == f"Theme: {THEME} — {OUTCOME}"
    assert "Original body." in body, "The filed body must be kept."
    _assert_no_parent_set(gh)
    _assert_untriaged_and_clean(gh, {"ci:main-failure"})


@pytest.mark.spec("PAD-02-029")
def test_helper_leaves_an_issue_a_person_re_themed_alone(
    tmp_path: Path,
) -> None:
    """A person's theme wins: the helper changes nothing."""
    issue = UNTHEMED_ISSUE | {
        "labels": {"nodes": [{"name": "theme:dev-workflow"}]},
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    assert not any(c.startswith("issue edit") for c in gh.calls())
    _assert_no_parent_set(gh)


def test_helper_keeps_an_existing_theme_line(tmp_path: Path) -> None:
    """A repair run adds the label without writing the line a second time."""
    line = f"Theme: {THEME} — {OUTCOME}"
    issue = UNTHEMED_ISSUE | {"body": f"{line}\n\nOriginal body."}
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
    issue = UNTHEMED_ISSUE | {
        "labels": {"nodes": [{"name": "ci:main-failure"}, {"name": THEME}]},
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    body = gh.written_body()
    assert body is not None and body.startswith(f"Theme: {THEME} — ")
    assert not any("--add-label" in c for c in gh.calls())
    _assert_untriaged_and_clean(gh, {THEME})


def test_helper_does_not_take_a_longer_label_for_its_theme(
    tmp_path: Path,
) -> None:
    """A ``Theme:`` line for a label that merely starts with the theme is
    not the theme's line, so the line is still written."""
    issue = UNTHEMED_ISSUE | {
        "body": f"Theme: {THEME}-extra — something else.\n\nOriginal body.",
    }
    gh = install_fake_gh(tmp_path, issue=issue)
    result = _run_helper(gh, *CALL)
    assert result.returncode == 0, result.stderr
    body = gh.written_body()
    assert body is not None
    assert body.splitlines()[0] == f"Theme: {THEME} — {OUTCOME}"


@pytest.mark.parametrize(
    "args",
    [
        ("OWNER/REPO", "999", "test-and-ci", OUTCOME),
        ("OWNER/REPO", "999", THEME, ""),
        ("OWNER/REPO", "999", THEME),
        # The old six-argument call, with an Epic and its variable (#5450).
        (*CALL, "3791", "CI_FAILURE_EPIC"),
    ],
    ids=["not-a-theme-label", "empty-outcome", "too-few", "old-epic-args"],
)
def test_helper_rejects_a_bad_call(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    """A caller bug fails before any ``gh`` call."""
    gh = install_fake_gh(tmp_path)
    result = _run_helper(gh, *args)
    assert result.returncode == 2
    assert gh.calls() == []


def _github_files() -> list[tuple[str, str]]:
    """Every file under ``.github/``, as (repo-relative path, text)."""
    return [
        (str(path.relative_to(REPO_ROOT)), path.read_text(errors="replace"))
        for path in sorted(GITHUB_DIR.rglob("*"))
        if path.is_file()
    ]


_EPIC_VARIABLE = re.compile(r"""vars(?:\.\w*|\[\s*['"]\w*)EPIC\w*""", re.I)
# ``addSubIssue`` is the GraphQL write; the REST write is a POST to
# ``.../sub_issues`` whose body needs ``sub_issue_id``. A read of
# ``.../sub_issues`` carries no ``sub_issue_id`` and is not a hit.
_PARENT_WRITES = ("addSubIssue", "sub_issue_id")


def _epic_or_parent_hits(text: str) -> list[str]:
    """Each retired variable, ``vars.*EPIC*`` read, or parent write in *text*."""
    return [
        *(n for n in RETIRED_EPIC_VARIABLES if n in text),
        *_EPIC_VARIABLE.findall(text),
        *(m for m in _PARENT_WRITES if m in text),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "epic: ${{ vars.CI_FAILURE_EPIC }}",
        "epic: ${{ vars.SOME_NEW_EPIC }}",
        "epic: ${{ vars['OTHER_EPIC'] }}",
        "mutation { addSubIssue(input: $i) { subIssue { number } } }",
        "gh api -X POST repos/o/r/issues/1/sub_issues -F sub_issue_id=7",
    ],
)
def test_the_scan_catches_each_way_to_name_an_epic(text: str) -> None:
    """A positive control: the scan below would fail on each form."""
    assert _epic_or_parent_hits(text)


def test_the_scan_passes_a_read_of_sub_issues() -> None:
    """The sweeper and planning scripts read sub-issues; that is no write."""
    text = 'gh api "repos/o/r/issues/1/sub_issues?per_page=100"'
    assert _epic_or_parent_hits(text) == []


@pytest.mark.spec("PAD-02-027")
def test_nothing_under_github_names_an_epic_or_sets_a_parent() -> None:
    """AC-2 (#5450): no filer is wired to a fixed Epic any more.

    A fixed Epic number needs upkeep each time that Epic closes, is
    rethemed or split, or fills up, so a workflow-filed issue gets no
    parent: nothing under ``.github/`` reads a retired variable or any
    ``vars.*EPIC*`` variable, or sets a parent through ``addSubIssue`` or
    the REST ``sub_issues`` endpoint.
    """
    breaches = [
        f"{path}: {hit}"
        for path, text in _github_files()
        for hit in _epic_or_parent_hits(text)
    ]
    assert breaches == []


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


def _run_notify(gh: FakeGh) -> subprocess.CompletedProcess[str]:
    """Run the notify arm's real script against the fake ``gh``."""
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "MODE": "notify",
        "WORKFLOW_LABEL": "ci:workflow-example",
        "WORKFLOW_NAME": "Example",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REF": "refs/heads/main",
        "GITHUB_ACTION_PATH": str(NOTIFY_ACTION.parent),
    }
    return subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", str(_notify_step()["run"])],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_notify_failure_takes_no_epic_input() -> None:
    """The action has no ``epic`` input and reads no ``vars`` (#5450)."""
    action: dict[str, Any] = yaml.safe_load(NOTIFY_ACTION.read_text())
    assert "epic" not in action["inputs"]
    assert "vars." not in NOTIFY_ACTION.read_text()


def test_notify_failure_closes_duplicates_and_themes_the_oldest(
    tmp_path: Path,
) -> None:
    """Duplicate trackers are closed (CISEC-05-011) and the one that
    remains is themed."""
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": 5087}, {"number": 5105}]
    )
    result = _run_notify(gh)
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    assert any(c.startswith("issue close 5105") for c in calls), calls
    assert f"issue edit 5087 --repo OWNER/REPO --add-label {THEME}" in calls
    assert not any(c.startswith("issue edit 5105") for c in calls), calls
    _assert_no_parent_set(gh)


@pytest.mark.spec("PAD-02-026", "PAD-02-027", "PAD-02-028")
@pytest.mark.parametrize(
    ("open_issues", "number"),
    [([], "999"), ([5087], "5087")],
    ids=["create-arm", "comment-arm"],
)
def test_notify_failure_triages_the_issue_it_files(
    tmp_path: Path, open_issues: list[int], number: str
) -> None:
    """AC-1: a ``ci:main-failure`` issue gets a theme and line, no parent.

    The comment arm repairs an open issue an earlier run filed bare.
    """
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": n} for n in open_issues]
    )
    result = _run_notify(gh)
    assert result.returncode == 0, result.stderr
    calls = gh.calls()
    assert (
        f"issue edit {number} --repo OWNER/REPO --add-label {THEME}" in calls
    )
    _assert_no_parent_set(gh)
    _assert_untriaged_and_clean(gh, {"ci:main-failure", "ci:workflow-example"})


@pytest.mark.spec("PAD-02-026", "PAD-02-027", "PAD-02-028")
@pytest.mark.parametrize(
    ("existing", "number"),
    [([], "999"), ([5434], "5434"), ([5434, 5500], "5434")],
    ids=["create-arm", "comment-arm", "comment-arm-oldest"],
)
def test_recordings_workflow_triages_the_task_it_files(
    tmp_path: Path, existing: list[int], number: str
) -> None:
    """AC-1: the refresh Task gets a theme and line, no parent, on both arms.

    With more than one open, only the oldest is updated.
    """
    step = _recordings_step("File or update the refresh Task")
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": n} for n in existing]
    )
    work = tmp_path / "work"
    (work / ".github").mkdir(parents=True)
    (work / ".github" / "scripts").symlink_to(SCRIPTS_DIR)
    (work / "changed.txt").write_text("demo-a\n")
    env = gh.env | {
        "REPO": "OWNER/REPO",
        "RUN_URL": "https://github.com/OWNER/REPO/actions/runs/1",
        "REFRESH_LABEL": "demo-recordings-stale",
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
    _assert_no_parent_set(gh)
    _assert_untriaged_and_clean(gh, {"demo-recordings-stale"})


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
