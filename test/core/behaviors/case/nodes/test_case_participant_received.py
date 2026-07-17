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

"""Tests for Add/Remove case participant BT leaf nodes."""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.case_participant_received import (
    AddCaseParticipantToCaseReceivedNode,
    RemoveCaseParticipantFromCaseReceivedNode,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/owner"
COORDINATOR_ID = "https://example.org/actors/coordinator"
CASE_ID = "https://example.org/cases/case-cp-01"
PARTICIPANT_ID = f"{CASE_ID}/participants/coord"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def case():
    return as_VulnerabilityCase(id_=CASE_ID, name="CP Node Test Case")


@pytest.fixture
def participant(case):
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        attributed_to=COORDINATOR_ID,
        context=case.id_,
    )


class TestAddCaseParticipantToCaseReceivedNode:
    """Unit tests for AddCaseParticipantToCaseReceivedNode."""

    def test_adds_participant_to_case(
        self, bridge, dl, case, participant
    ) -> None:
        """Happy path: participant is added and case is saved."""
        dl.create(case)
        dl.create(participant)
        tree = AddCaseParticipantToCaseReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        pids = [getattr(p, "id_", p) for p in refreshed.case_participants]
        assert PARTICIPANT_ID in pids

    def test_updates_actor_participant_index(
        self, bridge, dl, case, participant
    ) -> None:
        """actor_participant_index is populated after add (SC-PRE-2)."""
        dl.create(case)
        dl.create(participant)
        tree = AddCaseParticipantToCaseReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=CASE_ID
        )
        bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert COORDINATOR_ID in refreshed.actor_participant_index

    def test_fails_when_case_not_found(self, bridge, dl, participant) -> None:
        """FAILURE when case is missing from DataLayer."""
        dl.create(participant)
        tree = AddCaseParticipantToCaseReceivedNode(
            participant_id=PARTICIPANT_ID,
            case_id="https://example.org/cases/missing",
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE

    def test_fails_when_participant_not_found(self, bridge, dl, case) -> None:
        """FAILURE when participant is missing from DataLayer."""
        dl.create(case)
        tree = AddCaseParticipantToCaseReceivedNode(
            participant_id="https://example.org/participants/missing",
            case_id=CASE_ID,
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE


class TestRemoveCaseParticipantFromCaseReceivedNode:
    """Unit tests for RemoveCaseParticipantFromCaseReceivedNode."""

    def test_removes_participant_from_case(
        self, bridge, dl, case, participant
    ) -> None:
        """Happy path: participant removed and case persisted."""
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        tree = RemoveCaseParticipantFromCaseReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        pids = [getattr(p, "id_", p) for p in refreshed.case_participants]
        assert PARTICIPANT_ID not in pids

    def test_clears_actor_participant_index(
        self, bridge, dl, case, participant
    ) -> None:
        """actor_participant_index entry is removed after remove."""
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        assert COORDINATOR_ID in case.actor_participant_index
        tree = RemoveCaseParticipantFromCaseReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=CASE_ID
        )
        bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert COORDINATOR_ID not in refreshed.actor_participant_index

    def test_idempotent_when_participant_already_absent(
        self, bridge, dl, case
    ) -> None:
        """SUCCESS when participant is not in case (no-op, idempotent)."""
        dl.create(case)
        tree = RemoveCaseParticipantFromCaseReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=CASE_ID
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.SUCCESS

    def test_fails_when_case_not_found(self, bridge, dl) -> None:
        """FAILURE when case is missing from DataLayer."""
        tree = RemoveCaseParticipantFromCaseReceivedNode(
            participant_id=PARTICIPANT_ID,
            case_id="https://example.org/cases/missing",
        )
        result = bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)
        assert result.status == Status.FAILURE
