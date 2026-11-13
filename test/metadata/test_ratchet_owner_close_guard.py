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
"""A pull request cannot close an issue a ratchet still names as owner (ARCH-18-012).

The guard is a pull-request job that reads the body's closing references and
the ``# owner:`` markers at the head through ``vultron.metadata.ratchet_markers``
(#6408).  It runs on every body edit as well as on a push, since a closing
reference can be added without a commit.  No such job exists yet, so this is a
strict ``xfail`` until #6408 builds it.
"""

from pathlib import Path

import pytest
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github/workflows"


def _pull_request_types(workflow: dict[object, object]) -> list[str]:
    """The ``pull_request`` activity types a workflow runs on, if any.

    PyYAML reads a bare ``on:`` key as ``True``.
    """
    triggers = workflow.get("on", workflow.get(True)) or {}
    if not isinstance(triggers, dict) or "pull_request" not in triggers:
        return []
    return list((triggers["pull_request"] or {}).get("types", []))


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="ARCH-18-012: no pull-request job checks closed ratchet owners. "
    "Tracked by #6408.",
)
@pytest.mark.spec("ARCH-18-012")
def test_a_pull_request_job_checks_closed_ratchet_owners() -> None:
    guards = [
        path.name
        for path in sorted(_WORKFLOWS.glob("*.yml"))
        if "ratchet_markers" in path.read_text()
        and "edited" in _pull_request_types(yaml.safe_load(path.read_text()))
    ]
    assert guards, "no pull-request workflow checks ratchet owners on edit"
