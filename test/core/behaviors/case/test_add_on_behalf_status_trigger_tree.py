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

"""Structural tests for add_on_behalf_status_trigger_bt (CSB-15-004 wiring).

Verifies that CheckSomeVendorAtVFNode is included in the tree when d_state is
non-None and excluded when d_state is None.
"""

from vultron.core.behaviors.case.add_on_behalf_status_trigger_tree import (
    add_on_behalf_status_trigger_bt,
)
from vultron.core.behaviors.case.nodes.vfd_role_guards import (
    CheckSomeVendorAtVFNode,
)
from vultron.core.states.cs import CS_d, CS_vf
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/on-behalf-test-001"
ASSERTING_ACTOR_ID = "https://example.org/actors/case-manager"
TARGET_ACTOR_ID = "https://example.org/actors/deployer"


def _make_tree(
    d_state: CS_d | None = None,
    vf_state: CS_vf | None = None,
) -> object:
    return add_on_behalf_status_trigger_bt(
        case_id=CASE_ID,
        asserting_actor_id=ASSERTING_ACTOR_ID,
        target_actor_id=TARGET_ACTOR_ID,
        required_roles=[CVDRole.DEPLOYER],
        vf_state=vf_state,
        d_state=d_state,
        result_out={},
        activity_builder=lambda _: [],
    )


def _child_type_names(tree: object) -> list[str]:
    return [type(c).__name__ for c in tree.children]


def test_causal_gate_present_when_d_state_set() -> None:
    """CheckSomeVendorAtVFNode MUST be in the tree when d_state is non-None (CSB-15-004).

    The on-behalf path applies the same causal precondition as the direct path:
    a CASE_MANAGER asserting d→D on behalf of a DEPLOYER must also satisfy the
    "some VENDOR at VF" gate.
    """
    tree = _make_tree(d_state=CS_d.D)
    assert CheckSomeVendorAtVFNode.__name__ in _child_type_names(tree)


def test_causal_gate_absent_when_d_state_none() -> None:
    """CheckSomeVendorAtVFNode MUST NOT be in the tree when d_state is None.

    When no d→D transition is being asserted, the causal gate is irrelevant
    and must not be inserted — it would falsely block non-d transitions.
    """
    tree = _make_tree(d_state=None, vf_state=CS_vf.Vf)
    assert CheckSomeVendorAtVFNode.__name__ not in _child_type_names(tree)
