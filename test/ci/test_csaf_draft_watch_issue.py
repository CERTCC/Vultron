"""The issue step of the CSAF Draft Watch workflow (CSAF-05-005, CSAF-05-006).

``.github/scripts/csaf-draft-watch-issue.sh`` opens one Task when the
comparison script reports a change, and writes nothing while a Task with its
marker label is open. It runs here against the fake ``gh`` of
``test/ci/_fake_gh.py``, and the workflow is read to check that it checks out
the upstream paths the comparison script reads. The compare step runs under
``bash -e``, as on GitHub, to check that it hands the change status on.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._fake_gh import UNTHEMED_ISSUE, FakeGh, install_fake_gh
from test.ci._workflows import REPO_ROOT, WORKFLOWS_DIR
from vultron.metadata.csaf.draft_watch import (
    EXIT_CHANGED,
    PROFILES_FILE,
    TESTCASES_FILE,
    WATCHED_SCHEMA_DIRS,
)
from vultron.metadata.planning.themes import load_theme_catalog

SCRIPT = REPO_ROOT / ".github" / "scripts" / "csaf-draft-watch-issue.sh"
WORKFLOW = WORKFLOWS_DIR / "csaf-draft-watch.yml"
LABEL = "csaf-draft-watch"
THEME = "theme:standards-engagement"
#: The open Task a complete earlier run left: themed, with its Theme: line.
COMPLETE_ISSUE: dict[str, object] = {
    "body": f"Theme: {THEME} — maintainers learn.\n\nThe draft moved.",
    "labels": {"nodes": [{"name": LABEL}, {"name": THEME}]},
}
#: The ``gh`` calls that write: each would add, edit or comment on an issue.
WRITES = (
    "issue create",
    "issue edit",
    "issue comment",
    "issue close",
    "label create",
    "updateIssue",
)


def _run(gh: FakeGh, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    body = tmp_path / "report.md"
    body.write_text("The draft moved.\n", encoding="utf-8")
    return subprocess.run(
        ["bash", str(SCRIPT), "OWNER/REPO", str(body)],
        check=False,
        env=gh.env,
        capture_output=True,
        text=True,
    )


def _writes(gh: FakeGh) -> list[str]:
    return [
        call for call in gh.calls() if any(write in call for write in WRITES)
    ]


@pytest.mark.spec("CSAF-05-006")
def test_an_open_issue_with_the_marker_makes_the_step_write_nothing(
    tmp_path: Path,
) -> None:
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": 42}], issue=COMPLETE_ISSUE
    )

    result = _run(gh, tmp_path)

    assert result.returncode == 0, result.stderr
    assert "#42 is open" in result.stdout
    assert _writes(gh) == []
    assert any(f"labels={LABEL}&state=open" in c for c in gh.calls())


@pytest.mark.spec("CSAF-05-005")
def test_with_no_open_issue_the_step_files_one_typed_themed_task(
    tmp_path: Path,
) -> None:
    gh = install_fake_gh(tmp_path, issues_page=[])

    result = _run(gh, tmp_path)

    assert result.returncode == 0, result.stderr
    creates = [c for c in gh.calls() if c.startswith("issue create")]
    assert len(creates) == 1
    assert f"--label {LABEL}" in creates[0]
    calls = gh.calls()
    assert any(c.startswith("issue view 999") for c in calls), calls
    assert any(c.endswith(f"--add-label {THEME}") for c in calls), calls
    assert not any("sub_issue" in c or "addSubIssue" in c for c in calls)


@pytest.mark.parametrize(
    ("issue_type", "issue"),
    [("", COMPLETE_ISSUE), ("Task", UNTHEMED_ISSUE)],
    ids=["untyped", "unthemed"],
)
def test_the_open_issue_an_earlier_run_left_incomplete_is_repaired(
    tmp_path: Path, issue_type: str, issue: dict[str, object]
) -> None:
    gh = install_fake_gh(
        tmp_path,
        issues_page=[{"number": 42}],
        issue=issue,
        issue_type=issue_type,
    )

    result = _run(gh, tmp_path)

    assert result.returncode == 0, result.stderr
    writes = _writes(gh)
    assert writes, "the incomplete issue was not repaired"
    assert not any(
        w.startswith(("issue create", "issue comment", "label create"))
        for w in writes
    ), writes
    assert all(
        "updateIssue" in w or w.startswith("issue edit 42 ") for w in writes
    ), writes


def test_the_oldest_of_several_open_issues_is_the_one_kept(
    tmp_path: Path,
) -> None:
    gh = install_fake_gh(
        tmp_path,
        issues_page=[{"number": 42}, {"number": 50}],
        issue=COMPLETE_ISSUE,
    )

    result = _run(gh, tmp_path)

    assert result.returncode == 0, result.stderr
    assert "#42 is open" in result.stdout
    assert any(c.startswith("issue view 42 ") for c in gh.calls())
    assert not any(" 50 " in f"{c} " for c in gh.calls())


def test_the_script_files_under_an_active_catalog_theme() -> None:
    found = re.search(r"^theme=(\S+)$", SCRIPT.read_text(), re.MULTILINE)

    assert found is not None
    assert found.group(1) == THEME
    assert THEME in {t.label for t in load_theme_catalog().active()}


def test_a_pull_request_with_the_label_is_not_the_open_issue(
    tmp_path: Path,
) -> None:
    gh = install_fake_gh(
        tmp_path, issues_page=[{"number": 7, "pull_request": {"url": "x"}}]
    )

    result = _run(gh, tmp_path)

    assert result.returncode == 0, result.stderr
    assert any(c.startswith("issue create") for c in gh.calls())


def test_a_failed_lookup_fails_the_step_and_files_nothing(
    tmp_path: Path,
) -> None:
    gh = install_fake_gh(tmp_path, api_fails=True)

    result = _run(gh, tmp_path)

    assert result.returncode != 0
    assert _writes(gh) == []


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps: list[dict[str, Any]] = workflow["jobs"]["watch"]["steps"]
    return steps


def _sparse_paths(step_name: str) -> list[str]:
    step = next(s for s in _steps() if s.get("name") == step_name)
    return str(step["with"]["sparse-checkout"]).split()


def test_the_workflow_checks_out_what_the_comparison_reads() -> None:
    head = _sparse_paths("Check out the upstream head")
    pinned = _sparse_paths("Check out the pinned revision")

    for watched in WATCHED_SCHEMA_DIRS:
        assert f"{watched}**" in head
    for path in (str(PROFILES_FILE), str(TESTCASES_FILE)):
        assert path in head and path in pinned


def test_the_workflow_opens_the_issue_only_on_a_reported_change() -> None:
    step = next(
        s for s in _steps() if "csaf-draft-watch-issue.sh" in s.get("run", "")
    )

    assert step["if"] == f"steps.compare.outputs.status == '{EXIT_CHANGED}'"


def _run_compare_step(
    tmp_path: Path, uv_status: int
) -> tuple[subprocess.CompletedProcess[str], str]:
    """Run the compare step's script as GitHub does, under ``bash -e``.

    A stub ``uv`` exits *uv_status*, and a stub ``git`` prints a commit, so
    the step's own status handling is what the result shows.
    """
    step = next(s for s in _steps() if s.get("id") == "compare")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (
        ("uv", f"#!/usr/bin/env bash\nexit {uv_status}\n"),
        ("git", "#!/usr/bin/env bash\necho 0123abc\n"),
    ):
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    output = tmp_path / "output"
    output.touch()
    result = subprocess.run(
        ["bash", "-e", "-c", str(step["run"])],
        check=False,
        cwd=tmp_path,
        env={
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
    )
    return result, output.read_text(encoding="utf-8")


@pytest.mark.spec("CSAF-05-005")
@pytest.mark.parametrize("uv_status", [0, EXIT_CHANGED])
def test_the_compare_step_passes_the_status_to_the_issue_step(
    tmp_path: Path, uv_status: int
) -> None:
    result, output = _run_compare_step(tmp_path, uv_status)

    assert result.returncode == 0, result.stderr
    assert output.splitlines() == [f"status={uv_status}"]


def test_a_failed_comparison_fails_the_compare_step(tmp_path: Path) -> None:
    result, output = _run_compare_step(tmp_path, 1)

    assert result.returncode == 1
    assert output.splitlines() == ["status=1"]
