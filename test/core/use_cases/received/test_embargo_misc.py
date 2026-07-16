#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for AnnounceEmbargoEvent (no-op) and embargo consent reset (#609 regression)."""

import logging
from typing import cast
from unittest.mock import MagicMock

from vultron.core.states.em import EM
from vultron.core.use_cases.received.embargo import (
    AnnounceEmbargoEventToCaseReceivedUseCase,
    RemoveEmbargoEventFromCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    announce_embargo_activity,
    remove_embargo_from_case_activity,
)


class TestAnnounceEmbargoEventToCaseReceivedUseCase:
    """Tests for AnnounceEmbargoEventToCaseReceivedUseCase (no-op receiver)."""

    def test_announce_embargo_is_noop(self, make_payload):
        """execute() is a no-op: EM state and active_embargo are unchanged."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = SqliteDataLayer("sqlite:///:memory:")
        case = VulnerabilityCase(
            id_="https://example.org/cases/case_aem1",
            name="Announce Embargo No-Op Test",
        )
        embargo = EmbargoEvent(
            id_="https://example.org/cases/case_aem1/embargo_events/e1",
            context=case.id_,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        dl.create(case)

        activity = announce_embargo_activity(
            embargo=embargo,
            context=case,
            actor="https://example.org/users/vendor",
        )
        event = make_payload(activity)

        AnnounceEmbargoEventToCaseReceivedUseCase(dl, event).execute()

        updated = cast(VulnerabilityCase, dl.read(case.id_))
        assert updated is not None
        # State is UNCHANGED — Announce is not the ET message
        assert updated.current_status.em_state == EM.ACTIVE
        assert updated.active_embargo is not None

    def test_announce_embargo_logs_info(self, make_payload, caplog):
        """execute() logs receipt at INFO level."""
        dl = MagicMock()
        mock_event = MagicMock()
        mock_event.activity_id = "https://example.org/activities/ann1"

        with caplog.at_level(logging.INFO):
            AnnounceEmbargoEventToCaseReceivedUseCase(dl, mock_event).execute()

        assert any(
            "no receiver-side state change required" in r.message
            for r in caplog.records
        )


class TestResetEmbargoConsentWithInlineParticipants:
    """Regression tests for #609: _reset_case_participant_embargo_consent
    must tolerate inline CaseParticipant objects in case.case_participants,
    not just plain string IDs.
    """

    def test_remove_active_embargo_with_inline_participant_no_type_error(
        self, make_payload
    ):
        """remove_embargo_from_case must not raise TypeError when
        case.case_participants holds inline CaseParticipant objects
        (as stored on receiver side after fixes #572/#573).

        Regression test for #609.
        """
        import py_trees
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_609_inline"
        participant_id = f"{case_id}/participants/p1"

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Build a participant and store it — it also appears inline in case
        participant = CaseParticipant(
            id_=participant_id,
            context=case_id,
            attributed_to=actor_id,
        )
        # Simulate receiver-side: participant's consent state is SIGNATORY
        participant.embargo_consent_state = PEC.SIGNATORY
        dl.create(participant)

        embargo = EmbargoEvent(
            id_=f"{case_id}/embargo_events/e1",
            context=case_id,
        )
        dl.create(embargo)

        # Store inline CaseParticipant object (not string ID) in
        # case_participants — this is the condition that caused #609.
        case = VulnerabilityCase(
            id_=case_id,
            name="Inline Participant Regression Test",
            attributed_to=actor_id,
        )
        case.active_embargo = embargo.id_
        case.current_status.em_state = EM.ACTIVE
        case.case_participants.append(participant)  # inline object, not str
        case.actor_participant_index[actor_id] = participant_id
        dl.create(case)

        activity = remove_embargo_from_case_activity(
            embargo,
            origin=case,
            actor=actor_id,
        )
        event = make_payload(activity, receiving_actor_id=actor_id)

        # Must not raise TypeError
        RemoveEmbargoEventFromCaseReceivedUseCase(dl, event).execute()

        updated = cast(VulnerabilityCase, dl.read(case_id))
        assert updated is not None
        assert updated.active_embargo is None
        assert updated.current_status.em_state == EM.EXITED

    def test_reset_consent_with_inline_participant_resets_state(self):
        """_reset_case_participant_embargo_consent resets consent state even
        when case_participants entries are inline wire-layer CaseParticipant
        objects (not string IDs).

        Regression test for #609.
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.protocols import is_case_model
        from vultron.core.states.participant_embargo_consent import PEC
        from vultron.core.use_cases._helpers import (
            reset_case_participant_embargo_consent as _reset_case_participant_embargo_consent,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/case_609_reset"
        participant_id = f"{case_id}/participants/p1"

        dl = SqliteDataLayer("sqlite:///:memory:")

        # Wire-layer CaseParticipant with non-default consent state.
        # Stored in the DataLayer separately so dl.read(participant_id) works.
        participant = CaseParticipant(
            id_=participant_id,
            context=case_id,
            attributed_to=actor_id,
        )
        participant.embargo_consent_state = PEC.SIGNATORY.value
        dl.create(participant)

        # Inline wire-layer object in case_participants — this is the condition
        # that caused #609 on the receiver side after fixes #572/#573.
        case = VulnerabilityCase(
            id_=case_id,
            name="Reset Consent Inline",
        )
        case.case_participants.append(participant)
        dl.create(case)

        assert is_case_model(
            case
        ), "VulnerabilityCase should satisfy CaseModel"

        # Must not raise TypeError
        _reset_case_participant_embargo_consent(dl, case)

        updated_participant = dl.read(participant_id)
        assert updated_participant is not None
        assert (
            getattr(updated_participant, "embargo_consent_state", None)
            == PEC.NO_EMBARGO.value
        )
