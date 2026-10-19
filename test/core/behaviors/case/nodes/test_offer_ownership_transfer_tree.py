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

"""Tests for ForwardOfferToTransfereeNode and create_offer_ownership_transfer_tree.

Verifies CM-21-005 / ADR-0053: when the CaseActor receives an
Offer(VulnerabilityCase) ownership-transfer activity it MUST build a new
forwarded Offer via trigger_activity_factory and queue it in its own outbox.
Non-CaseManager actors MUST skip the forwarding step cleanly (role gate).
"""

from unittest.mock import patch

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_offer_ownership_transfer_tree,
)
from vultron.core.models._helpers import _as_id, now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    OfferCaseOwnershipTransferReceivedEvent,
)
from vultron.core.use_cases.received.actor.ownership import (
    OfferCaseOwnershipTransferReceivedUseCase,
)
from vultron.enums.roles import CVDRole

CASE_ID = "https://example.org/cases/case-fwd"
CASE_ACTOR_ID = "https://example.org/actors/case-actor-fwd"
VENDOR_ID = "https://example.org/actors/vendor-fwd"
TRANSFEREE_ID = "https://example.org/actors/transferee-fwd"
OFFER_ID = "https://example.org/activities/offer-fwd"
#: The rule the received use case declares; the vendor is the Case Owner.
_SENDER_RULE = OfferCaseOwnershipTransferReceivedUseCase.sender_entitlement


def _seed_case(bt_scenario: BTTestScenario) -> None:
    case_actor_participant = CaseParticipant(
        id_="https://example.org/participants/case-actor-fwd-cp",
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    # Only the Case Owner may offer the case (CM-21-019).
    owner_participant = CaseParticipant(
        id_="https://example.org/participants/vendor-fwd-cp",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="ForwardOffer test case",
        attributed_to=VENDOR_ID,
        case_participants=[case_actor_participant.id_, owner_participant.id_],
        actor_participant_index={
            CASE_ACTOR_ID: case_actor_participant.id_,
            VENDOR_ID: owner_participant.id_,
        },
    )
    bt_scenario.seed(case_actor_participant, owner_participant, case)


def _forwards(bt_scenario: BTTestScenario) -> list[str]:
    """The Offers in the outbox: the forward, beside the ledger Announce."""
    return [
        item
        for item in bt_scenario.dl.outbox_list()
        if getattr(
            getattr(bt_scenario.dl.read(item), "type_", None), "value", None
        )
        == "Offer"
    ]


def _offer_event() -> OfferCaseOwnershipTransferReceivedEvent:
    """The received Offer(Case, Actor) as a handler places it on the blackboard.

    A real event, not a stand-in: intake reads it first (CLP-10-017) and a
    bare object would be a wiring fault.  CLP-07-011: real activities always
    carry ``published``; one that omits it is rejected at the commit boundary.
    """
    activity = VultronActivity(
        id_=OFFER_ID,
        type_="Offer",
        actor=VENDOR_ID,
        to=[CASE_ACTOR_ID],
        context=CASE_ID,
        published=now_utc(),
        object_={"id": CASE_ID, "type": "VulnerabilityCase"},
        target={"id": TRANSFEREE_ID, "type": "Service"},
    )
    return OfferCaseOwnershipTransferReceivedEvent(
        activity_id=OFFER_ID, actor_id=VENDOR_ID, activity=activity
    )


def _forward_nodes(node) -> list[ForwardOfferToTransfereeNode]:
    """Every ``ForwardOfferToTransfereeNode`` anywhere in the tree under *node*."""
    found = [node] if isinstance(node, ForwardOfferToTransfereeNode) else []
    for child in getattr(node, "children", []):
        found.extend(_forward_nodes(child))
    return found


@pytest.mark.spec("CM-21-005")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_forward_offer_to_transferee_queues_in_case_actor_outbox(
    bt_scenario: BTTestScenario,
) -> None:
    """CaseActor's ForwardOfferToTransfereeNode enqueues a forwarded offer.

    Verifies that when the CaseActor executes the offer-ownership-transfer BT
    with trigger_activity wired up, the factory is called and the forwarded
    offer ID lands in the CaseActor's outbox (CM-21-005).
    """
    _seed_case(bt_scenario)
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=VENDOR_ID,
        offer_id=OFFER_ID,
        sender_rule=_SENDER_RULE,
        sender_id=VENDOR_ID,
    )

    result = bt_scenario.run(
        tree, actor_id=CASE_ACTOR_ID, activity=_offer_event()
    )

    assert result.status == Status.SUCCESS
    # The real TriggerActivityAdapter creates the activity; check outbox non-empty.
    forwards = _forwards(bt_scenario)
    assert len(forwards) == 1, (
        f"Expected exactly 1 forwarded offer in CaseActor outbox; got {forwards}"
    )


@pytest.mark.spec("CM-21-018")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_forward_offer_replies_to_the_recorded_offer(
    bt_scenario: BTTestScenario,
) -> None:
    """The forward names the recorded Offer it stands for in ``inReplyTo``."""
    _seed_case(bt_scenario)
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=VENDOR_ID,
        offer_id=OFFER_ID,
        sender_rule=_SENDER_RULE,
        sender_id=VENDOR_ID,
    )

    result = bt_scenario.run(
        tree, actor_id=CASE_ACTOR_ID, activity=_offer_event()
    )

    assert result.status == Status.SUCCESS
    (forward_id,) = _forwards(bt_scenario)
    forward = bt_scenario.dl.read(forward_id)
    assert _as_id(getattr(forward, "in_reply_to", None)) == OFFER_ID


@pytest.mark.spec("CM-21-005")
def test_non_case_manager_skips_forward(bt_scenario_factory) -> None:
    """Non-CaseManager actor skips ForwardOfferToTransfereeNode (role gate).

    The create_case_manager_gated_tree wrapper returns SUCCESS for actors
    without CASE_MANAGER — no factory call, no outbox write.
    """
    bt_scenario: BTTestScenario = bt_scenario_factory(VENDOR_ID)
    _seed_case(bt_scenario)
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=VENDOR_ID,
        offer_id=OFFER_ID,
        sender_rule=_SENDER_RULE,
        sender_id=CASE_ACTOR_ID,  # the forward, from the CASE_MANAGER
    )

    with patch.object(
        ForwardOfferToTransfereeNode, "update", autospec=True
    ) as mock_update:
        result = bt_scenario.run(
            tree, actor_id=VENDOR_ID, activity=_offer_event()
        )

    assert result.status == Status.SUCCESS
    mock_update.assert_not_called()


@pytest.mark.spec("CM-21-005")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_forward_offer_warns_when_no_factory(
    bt_scenario: BTTestScenario, caplog
) -> None:
    """ForwardOfferToTransfereeNode warns and returns FAILURE when factory absent.

    When BTBridge is not given a trigger_activity port, the node must emit a
    WARNING containing 'no trigger_activity' and leave the outbox untouched.
    """
    _seed_case(bt_scenario)

    node = ForwardOfferToTransfereeNode(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=VENDOR_ID,
        offer_id=OFFER_ID,
    )
    # Inject datalayer and actor_id manually; leave trigger_activity_factory None.
    node.datalayer = bt_scenario.dl
    node.actor_id = CASE_ACTOR_ID
    node.trigger_activity_factory = None

    with caplog.at_level("WARNING"):
        status = node.update()

    assert status == Status.FAILURE
    assert any("no trigger_activity" in r.message for r in caplog.records)
    assert bt_scenario.dl.outbox_list() == []


@pytest.mark.spec("CM-21-005")
def test_tree_factory_omits_forward_node_when_transferee_id_is_none() -> None:
    """No ForwardOfferToTransfereeNode is added when transferee_id is None.

    The ledger-commit gate must still fire, but no forwarding occurs.
    """
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=None,
        original_actor_id=VENDOR_ID,
        offer_id=OFFER_ID,
        sender_rule=_SENDER_RULE,
        sender_id=VENDOR_ID,
    )

    assert _forward_nodes(tree) == [], (
        "ForwardOfferToTransfereeNode must not appear when transferee_id is None"
    )


@pytest.mark.spec("CM-21-005")
def test_tree_factory_omits_forward_node_when_original_actor_id_is_none() -> (
    None
):
    """No ForwardOfferToTransfereeNode is added when original_actor_id is None."""
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=None,
        offer_id=OFFER_ID,
        sender_rule=_SENDER_RULE,
        sender_id=VENDOR_ID,
    )

    assert _forward_nodes(tree) == [], (
        "ForwardOfferToTransfereeNode must not appear when original_actor_id is None"
    )


@pytest.mark.spec("CM-21-018")
def test_tree_factory_omits_forward_node_when_offer_id_is_none() -> None:
    """No forward is built without the recorded Offer's id to link it to."""
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=VENDOR_ID,
        sender_rule=_SENDER_RULE,
        sender_id=VENDOR_ID,
    )

    assert _forward_nodes(tree) == [], (
        "a forward with no inReplyTo link must never be built (CM-21-018)"
    )
