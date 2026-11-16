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

"""The door and guard nodes read their case from ``/case_id`` (BTND-01-006).

Each stage builder seeds the port with the case the tree names, so a tree
built today hands each node the case it handed it through the constructor
before; and a structural check that inspects one of these nodes looks
through the :class:`~vultron.core.behaviors.case_id_scope.CaseIdScope` that
seeds it (#6500).
"""

import py_trees
import pytest

from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
    refusal_notice,
)
from vultron.core.behaviors.case.receive_stages.doors import post_close_stage
from vultron.core.behaviors.case.receive_stages.guards import refusal_stage
from vultron.core.behaviors.case_id_scope import (
    seeded_case_id,
    unscoped,
    with_case_id,
)
from vultron.core.behaviors.sender_check_context import SenderCheckContext
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderIsActiveParticipantNode,
    SenderIsParticipantNode,
    SenderRule,
)
from vultron.core.behaviors.sender_guard import compose_sender_guard
from vultron.core.behaviors.sync.nodes.sender_sequence import (
    ClassifySequenceNumberNode,
    EmitSequenceRefusalNoticeNode,
)
from vultron.core.behaviors.sync.sender_sequence_stage import (
    create_sender_sequence_stage,
)
from vultron.errors import VultronWiringError

CASE = "https://example.org/cases/c1"
SENDER = "https://example.org/actors/sender"


def _all_of(root: py_trees.behaviour.Behaviour, cls: type) -> list:
    return [n for n in root.iterate() if isinstance(n, cls)]


def _assert_seeded(nodes: list) -> None:
    assert nodes, "the builder placed no such node"
    for node in nodes:
        assert seeded_case_id(node) == CASE


@pytest.mark.spec("BTND-01-006")
def test_post_close_stage_seeds_the_guard_with_the_tree_case():
    (stage,) = post_close_stage("T", CASE, None, [])
    assert isinstance(unscoped(stage), CaseOpenToExternalWritesNode)
    _assert_seeded(_all_of(stage, CaseOpenToExternalWritesNode))


@pytest.mark.spec("BTND-01-006")
def test_post_close_stage_with_no_case_leaves_the_guard_unseeded():
    (stage,) = post_close_stage("T", None, None, [])
    assert isinstance(stage, CaseOpenToExternalWritesNode)
    assert seeded_case_id(stage) is None


@pytest.mark.spec("BTND-01-006")
@pytest.mark.parametrize(
    ("kind", "cls"),
    [
        (SenderEntitlementKind.PARTICIPANT, SenderIsParticipantNode),
        (
            SenderEntitlementKind.ACTIVE_PARTICIPANT,
            SenderIsActiveParticipantNode,
        ),
    ],
)
def test_sender_guard_seeds_the_membership_node(kind, cls):
    guard = compose_sender_guard(
        SenderRule(
            at_case_manager=frozenset({kind}),
            at_participant=frozenset({kind}),
            outside_case=frozenset({kind}),
        ),
        SenderCheckContext(sender_id=SENDER, case_id=CASE),
    )
    assert guard is not None
    _assert_seeded(_all_of(guard, cls))


@pytest.mark.spec("BTND-01-006")
def test_refusal_notice_is_seeded_with_its_case():
    notice = refusal_notice(CASE)
    assert isinstance(unscoped(notice), EmitRefusalNoticeNode)
    _assert_seeded(_all_of(notice, EmitRefusalNoticeNode))


@pytest.mark.spec("BTND-01-006")
@pytest.mark.spec("SYNC-21-001")
def test_sender_sequence_stage_seeds_its_case_scoped_nodes():
    stage = create_sender_sequence_stage(CASE, SENDER)
    _assert_seeded(_all_of(stage, ClassifySequenceNumberNode))
    _assert_seeded(_all_of(stage, EmitSequenceRefusalNoticeNode))


@pytest.mark.spec("BTND-01-006")
def test_refusal_stage_admits_a_seeded_emitter():
    """The emit-capable check reads the node inside the scope (#6500)."""
    stage = refusal_stage(
        "T",
        [py_trees.behaviours.Success(name="Guard")],
        [refusal_notice(CASE)],
        CASE,
        intake_ran=True,
    )
    _assert_seeded(_all_of(stage, EmitRefusalNoticeNode))


@pytest.mark.spec("BTND-01-006")
def test_refusal_stage_names_the_seeded_node_it_refuses():
    """A scoped non-emitter is refused by its own type, not the scope's."""
    with pytest.raises(VultronWiringError, match="Success"):
        refusal_stage(
            "T",
            [py_trees.behaviours.Success(name="Guard")],
            [
                with_case_id(
                    py_trees.behaviours.Success(name="NotAnEmit"), CASE
                )
            ],
            CASE,
            intake_ran=True,
        )


@pytest.mark.spec("BTND-01-006")
def test_an_unseeded_sequence_classifier_is_a_wiring_fault():
    """The stage builder always seeds the port; a node it did not seed
    names the missing seed rather than judging a number on no case."""
    node = ClassifySequenceNumberNode(sender_id=SENDER)
    with pytest.raises(VultronWiringError, match="/case_id"):
        _ = node.case_id
