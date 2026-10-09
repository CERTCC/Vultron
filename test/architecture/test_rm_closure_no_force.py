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
"""Ratchet: no RM closure overrides the transition table (RMB-14-005).

ADR-0114 adds ``R → C`` to the RM table and routes a ``Leave`` from *Valid*
through *Deferred* (``V → D → C``), so every closure is an ordinary
transition and the ``force_rm_state`` override has no closure use left
(#4044).  See ``notes/case-joining.md``.  The quarantine of the remaining (bootstrap)
overrides is pinned separately by ``test_participant_status_validation.py``.
"""

import ast

import pytest

from test.architecture import _corpus


def _names_rm_closed(node: ast.expr) -> bool:
    """True when *node* is ``RM.CLOSED`` (or any ``<alias>.CLOSED``)."""
    return isinstance(node, ast.Attribute) and node.attr == "CLOSED"


def _is_disabled(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def _forced_closure_sites() -> list[str]:
    """Every call that writes ``rm_state=…CLOSED`` with ``force_rm_state`` on.

    Any ``force_rm_state`` value other than a literal ``False`` counts, so a
    flag variable cannot hide an override.
    """
    sites: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "force_rm_state", under=_corpus.REPO_ROOT / "vultron"
    ):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            forced = kwargs.get("force_rm_state")
            rm_state = kwargs.get("rm_state")
            if forced is None or rm_state is None or _is_disabled(forced):
                continue
            if _names_rm_closed(rm_state):
                rel = path.relative_to(_corpus.REPO_ROOT)
                sites.append(f"{rel}:{_corpus.node_line(node)}")
    return sites


@pytest.mark.spec("RMB-14-005")
def test_no_rm_closure_forces_past_the_transition_table() -> None:
    """No write of ``RM.CLOSED`` in ``vultron/`` bypasses the RM table."""
    sites = _forced_closure_sites()
    assert sites == [], (
        "RM closure written with force_rm_state (RMB-14-005): "
        + ", ".join(sites)
    )
