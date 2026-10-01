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
"""Planned ratchet: case-content recipients come from one shared selection.

CM-10-005 puts the active-participant check (CM-10-004, ADR-0114) in the
shared recipient selection that every case-content send uses, so no send
site can forget it.  A site that builds its recipient list by iterating the
roster's actor IDs (``case.actor_participant_index``) itself bypasses that
check: today such a list is the whole roster, inert participants included.

The scan covers ``vultron/core/``.  Iterating ``.values()`` or ``.items()``
(participant lookups) is not recipient selection and is not flagged.  The
shared selection's own module is the one exemption; if the implementation
moves it, move the exemption with it.  Strict ``xfail`` until #4046 routes
every site through the shared selection; see ``notes/case-joining.md``.
"""

import ast

import pytest

from test.architecture import _corpus

#: Where the shared recipient selection lives (``case_addressees``).
_SHARED_SELECTION = {"vultron/core/models/case.py"}


def _iterates_roster_ids(node: ast.expr) -> bool:
    """True for ``x.actor_participant_index`` or its ``getattr`` spelling."""
    if isinstance(node, ast.Attribute):
        return node.attr == "actor_participant_index"
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == "actor_participant_index"
    )


def _roster_iteration_sites() -> list[str]:
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "actor_participant_index", under=_corpus.REPO_ROOT / "vultron" / "core"
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        if rel in _SHARED_SELECTION:
            continue
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.comprehension, ast.For, ast.AsyncFor)
            ):
                continue
            if _iterates_roster_ids(node.iter):
                sites.append(f"{rel}:{_corpus.node_line(node.iter)}")
    return sites


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-10-005: every case-content send selects recipients through the"
        " shared active-participant selection. Tracked by #4046."
    ),
)
@pytest.mark.spec("CM-10-005")
def test_no_send_site_builds_recipients_from_the_raw_roster() -> None:
    """No code in ``vultron/core/`` lists roster actor IDs outside the shared selection."""
    sites = _roster_iteration_sites()
    assert sites == [], (
        "recipient list built from the raw roster, bypassing the shared"
        " active-participant selection (CM-10-005): " + ", ".join(sites)
    )
