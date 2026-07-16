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

from datetime import timezone
from unittest.mock import patch

import pytest
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
    create_guarded_commit_case_ledger_entry_tree,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.vultron_types import VultronCase, VultronParticipant
from vultron.enums.roles import CVDRole
from test.core.behaviors.bt_harness import BTTestScenario

CASE_ID = "https://example.org/cases/case-001"
MANAGER_ACTOR_ID = "https://example.org/actors/coordinator"
NON_MANAGER_ACTOR_ID = "https://example.org/actors/vendor"
ACTIVITY_ID = "https://example.org/activities/act-001"


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
        attributed_to=MANAGER_ACTOR_ID,
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


class _FakeActivity:
    """Minimal stand-in activity for CommitCaseLedgerEntryNode blackboard input.

    The payload uses ``("Create", "VulnerabilityCase")`` — a canonical
    signature per ``_CANONICAL_PAYLOAD_SIGNATURES`` — with an inline object
    dict (not a bare URI string) and a non-empty ``actor`` URI.
    """

    def __init__(
        self,
        activity_id: str = ACTIVITY_ID,
        semantic_type: MessageSemantics = MessageSemantics.CREATE_CASE,
    ):
        self.activity_id = activity_id
        self.semantic_type = semantic_type

        class _Payload:
            def model_dump(self, **_: object) -> dict[str, object]:
                return {
                    "id": activity_id,
                    "type": "Create",
                    "actor": MANAGER_ACTOR_ID,
                    "object": {
                        "id": CASE_ID,
                        "type": "VulnerabilityCase",
                    },
                }

        self.activity = _Payload()


@pytest.fixture
def _seeded_scenario(bt_scenario: BTTestScenario) -> BTTestScenario:
    """BTTestScenario pre-seeded with a case and CASE_MANAGER participant."""
    _seed_case_with_manager(bt_scenario)
    return bt_scenario


def test_guarded_commit_tree_entry_has_non_empty_hash(
    _seeded_scenario: BTTestScenario,
) -> None:
    """CaseLedgerEntry committed by CaseActor MUST have a non-empty entry_hash.

    The CaseActor identity is MANAGER_ACTOR_ID — explicitly seeded in the
    fixture, with no ID derivation at runtime (CM-02-009, Issue #1021).
    """
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        CaseLedgerEntry as WireCaseLedgerEntry,
    )

    activity = _FakeActivity()
    tree = create_guarded_commit_case_ledger_entry_tree(case_id=CASE_ID)
    result = _seeded_scenario.run(
        tree, actor_id=MANAGER_ACTOR_ID, activity=activity
    )
    assert result.status == Status.SUCCESS

    entries = [
        e
        for e in _seeded_scenario.dl.list_objects("CaseLedgerEntry")
        if isinstance(e, WireCaseLedgerEntry) and e.case_id == CASE_ID
    ]
    assert len(entries) >= 1
    for entry in entries:
        assert entry.entry_hash is not None
        assert len(entry.entry_hash) > 0


def test_guarded_commit_tree_entry_has_utc_received_at(
    _seeded_scenario: BTTestScenario,
) -> None:
    """CaseLedgerEntry committed by CaseActor MUST have a UTC received_at timestamp.

    The CaseActor identity is MANAGER_ACTOR_ID — explicitly seeded in the
    fixture, with no ID derivation at runtime (CM-02-009, Issue #1021).
    """
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        CaseLedgerEntry as WireCaseLedgerEntry,
    )

    activity = _FakeActivity()
    tree = create_guarded_commit_case_ledger_entry_tree(case_id=CASE_ID)
    result = _seeded_scenario.run(
        tree, actor_id=MANAGER_ACTOR_ID, activity=activity
    )
    assert result.status == Status.SUCCESS

    entries = [
        e
        for e in _seeded_scenario.dl.list_objects("CaseLedgerEntry")
        if isinstance(e, WireCaseLedgerEntry) and e.case_id == CASE_ID
    ]
    assert len(entries) >= 1
    for entry in entries:
        assert entry.received_at is not None
        assert entry.received_at.tzinfo is not None
        assert entry.received_at.tzinfo == timezone.utc


def test_guarded_commit_tree_entry_references_correct_case_id(
    _seeded_scenario: BTTestScenario,
) -> None:
    """CaseLedgerEntry committed by CaseActor MUST reference the correct case_id.

    The CaseActor identity is MANAGER_ACTOR_ID — explicitly seeded in the
    fixture, with no ID derivation at runtime (CM-02-009, Issue #1021).
    """
    from vultron.wire.as2.vocab.objects.case_ledger_entry import (
        CaseLedgerEntry as WireCaseLedgerEntry,
    )

    activity = _FakeActivity()
    tree = create_guarded_commit_case_ledger_entry_tree(case_id=CASE_ID)
    result = _seeded_scenario.run(
        tree, actor_id=MANAGER_ACTOR_ID, activity=activity
    )
    assert result.status == Status.SUCCESS

    entries = [
        e
        for e in _seeded_scenario.dl.list_objects("CaseLedgerEntry")
        if isinstance(e, WireCaseLedgerEntry) and e.case_id == CASE_ID
    ]
    assert len(entries) >= 1
    assert all(e.case_id == CASE_ID for e in entries)
