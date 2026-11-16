"""The committed-data check runs in pre-commit and in CI (#5961, AC-3).

A recorded VINCE response can arrive in any file, so both runs read the whole
tracked tree: CI on every pull request with no ``paths`` filter, since the
``CI gate`` passes a skipped check (PAD-18-031), and pre-commit with no
staged-file list, so its target set is never just the commit's files.
"""

from __future__ import annotations

import pytest
import yaml

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)

_COMMAND = "uv run vince-data check"


@pytest.mark.spec("VSD-02-001")
def test_ci_runs_the_check_on_every_pull_request() -> None:
    workflow = load_workflow(WORKFLOWS_DIR / "vince-data-check.yml")
    pull_request = triggers(workflow)["pull_request"]
    assert pull_request.get("branches") == ["main"]
    assert "paths" not in pull_request
    assert "paths-ignore" not in pull_request
    steps = workflow["jobs"]["vince-data"]["steps"]
    assert [s.get("run") for s in steps if "run" in s] == [_COMMAND]


@pytest.mark.spec("VSD-02-001")
def test_pre_commit_runs_the_check_over_the_tree() -> None:
    config = yaml.safe_load(
        (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = [
        hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook["id"] == "vince-data-check"
    ]
    [hook] = hooks
    assert hook["entry"] == _COMMAND
    assert hook["pass_filenames"] is False
