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

"""Regression tests for ISSUE-2252 — accept-ownership-transfer BT commit guard.

Verifies that ``create_accept_ownership_transfer_tree`` commits exactly one
canonical ledger entry when the CaseActor processes the Accept, and zero
entries when any other actor processes it.

Root cause: an extra unguarded ``CommitCaseLedgerEntryNode`` in ``effect_nodes``
allowed the transferee to write a second entry at the same ``log_index`` as the
CaseActor's guarded commit, producing a hash-chain fork (AC-3, CLP-09-001).
"""

from unittest.mock import patch

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.ownership_transfer_tree import (
    create_accept_ownership_transfer_tree,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

CASE_ID = "https://example.org/cases/case-2252"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
TRANSFEREE_ID = "https://example.org/actors/coordinator"
OFFER_ID = "https://example.org/activities/offer-2252"


def _seed_case(bt_scenario: BTTestScenario) -> None:
    case_actor_participant = VultronParticipant(
        id_="https://example.org/participants/case-actor-cp",
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    transferee_participant = VultronParticipant(
        id_="https://example.org/participants/coordinator-cp",
        attributed_to=TRANSFEREE_ID,
        context=CASE_ID,
        case_roles=[CVDRole.COORDINATOR],
    )
    case = VultronCase(
        id_=CASE_ID,
        name="ISSUE-2252 test case",
        attributed_to="https://example.org/actors/vendor",
        case_participants=[
            case_actor_participant.id_,
            transferee_participant.id_,
        ],
        actor_participant_index={
            CASE_ACTOR_ID: case_actor_participant.id_,
            TRANSFEREE_ID: transferee_participant.id_,
        },
    )
    bt_scenario.seed(case_actor_participant, transferee_participant, case)


class _FakeAcceptActivity:
    """Minimal accept activity for the blackboard."""

    activity_id = OFFER_ID

    class activity:
        @staticmethod
        def model_dump(**_: object) -> dict:
            return {
                "id": OFFER_ID,
                "type": "Accept",
                "actor": TRANSFEREE_ID,
                "context": CASE_ID,
                "object": {
                    "id": OFFER_ID,
                    "type": "Offer",
                    "object": {"id": CASE_ID, "type": "VulnerabilityCase"},
                },
            }


@pytest.mark.parametrize(
    "actor_id,expect_commit",
    [
        (CASE_ACTOR_ID, True),
        (TRANSFEREE_ID, False),
    ],
)
@pytest.mark.spec("CM-21-007")
def test_accept_ownership_transfer_commit_is_role_gated(
    bt_scenario_factory,
    actor_id: str,
    expect_commit: bool,
) -> None:
    """CaseActor commits exactly once; all other actors skip the commit.

    Regression for ISSUE-2252: the previous tree had an extra unguarded
    ``CommitCaseLedgerEntryNode`` in ``effect_nodes`` that fired for the
    transferee, writing a duplicate entry at the same ``log_index`` as the
    CaseActor's guarded commit (CLP-09-001, AC-3).

    The scenario is built per parameter rather than taken from the ``bt_scenario``
    fixture, because this test has *two* executing actors and a BT's store follows
    the actor it executes as (ADR-0072).  One shared store would leave whichever
    actor did not own it reading an empty one — the case would be absent, the role
    guard would fail for lack of a case rather than for lack of the role, and the
    "transferee does not commit" half would pass for the wrong reason.
    """
    bt_scenario: BTTestScenario = bt_scenario_factory(actor_id)
    _seed_case(bt_scenario)
    tree = create_accept_ownership_transfer_tree(
        case_id=CASE_ID,
        new_owner_id=TRANSFEREE_ID,
    )

    with patch.object(
        CommitCaseLedgerEntryNode, "update", autospec=True
    ) as mock_commit:
        mock_commit.return_value = Status.SUCCESS
        result = bt_scenario.run(
            tree, actor_id=actor_id, activity=_FakeAcceptActivity()
        )

    assert result.status == Status.SUCCESS
    if expect_commit:
        mock_commit.assert_called_once()
    else:
        mock_commit.assert_not_called()


@pytest.mark.spec("CM-21-007")
@pytest.mark.executes_as(CASE_ACTOR_ID)
def test_accept_ownership_transfer_no_double_commit(
    bt_scenario: BTTestScenario,
) -> None:
    """Only one ``CommitCaseLedgerEntryNode.update`` call fires for CaseActor.

    Guards against re-introducing the ISSUE-2252 double-write: if
    ``CommitCaseLedgerEntryNode`` appears in ``effect_nodes`` AND is injected
    by ``create_receive_activity_tree``, it fires twice — forking the chain.
    """
    _seed_case(bt_scenario)
    tree = create_accept_ownership_transfer_tree(
        case_id=CASE_ID,
        new_owner_id=TRANSFEREE_ID,
    )

    with patch.object(
        CommitCaseLedgerEntryNode, "update", autospec=True
    ) as mock_commit:
        mock_commit.return_value = Status.SUCCESS
        bt_scenario.run(
            tree, actor_id=CASE_ACTOR_ID, activity=_FakeAcceptActivity()
        )

    assert mock_commit.call_count == 1, (
        f"Expected exactly 1 CommitCaseLedgerEntryNode.update call for "
        f"CaseActor; got {mock_commit.call_count}. "
        f"A count > 1 means the double-write bug (ISSUE-2252) is back."
    )
