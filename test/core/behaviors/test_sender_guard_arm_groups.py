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

"""A sender-guard arm that groups an in-case path with the no-case path.

When two declared paths' sides name the same kinds, the guard judges them in
one arm (HP-01-036).  The usual group is the two in-case paths; this module
pins the names and refusal wording of a group that is not, the CASE_MANAGER
path with the no-case path.
"""

import pytest

from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import (
    NoSenderAdmittedNode,
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import compose_sender_guard
from vultron.core.behaviors.sender_guard.compose import (
    _arm_name,
    _receiver_of,
)

CM = ReceivedPath.CASE_MANAGER
PR = ReceivedPath.PARTICIPANT_REPLICA
NC = ReceivedPath.NO_CASE


@pytest.mark.spec("HP-01-036")
def test_a_manager_and_no_case_group_names_both_receivers() -> None:
    assert _receiver_of(frozenset({CM, NC})) == (
        "the CASE_MANAGER or a receiver with no case to act on for this"
        " activity (the tree names no case this store holds)"
    )
    assert _arm_name(frozenset({CM, NC})) == "AtCaseManagerOrOutsideCase"


@pytest.mark.spec("HP-01-036")
def test_the_composed_guard_judges_the_group_in_one_arm() -> None:
    """The CASE_MANAGER and no-case sides name one kind, so they share an
    arm; the participant side admits no sender, in its own arm."""
    owner = frozenset({SenderEntitlementKind.CASE_OWNER})
    rule = SenderRule(at_case_manager=owner, outside_case=owner)
    stage = ReceivedPathNode(
        declared=frozenset({CM, PR, NC}), label="GroupedArmsBT"
    )
    guard = compose_sender_guard(
        rule, SenderCheckContext(sender_id="https://example.org/s"), stage
    )
    assert guard is not None
    arms = {arm.name: arm for arm in guard.children}
    assert set(arms) == {"AtCaseManagerOrOutsideCase", "AtParticipant"}
    assert any(
        isinstance(n, NoSenderAdmittedNode)
        for n in arms["AtParticipant"].iterate()
    )
