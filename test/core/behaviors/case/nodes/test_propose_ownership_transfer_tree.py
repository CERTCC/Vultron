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

"""Tests for MakeOwnershipTransferOfferNode and the proposal tree (ADR-0148).

The Case Owner proposes a transfer as ``Offer(Offer(VulnerabilityCase))``;
the CASE_MANAGER's received tree makes the one ``Offer(VulnerabilityCase)``
under an id it derives, queues it in its own outbox and ledgers it
(CM-21-005).  A receiver that is not the CASE_MANAGER makes nothing.
"""

from unittest.mock import patch

import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.support.received import with_evidence
from vultron.core.behaviors.case.nodes.ownership_transfer import (
    MakeOwnershipTransferOfferNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_propose_ownership_transfer_tree,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.actor import (
    ProposeCaseOwnershipTransferReceivedEvent,
)
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.use_cases.received.actor.ownership import (
    ProposeCaseOwnershipTransferReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronWiringError

CASE_ID = "https://example.org/cases/case-make"
CASE_ACTOR_ID = "https://example.org/actors/case-actor-make"
VENDOR_ID = "https://example.org/actors/vendor-make"
TRANSFEREE_ID = "https://example.org/actors/transferee-make"
PROPOSAL_ID = "https://example.org/activities/proposal-make"
#: The rule the received use case declares; the vendor is the Case Owner.
_SENDER_RULE = ProposeCaseOwnershipTransferReceivedUseCase.sender_entitlement


def _seed_case(bt_scenario: BTTestScenario) -> None:
    case_actor_participant = CaseParticipant(
        id_="https://example.org/participants/case-actor-make-cp",
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    # Only the Case Owner may propose to offer the case (CM-21-019).
    owner_participant = CaseParticipant(
        id_="https://example.org/participants/vendor-make-cp",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    case = VulnerabilityCase(
        id_=CASE_ID,
        name="MakeOffer test case",
        attributed_to=VENDOR_ID,
        case_participants=[case_actor_participant.id_, owner_participant.id_],
        actor_participant_index={
            CASE_ACTOR_ID: case_actor_participant.id_,
            VENDOR_ID: owner_participant.id_,
        },
    )
    bt_scenario.seed(case_actor_participant, owner_participant, case)


def _offers(bt_scenario: BTTestScenario) -> list[str]:
    """The Offers in the outbox, beside the ledger Announces."""
    return [
        item
        for item in bt_scenario.dl.outbox_list()
        if getattr(
            getattr(bt_scenario.dl.read(item), "type_", None), "value", None
        )
        == "Offer"
    ]


def _proposal_event() -> ProposeCaseOwnershipTransferReceivedEvent:
    """The received proposal as a handler places it on the blackboard.

    A real event: intake reads it first (CLP-10-017), and the commit
    boundary refuses an activity with no ``published`` (CLP-07-011).
    """
    inner = {
        "id": "https://example.org/activities/inner-make",
        "type": "Offer",
        "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
        "target": {"id": TRANSFEREE_ID, "type": "Service"},
    }
    activity = VultronActivity(
        id_=PROPOSAL_ID,
        type_="Offer",
        actor=VENDOR_ID,
        to=[CASE_ACTOR_ID],
        context=CASE_ID,
        published=now_utc(),
        object_=inner,
    )
    return with_evidence(
        ProposeCaseOwnershipTransferReceivedEvent(
            activity_id=PROPOSAL_ID, actor_id=VENDOR_ID, activity=activity
        )
    )


def _tree(transferee_id: str | None = TRANSFEREE_ID, sender=VENDOR_ID):
    return create_propose_ownership_transfer_tree(
        case_id=CASE_ID,
        proposed_case_id=CASE_ID,
        transferee_id=transferee_id,
        proposal_id=PROPOSAL_ID,
        sender_rule=_SENDER_RULE,
        sender_id=sender,
    )


def _make_nodes(node) -> list[MakeOwnershipTransferOfferNode]:
    """Every ``MakeOwnershipTransferOfferNode`` under *node*."""
    found = [node] if isinstance(node, MakeOwnershipTransferOfferNode) else []
    for child in getattr(node, "children", []):
        found.extend(_make_nodes(child))
    return found


@pytest.mark.spec("CM-21-005")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_the_case_manager_makes_one_offer_and_ledgers_it(
    bt_scenario: BTTestScenario,
) -> None:
    """One Offer, under the derived id, queued and then ledgered."""
    # The transferee is off the roster here, which CM-21-021 forbids; #5189
    # (AC-5) seats it as an active participant when the rule is built.
    _seed_case(bt_scenario)

    result = bt_scenario.run(
        _tree(), actor_id=CASE_ACTOR_ID, activity=_proposal_event()
    )

    assert result.status == Status.SUCCESS
    made_id = ownership_offer_id(
        CASE_ACTOR_ID, CASE_ID, PROPOSAL_ID, VENDOR_ID
    )
    assert _offers(bt_scenario) == [made_id]
    offer = bt_scenario.dl.read(made_id)
    assert offer is not None
    assert getattr(offer, "attributed_to", None) == VENDOR_ID
    entries = {
        entry.semantic_type: entry
        for entry in bt_scenario.dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    }
    assert entries["offer_case_ownership_transfer"].log_object_id == made_id
    assert (
        entries["propose_case_ownership_transfer"].log_object_id == PROPOSAL_ID
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "CM-21-021: a transferee off the roster is not refused yet. "
        "Tracked by #5189."
    ),
)
@pytest.mark.spec("CM-21-021")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_a_transferee_that_is_not_an_active_participant_is_refused(
    bt_scenario: BTTestScenario,
) -> None:
    """No Offer, and so no case content, goes to an actor off the roster."""
    _seed_case(bt_scenario)

    result = bt_scenario.run(
        _tree(), actor_id=CASE_ACTOR_ID, activity=_proposal_event()
    )

    assert result.status == Status.FAILURE
    assert _offers(bt_scenario) == []
    assert not [
        entry
        for entry in bt_scenario.dl.list_objects("CaseLedgerEntry")
        if isinstance(entry, CaseLedgerEntry)
    ]


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("BT-17-008")
def test_a_receiver_that_is_not_the_case_manager_makes_nothing(
    bt_scenario_factory,
) -> None:
    """The effect sits behind the CASE_MANAGER gate the factory composes."""
    bt_scenario: BTTestScenario = bt_scenario_factory(VENDOR_ID)
    _seed_case(bt_scenario)

    with patch.object(
        MakeOwnershipTransferOfferNode, "update", autospec=True
    ) as mock_update:
        bt_scenario.run(
            _tree(), actor_id=VENDOR_ID, activity=_proposal_event()
        )

    mock_update.assert_not_called()
    assert _offers(bt_scenario) == []


@pytest.mark.spec("CM-21-005")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_a_missing_factory_is_a_wiring_fault(
    bt_scenario: BTTestScenario,
) -> None:
    """With no factory the Offer cannot be made: the node fails, nothing is
    queued, and the handler reports an internal error, not a refusal."""
    _seed_case(bt_scenario)
    node = MakeOwnershipTransferOfferNode(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        owner_id=VENDOR_ID,
        proposal_id=PROPOSAL_ID,
    )
    node.datalayer = bt_scenario.dl
    node.actor_id = CASE_ACTOR_ID
    node.trigger_activity_factory = None

    with pytest.raises(VultronWiringError):
        node.update()

    assert bt_scenario.dl.outbox_list() == []


@pytest.mark.spec("CM-21-005")
def test_no_offer_is_built_for_a_proposal_naming_no_transferee() -> None:
    """The guard refuses such a proposal; no effect is composed for it."""
    assert _make_nodes(_tree(transferee_id=None)) == []
    assert len(_make_nodes(_tree())) == 1
