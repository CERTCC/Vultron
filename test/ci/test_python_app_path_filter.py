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
"""The unit-test workflow runs on a change to an input no Python file names.

Two kinds of pull request change only a non-Python file that a test reads, so
each needs its own path-filter entry or no test runs at all:

- A Dependabot bump inside an existing version range touches only ``uv.lock``.
  The demo workflow skips Dependabot PRs on the premise that
  ``python-app.yml`` still tests them (DEMOCI-02-004), which DEMOCI-02-016
  secures; without ``uv.lock`` in the filter the py_trees 2.6.0 bump reached
  ``main`` untested (#3610).
- A hand edit or a half-finished regeneration of a committed vocab example
  touches only ``docs/reference/examples/``, which
  ``test/architecture/test_vocab_examples_current.py`` compares byte for byte
  against a fresh generation (#5776). A gate whose input is in no trigger list
  is installed but unreachable on the pull-request shape it exists to police
  (#4506).
"""

from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import load_workflow, triggers

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "python-app.yml"
)


def _triggers() -> dict[str, Any]:
    return triggers(load_workflow(WORKFLOW))


@pytest.mark.spec("DEMOCI-02-016")
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_lockfile_change(event: str) -> None:
    assert "uv.lock" in _triggers()[event]["paths"]


@pytest.mark.spec("DEMOCI-02-021")
@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_python_app_workflow_runs_on_a_committed_example_change(
    event: str,
) -> None:
    assert "docs/reference/examples/**" in _triggers()[event]["paths"]
