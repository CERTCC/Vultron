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

"""Unit tests for ``create_guarded_commit_case_ledger_entry_tree``."""

from unittest.mock import patch

from py_trees.common import Status

from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
    create_guarded_commit_case_ledger_entry_tree,
)
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.core.states.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

CASE_ID = "https://example.org/cases/case-001"
MANAGER_ACTOR_ID = "https://example.org/actors/coordinator"
NON_MANAGER_ACTOR_ID = "https://example.org/actors/vendor"


def _seed_case_with_manager(bt_scenario: BTTestScenario) -> None:
    manager_participant = VultronParticipant(
        id_="https://example.org/participants/coordinator-cp-001",
        attributed_to=MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
    )
    vendor_participant = VultronParticipant(
        id_="https://example.org/participants/vendor-cp-001",
        attributed_to=NON_MANAGER_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.VENDOR],
    )
    case = VultronCase(
        id_=CASE_ID,
        name="Test Case",
        case_participants=[manager_participant.id_, vendor_participant.id_],
        actor_participant_index={
            MANAGER_ACTOR_ID: manager_participant.id_,
            NON_MANAGER_ACTOR_ID: vendor_participant.id_,
        },
    )
    bt_scenario.seed(manager_participant, vendor_participant, case)


def test_guarded_commit_tree_calls_commit_for_case_manager(
    bt_scenario: BTTestScenario,
) -> None:
    _seed_case_with_manager(bt_scenario)
    tree = create_guarded_commit_case_ledger_entry_tree(case_id=CASE_ID)

    with patch.object(
        CommitCaseLedgerEntryNode, "update", autospec=True
    ) as mock_update:
        mock_update.return_value = Status.SUCCESS
        result = bt_scenario.run(tree, actor_id=MANAGER_ACTOR_ID)

    assert result.status == Status.SUCCESS
    mock_update.assert_called_once()


def test_guarded_commit_tree_skips_commit_for_non_manager(
    bt_scenario: BTTestScenario,
) -> None:
    _seed_case_with_manager(bt_scenario)
    tree = create_guarded_commit_case_ledger_entry_tree(case_id=CASE_ID)

    with patch.object(
        CommitCaseLedgerEntryNode, "update", autospec=True
    ) as mock_update:
        result = bt_scenario.run(tree, actor_id=NON_MANAGER_ACTOR_ID)

    assert result.status == Status.SUCCESS
    mock_update.assert_not_called()
