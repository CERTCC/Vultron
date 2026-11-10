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

A Dependabot version-update PR for the ui/ npm dependencies changes only
ui/package.json and ui/package-lock.json. The ui workflow must fire on those
paths, or a Dependabot PR merges without running the UI lint, test, and build
checks it exists to gate (#6172).

The workflow already carries ``ui/**`` as a path filter, which covers both
files. This test pins that coverage so a future filter narrowing does not
silently exclude them.
"""

from pathlib import Path
from typing import Any

import pytest

from test.ci._workflows import load_workflow, triggers

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ui.yml"
)


def _triggers() -> dict[str, Any]:
    return triggers(load_workflow(WORKFLOW))


@pytest.mark.parametrize("event", ["push", "pull_request"])
def test_ui_workflow_runs_on_package_json_change(event: str) -> None:
    """A change to ui/package.json triggers the UI workflow (#6172)."""
    paths = _triggers()[event]["paths"]
    # The filter is ui/**, which covers ui/package.json and ui/package-lock.json.
    # Assert that the broad filter is present. A future narrowing to specific
    # files must keep these two.
    assert any(
        pattern in ("ui/**", "ui/package.json", "ui/package-lock.json")
        for pattern in paths
    ), (
        f"The {event} paths must include ui/package.json or ui/package-lock.json "
        "or the broad ui/** filter, so a Dependabot npm PR runs the UI checks:\n"
        + "\n".join(f"  {pattern}" for pattern in paths)
    )
