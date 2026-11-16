"""The committed-data check runs in pre-commit and in CI (#5961, AC-3).

A recorded VINCE response can arrive in any file, so both runs read the whole
tracked tree: CI on every pull request with no ``paths`` filter, since the
``CI gate`` passes a skipped check (PAD-18-031), and pre-commit with no
staged-file list, so its target set is never just the commit's files.
"""

from __future__ import annotations

import re

import pytest
import yaml

from test.ci._workflows import (
    REPO_ROOT,
    WORKFLOWS_DIR,
    load_workflow,
    triggers,
)
from vultron.metadata.vince_data.marker import CLEARED_CASES_PATH, FIXTURE_DIR
from vultron.metadata.vince_data.shape import JSON_SUFFIXES

_COMMAND = "uv run vince-data check"


@pytest.mark.spec("VSD-02-001")
def test_ci_runs_the_check_on_every_pull_request() -> None:
    workflow = load_workflow(WORKFLOWS_DIR / "vince-data-check.yml")
    pull_request = triggers(workflow)["pull_request"]
    assert pull_request.get("branches") == ["main"]
    assert "paths" not in pull_request
    assert "paths-ignore" not in pull_request
    steps = workflow["jobs"]["vince-data"]["steps"]
    assert [s.get("run") for s in steps if "run" in s] == [
        f'{_COMMAND} --history "origin/$BASE_REF"'
    ]
    checkout = steps[0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["fetch-depth"] == 0


def _hook() -> dict[str, object]:
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
    assert isinstance(hook, dict)
    return hook


@pytest.mark.spec("VSD-02-001")
def test_pre_commit_runs_the_check_over_the_tree() -> None:
    hook = _hook()
    assert hook["entry"] == _COMMAND
    assert hook["pass_filenames"] is False


@pytest.mark.parametrize(
    "path",
    [
        *(f"any/dir/file{suffix}" for suffix in JSON_SUFFIXES),
        *(f"FILE{suffix.upper()}" for suffix in JSON_SUFFIXES),
        CLEARED_CASES_PATH,
        f"{FIXTURE_DIR}/999901-active-embargoed.json",
        "vultron/metadata/vince_data/check.py",
        "pyproject.toml",
    ],
)
def test_pre_commit_triggers_on_every_input_of_the_check(path: str) -> None:
    pattern = _hook()["files"]
    assert isinstance(pattern, str)
    assert re.search(pattern, path), path
