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

"""Architecture invariant: ``wait_for_case_participants`` must receive dynamic actor IDs.

``wait_for_case_participants`` changed from count-based to identity-based in
PR #2625.  Its ``expected_actor_ids`` parameter is checked against
``actor_participant_index.keys()``, which stores the actual IDs assigned when
actors were seeded.  Passing hardcoded ``*_ACTOR_ID`` module-level string
constants instead of the live ``actor.id_`` attributes causes the identity
check to diverge from the stored keys whenever the server derives an ID that
differs from the constant — producing a 15-second timeout and CI failure.

The fix is always to use ``{actor_obj.id_, other_obj.id_}`` (attributes of the
objects returned by the seeding helpers), not ``{FINDER_ACTOR_ID, VENDOR_ACTOR_ID}``.

Issue: #2628
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

_SCENARIO_TREES = {
    path: tree
    for path, tree in _corpus.files_mentioning(
        "wait_for_case_participants", under=_SCENARIO_DIR
    )
    if path.name != "__init__.py"
}


def _hardcoded_actor_id_violations(
    tree: ast.AST,
) -> list[tuple[int, str]]:
    """Return ``(line, name)`` for each hardcoded ``*_ACTOR_ID`` constant found
    inside ``expected_actor_ids`` of a ``wait_for_case_participants`` call.

    A violation is a ``Name`` node whose identifier ends with ``_ACTOR_ID``
    (e.g., ``FINDER_ACTOR_ID``, ``C1_ACTOR_ID``).  The correct form is an
    ``Attribute`` access such as ``finder.id_`` or ``c1.id_``.
    """
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        callee = (
            func.attr
            if isinstance(func, ast.Attribute)
            else getattr(func, "id", "")
        )
        if callee != "wait_for_case_participants":
            continue
        for kw in node.keywords:
            if kw.arg != "expected_actor_ids":
                continue
            val = kw.value
            if not isinstance(val, ast.Set):
                continue
            for elt in val.elts:
                if isinstance(elt, ast.Name) and elt.id.endswith("_ACTOR_ID"):
                    violations.append((node.lineno, elt.id))
    return violations


@pytest.mark.parametrize(
    "scenario", sorted(_SCENARIO_TREES), ids=lambda p: p.name
)
def test_wait_for_case_participants_uses_dynamic_actor_ids(scenario: Path):
    """``expected_actor_ids`` must use live actor object ``.id_`` attributes.

    Hardcoded ``*_ACTOR_ID`` string constants diverge from server-derived IDs
    and cause a 15-second timeout in the Demo Integration CI tier (issue #2628).
    Use ``{seeded_actor.id_, other_actor.id_}`` instead.
    """
    violations = _hardcoded_actor_id_violations(_SCENARIO_TREES[scenario])
    assert not violations, (
        f"{scenario.relative_to(_corpus.REPO_ROOT)} passes hardcoded"
        f" constants to wait_for_case_participants expected_actor_ids:"
        f" {violations}. Replace with actor_obj.id_ attributes from the"
        " seeded actor objects (issue #2628)."
    )


def test_the_check_can_actually_fail():
    """Guard: the detector must flag a genuine hardcoded-constant violation."""
    sample = _corpus.parse_inline(
        "FINDER_ACTOR_ID = 'http://finder:7999/api/v2/actors/finder'\n"
        "VENDOR_ACTOR_ID = 'http://vendor:7999/api/v2/actors/vendor'\n"
        "wait_for_case_participants(\n"
        "    vendor_client=vendor_client,\n"
        "    case_id=case.id_,\n"
        "    expected_actor_ids={FINDER_ACTOR_ID, VENDOR_ACTOR_ID},\n"
        ")\n"
    )
    violations = _hardcoded_actor_id_violations(sample)
    assert len(violations) == 2
    names = {name for _, name in violations}
    assert names == {"FINDER_ACTOR_ID", "VENDOR_ACTOR_ID"}
