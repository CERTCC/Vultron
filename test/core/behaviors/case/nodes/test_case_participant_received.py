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
    RemovalNamesCaseParticipantNode,
    RemoveCaseParticipantFromCaseReceivedNode,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    ParticipantHasJoinedNode,
    ParticipantIsRemovedNode,
    ReinstateCaseParticipantReceivedNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/owner"
COORDINATOR_ID = "https://example.org/actors/coordinator"
CASE_ID = "https://example.org/cases/case-cp-01"
PARTICIPANT_ID = f"{CASE_ID}/participants/coord"


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=ACTOR_ID,
    )


@pytest.fixture
def bridge(dl):
    return BTBridge(datalayer=dl)


@pytest.fixture
def case():
    return VulnerabilityCase(
        id_=CASE_ID, name="CP Node Test Case", attributed_to=ACTOR_ID
    )


@pytest.fixture
def participant(case):
    return as_CaseParticipant(
        id_=PARTICIPANT_ID,
        attributed_to=COORDINATOR_ID,
        context=case.id_,
    )


REMOVE_ID = "https://example.org/activities/remove-coord"


class TestRemoveCaseParticipantFromCaseReceivedNode:
    """Removal sets the fact and keeps the record (CM-31-001, ADR-0116)."""

    def _run(self, bridge, case_id: str = CASE_ID):
        tree = RemoveCaseParticipantFromCaseReceivedNode(
            participant_id=PARTICIPANT_ID,
            case_id=case_id,
            removal_activity_id=REMOVE_ID,
        )
        return bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)

    @pytest.mark.spec("CM-31-001")
    def test_keeps_the_participant_on_the_roster(
        self, bridge, dl, case, participant
    ) -> None:
        """Inverted from the deletion pin: the record stays in the case."""
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        result = self._run(bridge)

        assert result.status == Status.SUCCESS
        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        pids = [getattr(p, "id_", p) for p in refreshed.case_participants]
        assert PARTICIPANT_ID in pids
        record = dl.read(PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        assert record.removal_activity == REMOVE_ID
        assert not refreshed.is_active_participant(record)

    @pytest.mark.spec("CM-19-002")
    def test_keeps_the_actor_participant_index_entry(
        self, bridge, dl, case, participant
    ) -> None:
        """Inverted from the index-clearing pin: the index entry stays."""
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        self._run(bridge)

        refreshed = dl.read(CASE_ID)
        assert refreshed is not None
        assert refreshed.actor_participant_index[COORDINATOR_ID] == (
            PARTICIPANT_ID
        )

    @pytest.mark.spec("CM-31-001")
    def test_a_second_removal_keeps_the_first_fact(
        self, bridge, dl, case, participant
    ) -> None:
        participant.removal_activity = "https://example.org/activities/first"
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        assert self._run(bridge).status == Status.SUCCESS

        record = dl.read(PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        assert record.removal_activity == (
            "https://example.org/activities/first"
        )

    def test_fails_when_participant_not_on_the_case(
        self, bridge, dl, case, participant
    ) -> None:
        """Regime 1: the guards found it, so its absence is a fault."""
        dl.create(case)
        dl.create(participant)

        assert self._run(bridge).status == Status.FAILURE

    def test_fails_when_case_not_found(self, bridge, dl) -> None:
        """FAILURE when case is missing from DataLayer."""
        result = self._run(bridge, case_id="https://example.org/cases/missing")
        assert result.status == Status.FAILURE


class TestReinstateCaseParticipantReceivedNode:
    """Reinstatement clears the removal fact and nothing else (CM-31-011)."""

    def _run(self, bridge, case_id: str = CASE_ID):
        tree = ReinstateCaseParticipantReceivedNode(
            participant_id=PARTICIPANT_ID, case_id=case_id
        )
        return bridge.execute_with_setup(tree=tree, actor_id=ACTOR_ID)

    @pytest.mark.spec("CM-31-011")
    def test_clears_the_removal_fact(
        self, bridge, dl, case, participant
    ) -> None:
        participant.removal_activity = REMOVE_ID
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        assert self._run(bridge).status == Status.SUCCESS

        record = dl.read(PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        assert record.removal_activity is None
        assert record.joined
        refreshed = dl.read(CASE_ID)
        assert isinstance(refreshed, VulnerabilityCase)
        assert refreshed.is_active_participant(record)

    @pytest.mark.spec("CM-31-011")
    def test_a_participant_that_is_not_removed_is_unchanged(
        self, bridge, dl, case, participant
    ) -> None:
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        assert self._run(bridge).status == Status.SUCCESS

        record = dl.read(PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        assert record.removal_activity is None

    def test_fails_when_participant_not_on_the_case(
        self, bridge, dl, case, participant
    ) -> None:
        """Regime 1: the guards found it, so its absence is a fault."""
        dl.create(case)
        dl.create(participant)

        assert self._run(bridge).status == Status.FAILURE


class TestReinstatementGuards:
    """``Add`` only reinstates: each guard refuses a request to seat (CM-31-011)."""

    @staticmethod
    def _run(bridge, node):
        return bridge.execute_with_setup(tree=node, actor_id=ACTOR_ID)

    @pytest.mark.spec("CM-31-011")
    def test_is_removed_guard_refuses_a_participant_that_is_not_removed(
        self, bridge, dl, case, participant
    ) -> None:
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        node = ParticipantIsRemovedNode(
            participant_id=PARTICIPANT_ID,
            case_id=CASE_ID,
            move="reinstatement",
        )

        assert self._run(bridge, node).status == Status.FAILURE
        assert "reinstatement REFUSED (CM-31-011)" in node.feedback_message

    @pytest.mark.spec("CM-31-011")
    def test_is_removed_guard_admits_a_removed_participant(
        self, bridge, dl, case, participant
    ) -> None:
        participant.removal_activity = REMOVE_ID
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        node = ParticipantIsRemovedNode(
            participant_id=PARTICIPANT_ID,
            case_id=CASE_ID,
            move="reinstatement",
        )

        assert self._run(bridge, node).status == Status.SUCCESS

    @pytest.mark.spec("CM-31-011")
    def test_has_joined_guard_refuses_an_invitee_that_never_joined(
        self, bridge, dl, case
    ) -> None:
        invitee = as_CaseParticipant(
            id_=PARTICIPANT_ID,
            attributed_to=COORDINATOR_ID,
            context=CASE_ID,
            joined=False,
        )
        case.add_participant(invitee)
        dl.create(case)
        dl.create(invitee)
        node = ParticipantHasJoinedNode(
            participant_id=PARTICIPANT_ID,
            case_id=CASE_ID,
            move="reinstatement",
        )

        assert self._run(bridge, node).status == Status.FAILURE
        assert "never joined" in node.feedback_message

    @pytest.mark.spec("CM-31-011")
    def test_names_guard_refuses_a_record_off_the_roster(
        self, bridge, dl, case, participant
    ) -> None:
        dl.create(case)
        dl.create(participant)
        node = RemovalNamesCaseParticipantNode(
            participant_id=PARTICIPANT_ID,
            case_id=CASE_ID,
            move="reinstatement",
        )

        assert self._run(bridge, node).status == Status.FAILURE
        assert "reinstatement REFUSED" in node.feedback_message
