#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""``ui.yml`` fires on package file changes so Dependabot PRs run the checks.

A Dependabot version-update PR for the ui/ npm dependencies changes
ui/package.json and ui/package-lock.json, and a security update for a
transitive dependency changes only the lockfile. The ui workflow must fire on
each of those paths alone, or a Dependabot PR merges without running the UI
lint, test, and build checks it exists to gate (#6172).

The filter is read as GitHub reads it (globs, ``!`` exclusions, last match
wins) through the CI mirror's trigger model, so any filter that still covers
both files passes and one that stops covering either fails.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import load_workflow, triggers
from vultron.metadata.planning.ci_mirror._workflows import (
    matches_filter,
    pull_request_trigger,
)

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ui.yml"
)

PACKAGE_FILES = ("ui/package.json", "ui/package-lock.json")


def _pull_request_fires(wf_data: Mapping[Any, Any], path: str) -> bool:
    trigger = pull_request_trigger(wf_data)
    return trigger is not None and trigger.runs_for("main", [path])


def _push_fires(wf_data: Mapping[Any, Any], path: str) -> bool:
    push = triggers(dict(wf_data)).get("push")
    if push is None:
        return False
    if not isinstance(push, dict) or "paths" not in push:
        return True
    return matches_filter(path, [str(p) for p in push["paths"]])


@pytest.mark.parametrize("path", PACKAGE_FILES)
def test_ui_workflow_runs_on_a_dependabot_pull_request(path: str) -> None:
    """A PR to main changing only *path* runs the UI checks (#6172 AC-2)."""
    assert _pull_request_fires(load_workflow(WORKFLOW), path), (
        f"ui.yml's pull_request filter does not match {path}, so a Dependabot "
        "npm PR that changes only it would merge without the UI checks."
    )


@pytest.mark.parametrize("path", PACKAGE_FILES)
def test_ui_workflow_runs_on_a_dependabot_merge(path: str) -> None:
    """The merged Dependabot change re-runs the UI checks on main."""
    assert _push_fires(load_workflow(WORKFLOW), path), (
        f"ui.yml's push filter does not match {path}."
    )


@pytest.mark.parametrize(
    "paths",
    [
        ["ui/src/**"],
        ["ui/package.json"],
        ["ui/**", "!ui/package*.json"],
    ],
)
def test_a_filter_missing_a_package_file_is_caught(paths: list[str]) -> None:
    """The check fails for a filter that misses either package file."""
    wf = {"on": {"pull_request": {"branches": ["main"], "paths": paths}}}
    assert not all(_pull_request_fires(wf, path) for path in PACKAGE_FILES)


@pytest.mark.parametrize("paths", [["ui/**"], ["ui/package*.json"], ["ui/*"]])
def test_a_filter_covering_both_package_files_passes(paths: list[str]) -> None:
    """Any filter shape that covers both files satisfies the check."""
    wf = {"on": {"pull_request": {"branches": ["main"], "paths": paths}}}
    assert all(_pull_request_fires(wf, path) for path in PACKAGE_FILES)
