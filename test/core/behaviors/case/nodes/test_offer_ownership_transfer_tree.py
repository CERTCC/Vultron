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

import pytest

from vultron.core.models._helpers import _now_utc
from py_trees.common import Status
from unittest.mock import patch

from vultron.core.behaviors.case.nodes.ownership_transfer import (
    ForwardOfferToTransfereeNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_offer_ownership_transfer_tree,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

CASE_ID = "https://example.org/cases/case-fwd"
CASE_ACTOR_ID = "https://example.org/actors/case-actor-fwd"
VENDOR_ID = "https://example.org/actors/vendor-fwd"
TRANSFEREE_ID = "https://example.org/actors/transferee-fwd"
OFFER_ID = "https://example.org/activities/offer-fwd"


def _seed_case(bt_scenario: BTTestScenario) -> None:
    case_actor_participant = VultronParticipant(
        id_="https://example.org/participants/case-actor-fwd-cp",
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    case = VultronCase(
        id_=CASE_ID,
        name="ForwardOffer test case",
        attributed_to=VENDOR_ID,
        case_participants=[case_actor_participant.id_],
        actor_participant_index={
            CASE_ACTOR_ID: case_actor_participant.id_,
        },
    )
    bt_scenario.seed(case_actor_participant, case)


class _FakeOfferActivity:
    activity_id = OFFER_ID

    class activity:
        @staticmethod
        def model_dump(**_: object) -> dict:
            return {
                "id": OFFER_ID,
                "type": "Offer",
                "actor": VENDOR_ID,
                # CLP-07-011: real activities always carry ``published``; a
                # fake that omits it is rejected at the commit boundary.
                "published": _now_utc().isoformat(),
                "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
                "target": {"id": TRANSFEREE_ID, "type": "Service"},
            }


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
    )

    result = bt_scenario.run(
        tree, actor_id=CASE_ACTOR_ID, activity=_FakeOfferActivity()
    )

    assert result.status == Status.SUCCESS
    # The real TriggerActivityAdapter creates the activity; check outbox non-empty.
    outbox = bt_scenario.dl.outbox_list()
    assert (
        len(outbox) == 1
    ), f"Expected exactly 1 forwarded offer in CaseActor outbox; got {outbox}"


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
    )

    with patch.object(
        ForwardOfferToTransfereeNode, "update", autospec=True
    ) as mock_update:
        result = bt_scenario.run(
            tree, actor_id=VENDOR_ID, activity=_FakeOfferActivity()
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
    )

    # Walk the tree: ForwardOfferToTransfereeNode must not appear anywhere.
    def _collect(node):
        nodes = [node]
        for child in getattr(node, "children", []):
            nodes.extend(_collect(child))
        return nodes

    all_nodes = _collect(tree)
    fwd_nodes = [
        n for n in all_nodes if isinstance(n, ForwardOfferToTransfereeNode)
    ]
    assert (
        len(fwd_nodes) == 0
    ), "ForwardOfferToTransfereeNode must not appear when transferee_id is None"


@pytest.mark.spec("CM-21-005")
def test_tree_factory_omits_forward_node_when_original_actor_id_is_none() -> (
    None
):
    """No ForwardOfferToTransfereeNode is added when original_actor_id is None."""
    tree = create_offer_ownership_transfer_tree(
        case_id=CASE_ID,
        transferee_id=TRANSFEREE_ID,
        original_actor_id=None,
    )

    def _collect(node):
        nodes = [node]
        for child in getattr(node, "children", []):
            nodes.extend(_collect(child))
        return nodes

    all_nodes = _collect(tree)
    fwd_nodes = [
        n for n in all_nodes if isinstance(n, ForwardOfferToTransfereeNode)
    ]
    assert (
        len(fwd_nodes) == 0
    ), "ForwardOfferToTransfereeNode must not appear when original_actor_id is None"
