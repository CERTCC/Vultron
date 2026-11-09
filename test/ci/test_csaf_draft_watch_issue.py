"""The issue step of the CSAF Draft Watch workflow (CSAF-05-005, CSAF-05-006).

``.github/scripts/csaf-draft-watch-issue.sh`` opens one Task when the
comparison script reports a change, and writes nothing while a Task with its
marker label is open. It runs here against the fake ``gh`` of
``test/ci/_fake_gh.py``, and the workflow is read to check that it checks out
the upstream paths the comparison script reads.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from test.ci._fake_gh import FakeGh, install_fake_gh
from test.ci._workflows import REPO_ROOT, WORKFLOWS_DIR
from vultron.metadata.csaf.draft_watch import (
    EXIT_CHANGED,
    PROFILES_FILE,
    TESTCASES_FILE,
    WATCHED_SCHEMA_DIRS,
)

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
