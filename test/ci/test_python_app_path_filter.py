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
"""The unit-test workflow runs on a lockfile-only change.

The demo workflow skips Dependabot PRs on the premise that ``python-app.yml``
still tests them (DEMOCI-02-004), which DEMOCI-02-016 secures. A Dependabot bump inside an existing
version range touches only ``uv.lock``, so without ``uv.lock`` in the path
filter no test runs at all — which is how the py_trees 2.6.0 bump reached
``main`` untested (#3610).
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
