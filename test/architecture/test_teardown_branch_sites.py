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

"""The P/X/A embargo teardown is built in one received tree only (RSH-03-004).

``ThreatTerminationBranchNode`` is composed by ``add_participant_status_tree``
alone, under its CASE_MANAGER gate
(``test_add_participant_status_bt.py::...::test_teardown_branch_runs_only_at_the_case_manager``).
A replica therefore never runs the teardown, so it never asks the CASE_MANAGER
to end an embargo the CASE_MANAGER declared public: it learns the teardown
from the committed ledger entries alone.  A second production call site
would reopen that question, so it fails here.
"""

import ast

import pytest

from test.architecture import _corpus

_ALLOWED = {"vultron/core/behaviors/status/add_participant_status_tree.py"}


def _call_sites() -> set[str]:
    sites: set[str] = set()
    for path in _corpus.paths_under(_corpus.REPO_ROOT / "vultron"):
        for node in ast.walk(_corpus.tree_of(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ThreatTerminationBranchNode"
            ):
                sites.add(path.relative_to(_corpus.REPO_ROOT).as_posix())
    return sites


@pytest.mark.spec("RSH-03-004")
def test_only_the_participant_status_tree_builds_the_teardown_branch():
    assert _call_sites() == _ALLOWED
