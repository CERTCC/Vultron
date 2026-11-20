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

"""Tests for the Case Owner's removal and reinstatement BT leaf nodes."""

from types import SimpleNamespace

import pytest
from py_trees.common import Status

from test.support.act_runner import run_tree
from test.support.objects import make
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.case_participant_received import (
    NamedParticipantIsNotProtectedNode,
    RecordParticipantRemovalNode,
)
from vultron.core.behaviors.case.nodes.participant_reinstatement import (
    ClearParticipantRemovalNode,
    ParticipantHasJoinedNode,
    ParticipantIsRemovedNode,
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
    return make(
        VulnerabilityCase,
        id_=CASE_ID,
        name="CP Node Test Case",
        attributed_to=ACTOR_ID,
    )


@pytest.fixture
def participant(case):
    return make(
        as_CaseParticipant,
        id_=PARTICIPANT_ID,
        attributed_to=COORDINATOR_ID,
        context=case.id_,
    )


REMOVE_ID = "https://example.org/activities/remove-coord"


def _run_move(bridge, node, case_id: str = CASE_ID, **keys):
    """Run *node* with the case and the named actor seeded (BTND-01-008)."""
    return run_tree(
        bridge,
        tree=node,
        actor_id=ACTOR_ID,
        case_id=case_id,
        participant_actor_id=COORDINATOR_ID,
        **keys,
    )


class TestRecordParticipantRemovalNode:
    """Removal sets the fact and keeps the record (CM-31-001, CM-31-015, ADR-0116)."""

    def _run(self, bridge, case_id: str = CASE_ID):
        # The removal fact is the received act's id, read from ``/activity``.
        return _run_move(
            bridge,
            RecordParticipantRemovalNode(),
            case_id,
            activity=SimpleNamespace(activity_id=REMOVE_ID),
        )

    @pytest.mark.spec("CM-31-015")
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


class TestClearParticipantRemovalNode:
    """Reinstatement clears the removal fact and nothing else (CM-31-034)."""

    def _run(self, bridge, case_id: str = CASE_ID):
        return _run_move(bridge, ClearParticipantRemovalNode(), case_id)

    @pytest.mark.spec("CM-31-011")
    @pytest.mark.spec("CM-31-034")
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
    """A reinstatement only reinstates: each guard refuses a request to seat
    (CM-31-036)."""

    @staticmethod
    def _run(bridge, node):
        return _run_move(bridge, node)

    @pytest.mark.spec("CM-31-036")
    def test_is_removed_guard_refuses_a_participant_that_is_not_removed(
        self, bridge, dl, case, participant
    ) -> None:
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        node = ParticipantIsRemovedNode(move="reinstatement")

        assert self._run(bridge, node).status == Status.FAILURE
        assert "reinstatement REFUSED (CM-31-036)" in node.feedback_message

    @pytest.mark.spec("CM-31-011")
    def test_is_removed_guard_admits_a_removed_participant(
        self, bridge, dl, case, participant
    ) -> None:
        participant.removal_activity = REMOVE_ID
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)
        node = ParticipantIsRemovedNode(move="reinstatement")

        assert self._run(bridge, node).status == Status.SUCCESS

    @pytest.mark.spec("CM-31-036")
    def test_has_joined_guard_refuses_an_invitee_that_never_joined(
        self, bridge, dl, case
    ) -> None:
        invitee = make(
            as_CaseParticipant,
            id_=PARTICIPANT_ID,
            attributed_to=COORDINATOR_ID,
            context=CASE_ID,
            joined=False,
        )
        case.add_participant(invitee)
        dl.create(case)
        dl.create(invitee)
        node = ParticipantHasJoinedNode(move="reinstatement")

        assert self._run(bridge, node).status == Status.FAILURE
        assert "never joined" in node.feedback_message

    @pytest.mark.spec("CM-31-036")
    def test_guard_refuses_an_actor_off_the_roster(
        self, bridge, dl, case, participant
    ) -> None:
        dl.create(case)
        dl.create(participant)
        node = ParticipantIsRemovedNode(move="reinstatement")

        assert self._run(bridge, node).status == Status.FAILURE
        assert "is not a participant" in node.feedback_message
        assert "reinstatement REFUSED" in node.feedback_message

    @pytest.mark.spec("CM-31-004")
    @pytest.mark.spec("CM-31-036")
    @pytest.mark.parametrize("move", ["removal", "reinstatement"])
    @pytest.mark.parametrize("role", ["CASE_MANAGER", "CASE_OWNER"])
    def test_protected_guard_refuses_the_manager_and_the_owner(
        self, bridge, dl, case, move, role
    ) -> None:
        from vultron.enums.roles import CVDRole

        protected = make(
            as_CaseParticipant,
            id_=PARTICIPANT_ID,
            attributed_to=COORDINATOR_ID,
            context=CASE_ID,
            case_roles=[CVDRole[role]],
        )
        case.add_participant(protected)
        dl.create(case)
        dl.create(protected)
        node = NamedParticipantIsNotProtectedNode(move=move)

        assert self._run(bridge, node).status == Status.FAILURE
        assert role in node.feedback_message
        assert f"{move} REFUSED" in node.feedback_message


class TestEffectAndAnnounceFailures:
    """The effect and the shared Announce emit fail whole, sending nothing."""

    @staticmethod
    def _seed(dl, case, participant):
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

    @pytest.mark.spec("CM-31-001")
    def test_removal_with_no_received_act_fails_before_writing(
        self, bridge, dl, case, participant
    ) -> None:
        self._seed(dl, case, participant)

        result = _run_move(bridge, RecordParticipantRemovalNode())

        assert result.status == Status.FAILURE
        record = dl.read(PARTICIPANT_ID)
        assert isinstance(record, CaseParticipant)
        assert not record.removed

    @pytest.mark.spec("CM-31-006")
    def test_announce_with_no_received_act_sends_nothing(
        self, dl, case, participant
    ) -> None:
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.nodes.case_participant_received import (
            AnnounceParticipantMoveNode,
        )

        self._seed(dl, case, participant)
        bridge = BTBridge(
            datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
        )

        result = _run_move(bridge, AnnounceParticipantMoveNode())

        assert result.status == Status.FAILURE
        assert dl.outbox_list() == []

    @pytest.mark.spec("CM-31-006")
    def test_announce_naming_no_recipient_sends_nothing(
        self, dl, case, participant
    ) -> None:
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.case.nodes.announce_admitted_act import (
            EmitAnnounceAdmittedActNode,
        )

        class _NoOne(EmitAnnounceAdmittedActNode):
            def _recipients(self) -> list[str]:
                return []

        self._seed(dl, case, participant)
        bridge = BTBridge(
            datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
        )

        result = run_tree(
            bridge,
            tree=_NoOne(),
            actor_id=ACTOR_ID,
            case_id=CASE_ID,
            activity=SimpleNamespace(activity_id=REMOVE_ID),
        )

        assert result.status == Status.FAILURE
        assert "names no recipient" in (result.feedback_message or "")
        assert dl.outbox_list() == []
