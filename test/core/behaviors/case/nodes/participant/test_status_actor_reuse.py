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

"""Regression: a pre-built CreateParticipantStatusNode is actor-scoped per tick.

Issue #3268: nodes such as ``CreateOwnerInitialStatusNode`` and
``AddCaseActorParticipantNode`` build one ``CreateParticipantStatusNode`` in
``__init__`` (BTND-10-004) and run it through ``BTBridge.execute_with_setup``
for whichever actor is executing.  ``initialise`` latches ``_actor_id`` from the
port only while it is empty, so before the fix the *first* actor's id stuck and
a second execution wrote to the first actor's participant.  ``stop`` now restores
the constructor value after every tick, making ``_actor_id`` execution-scoped.
"""

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.participant.status import (
    CreateParticipantStatusNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_status import participant_status_rm_state
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

ACTOR_A = "https://example.test/actors/a"
ACTOR_B = "https://example.test/actors/b"


def test_prebuilt_node_writes_to_the_executing_actor_each_tick(
    bt_scenario: BTTestScenario,
) -> None:
    """Re-using one node for two actors advances each actor's own participant.

    Both participants start auto-seeded at ``RM.START``.  One shared node
    (built with ``actor_id=""``, the pattern of the bootstrap containers) is
    executed once per actor; each must reach ``RM.RECEIVED``.  Before #3268 the
    second execution latched actor A again, leaving actor B at ``RM.START``.
    """
    case = VulnerabilityCase(name="reuse case", attributed_to=ACTOR_A)
    participant_a = CaseParticipant(
        id_=f"{case.id_}/participants/a",
        attributed_to=ACTOR_A,
        context=case.id_,
        case_roles=[CVDRole.COORDINATOR],
    )
    participant_b = CaseParticipant(
        id_=f"{case.id_}/participants/b",
        attributed_to=ACTOR_B,
        context=case.id_,
        case_roles=[CVDRole.COORDINATOR],
    )
    case.add_participant(participant_a)
    case.add_participant(participant_b)
    bt_scenario.seed(participant_a, participant_b, case)

    # One node, built once (BTND-10-004) with an empty constructor actor_id.
    node = CreateParticipantStatusNode(
        actor_id="",
        rm_state=RM.RECEIVED,
        vf_state=None,
        d_state=None,
        pxa_state=None,
    )
    bridge = BTBridge(datalayer=bt_scenario.dl)

    first = bridge.execute_with_setup(node, actor_id=ACTOR_A, case_id=case.id_)
    assert first.status.name == "SUCCESS"

    # Same node object, different executing actor.
    second = bridge.execute_with_setup(
        node, actor_id=ACTOR_B, case_id=case.id_
    )
    assert second.status.name == "SUCCESS"

    reloaded_a = bt_scenario.dl.read(participant_a.id_)
    reloaded_b = bt_scenario.dl.read(participant_b.id_)
    assert isinstance(reloaded_a, CaseParticipant)
    assert isinstance(reloaded_b, CaseParticipant)
    assert (
        participant_status_rm_state(reloaded_a.participant_status)
        == RM.RECEIVED
    )
    # The load-bearing assertion: actor B's write landed on actor B, not on the
    # first actor latched by the shared node.
    assert (
        participant_status_rm_state(reloaded_b.participant_status)
        == RM.RECEIVED
    )


def test_stop_restores_the_constructor_actor_id() -> None:
    """``stop`` resets ``_actor_id`` to the value handed to the constructor."""
    node = CreateParticipantStatusNode(
        actor_id="",
        rm_state=RM.RECEIVED,
        vf_state=None,
        d_state=None,
        pxa_state=None,
    )
    node._actor_id = ACTOR_A  # simulate a latched execution
    node.stop()
    assert node._actor_id == ""

    pinned = CreateParticipantStatusNode(
        actor_id=ACTOR_A,
        rm_state=RM.RECEIVED,
        vf_state=None,
        d_state=None,
        pxa_state=None,
    )
    pinned._actor_id = ACTOR_B
    pinned.stop()
    assert pinned._actor_id == ACTOR_A
