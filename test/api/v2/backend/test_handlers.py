"""
Unit tests for handler functions and the verify_semantics decorator.

Tests ensure that:
- HP-02-001: All handlers have @verify_semantics decorator
- HP-02-002: Decorator validates semantic type matches
- HP-02-003: Decorator raises errors for mismatched semantics
- HP-02-004: Decorator raises errors for missing semantics
"""

from unittest.mock import MagicMock

import pytest

from vultron.api.v2.backend import handlers
from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Create
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)
from vultron.core.models.events import InboundPayload, MessageSemantics
from vultron.types import DispatchActivity


def _make_payload(activity):
    """Wrap a raw activity in InboundPayload for use in tests."""
    return InboundPayload(
        activity_id=getattr(activity, "as_id", "") or "",
        actor_id=(
            str(activity.actor) if getattr(activity, "actor", None) else ""
        ),
        raw_activity=activity,
    )


class TestVerifySemanticsDecorator:
    """Test the verify_semantics decorator validation logic."""

    def test_decorator_validates_matching_semantics(self):
        """Test that decorator allows through activities with matching semantics."""

        # Create a test handler decorated with verify_semantics
        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity, dl=None) -> str:
            return "success"

        # Create a mock DispatchActivity with matching semantics
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT

        # Create proper as_Create activity with VulnerabilityReport object
        report = VulnerabilityReport(
            name="TEST-001", content="Test vulnerability report"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=report
        )
        mock_activity.payload = _make_payload(create_activity)

        # Should execute successfully
        result = test_handler(mock_activity, None)
        assert result == "success"

    def test_decorator_raises_error_for_missing_semantic_type(self):
        """Test that decorator raises error when semantic_type is None."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity, dl=None) -> str:
            return "success"

        # Create mock with None semantic_type
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = None

        # Should raise VultronApiHandlerMissingSemanticError
        with pytest.raises(VultronApiHandlerMissingSemanticError):
            test_handler(mock_activity, None)

    def test_decorator_raises_error_for_semantic_mismatch(self):
        """Test that decorator raises error when semantic types don't match."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity, dl=None) -> str:
            return "success"

        # Create mock with wrong semantic_type (handler expects CREATE_REPORT)
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_CASE

        # Should raise VultronApiHandlerSemanticMismatchError
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            test_handler(mock_activity, None)

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves the wrapped function's __name__."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity, dl=None) -> str:
            return "success"

        # Decorator should preserve function name via @wraps
        assert test_handler.__name__ == "test_handler"


class TestHandlerDecoratorPresence:
    """Test that all handler functions have the @verify_semantics decorator."""

    def test_create_report_has_decorator(self):
        """Test create_report handler has verify_semantics decorator."""
        # Function should be callable (not None) - this was the bug!
        assert callable(handlers.create_report)
        assert handlers.create_report.__name__ == "create_report"

    def test_all_handlers_are_callable(self):
        """Test that all 47 handler functions are callable (regression test for decorator bug)."""
        handler_list = [
            handlers.create_report,
            handlers.submit_report,
            handlers.validate_report,
            handlers.invalidate_report,
            handlers.ack_report,
            handlers.close_report,
            handlers.create_case,
            handlers.add_report_to_case,
            handlers.suggest_actor_to_case,
            handlers.accept_suggest_actor_to_case,
            handlers.reject_suggest_actor_to_case,
            handlers.offer_case_ownership_transfer,
            handlers.accept_case_ownership_transfer,
            handlers.reject_case_ownership_transfer,
            handlers.invite_actor_to_case,
            handlers.accept_invite_actor_to_case,
            handlers.reject_invite_actor_to_case,
            handlers.create_embargo_event,
            handlers.add_embargo_event_to_case,
            handlers.remove_embargo_event_from_case,
            handlers.announce_embargo_event_to_case,
            handlers.invite_to_embargo_on_case,
            handlers.accept_invite_to_embargo_on_case,
            handlers.reject_invite_to_embargo_on_case,
            handlers.close_case,
            handlers.create_case_participant,
            handlers.add_case_participant_to_case,
            handlers.remove_case_participant_from_case,
            handlers.create_note,
            handlers.add_note_to_case,
            handlers.remove_note_from_case,
            handlers.create_case_status,
            handlers.add_case_status_to_case,
            handlers.create_participant_status,
            handlers.add_participant_status_to_participant,
            handlers.unknown,
        ]

        # Before the bug fix, missing 'return wrapper' made all these None
        for handler in handler_list:
            assert callable(handler), f"{handler} is not callable"


class TestHandlerExecution:
    """Test that handlers execute with valid semantics."""

    def test_create_report_executes_with_valid_semantics(self):
        """Test create_report handler executes when semantics match."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT

        # Create proper as_Create activity with VulnerabilityReport object
        report = VulnerabilityReport(
            name="TEST-002", content="Test vulnerability report"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=report
        )
        mock_activity.payload = _make_payload(create_activity)

        # Should execute without raising
        mock_dl = MagicMock()
        result = handlers.create_report(mock_activity, mock_dl)
        # Current stub implementation returns None
        assert result is None

    def test_create_case_executes_with_valid_semantics(self):
        """Test create_case handler executes when semantics match."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_CASE

        # Create proper as_Create activity with VulnerabilityCase object
        case = VulnerabilityCase(
            name="TEST-CASE-002", content="Test vulnerability case"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=case
        )
        mock_activity.payload = _make_payload(create_activity)

        # Should execute without raising
        mock_dl = MagicMock()
        result = handlers.create_case(mock_activity, mock_dl)
        assert result is None

    def test_handler_rejects_wrong_semantic_type(self):
        """Test handler rejects activity with wrong semantic type."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_CASE

        # Should raise semantic mismatch error (handler expects CREATE_REPORT)
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            handlers.create_report(mock_activity, None)


class TestInviteActorHandlers:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    reject_invite_actor_to_case, and remove_case_participant_from_case."""

    def test_invite_actor_to_case_stores_invite(self, monkeypatch):
        """invite_actor_to_case persists the Invite activity to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import RmInviteToCase

        dl = TinyDbDataLayer(db_path=None)

        invite = RmInviteToCase(
            id="https://example.org/cases/case1/invitations/1",
            actor="https://example.org/users/owner",
            object="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.INVITE_ACTOR_TO_CASE
        mock_dispatchable.payload = _make_payload(invite)

        handlers.invite_actor_to_case(mock_dispatchable, dl)

        stored = dl.get(invite.as_type.value, invite.as_id)
        assert stored is not None

    def test_invite_actor_to_case_idempotent(self, monkeypatch):
        """invite_actor_to_case skips storing a duplicate Invite."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import RmInviteToCase

        dl = TinyDbDataLayer(db_path=None)

        invite = RmInviteToCase(
            id="https://example.org/cases/case1/invitations/2",
            actor="https://example.org/users/owner",
            object="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.INVITE_ACTOR_TO_CASE
        mock_dispatchable.payload = _make_payload(invite)

        handlers.invite_actor_to_case(mock_dispatchable, dl)
        handlers.invite_actor_to_case(
            mock_dispatchable, dl
        )  # second call is no-op

        stored = dl.get(invite.as_type.value, invite.as_id)
        assert stored is not None

    def test_reject_invite_actor_to_case_logs_rejection(self):
        """reject_invite_actor_to_case logs without raising."""
        from vultron.wire.as2.vocab.activities.case import (
            RmInviteToCase,
            RmRejectInviteToCase,
        )

        invite = RmInviteToCase(
            id="https://example.org/cases/case1/invitations/3",
            actor="https://example.org/users/owner",
            object="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )
        reject = RmRejectInviteToCase(
            actor="https://example.org/users/coordinator",
            object=invite,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(reject)

        result = handlers.reject_invite_actor_to_case(
            mock_dispatchable, MagicMock()
        )
        assert result is None

    def test_remove_case_participant_from_case(self, monkeypatch):
        """remove_case_participant_from_case removes the participant from case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case2",
            name="TEST-REMOVE",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/case2/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.as_id,
        )
        case.case_participants.append(participant.as_id)
        dl.create(case)
        dl.create(participant)

        # Pass objects directly so rehydrate returns them without a DB lookup
        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object=participant,
            target=case,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
        )
        mock_dispatchable.payload = _make_payload(remove_activity)

        handlers.remove_case_participant_from_case(mock_dispatchable, dl)

        assert participant.as_id not in [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]

    def test_remove_case_participant_idempotent(self, monkeypatch):
        """remove_case_participant_from_case is idempotent when participant absent."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case3",
            name="TEST-REMOVE-IDEMPOTENT",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/case3/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.as_id,
        )
        # participant NOT added to case
        dl.create(case)
        dl.create(participant)

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object=participant,
            target=case,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
        )
        mock_dispatchable.payload = _make_payload(remove_activity)

        result = handlers.remove_case_participant_from_case(
            mock_dispatchable, dl
        )
        assert result is None

    def test_add_case_participant_updates_index(self, monkeypatch):
        """add_case_participant_to_case updates actor_participant_index (SC-PRE-2)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        actor_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id="https://example.org/cases/caseAP1",
            name="TEST-ADD-INDEX",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/caseAP1/participants/coord",
            attributed_to=actor_id,
            context=case.as_id,
        )
        dl.create(case)
        dl.create(participant)

        add_activity = as_Add(
            actor="https://example.org/users/owner",
            object=participant,
            target=case,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(add_activity)

        handlers.add_case_participant_to_case(mock_dispatchable, dl)

        assert actor_id in case.actor_participant_index
        assert case.actor_participant_index[actor_id] == participant.as_id

    def test_remove_case_participant_clears_index(self, monkeypatch):
        """remove_case_participant_from_case clears actor_participant_index (SC-PRE-2)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        actor_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id="https://example.org/cases/caseRM1",
            name="TEST-REMOVE-INDEX",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/caseRM1/participants/coord",
            attributed_to=actor_id,
            context=case.as_id,
        )
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        assert actor_id in case.actor_participant_index

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object=participant,
            target=case,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE
        )
        mock_dispatchable.payload = _make_payload(remove_activity)

        handlers.remove_case_participant_from_case(mock_dispatchable, dl)

        assert actor_id not in case.actor_participant_index

    def test_accept_invite_actor_to_case_adds_participant(self, monkeypatch):
        """accept_invite_actor_to_case creates a CaseParticipant and adds them to the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCase,
            RmInviteToCase,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Actor(id=invitee_id)
        case = VulnerabilityCase(
            id="https://example.org/cases/caseIA1",
            name="TEST-ACCEPT-INVITE",
        )
        invite = RmInviteToCase(
            id="https://example.org/cases/caseIA1/invitations/1",
            actor="https://example.org/users/owner",
            object=invitee,
            target=case,
        )
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCase(
            actor=invitee_id,
            object=invite,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        handlers.accept_invite_actor_to_case(mock_dispatchable, dl)

        assert invitee_id in case.actor_participant_index

    def test_accept_invite_actor_to_case_records_active_embargo(
        self, monkeypatch
    ):
        """accept_invite_actor_to_case records the active embargo ID on the new participant (CM-10-001, CM-10-003)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCase,
            RmInviteToCase,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Actor(id=invitee_id)
        embargo = EmbargoEvent(
            id="https://example.org/cases/caseIA2/embargo_events/e1",
            content="Active embargo",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/caseIA2",
            name="TEST-ACCEPT-INVITE-EMBARGO",
        )
        case.active_embargo = embargo.as_id
        invite = RmInviteToCase(
            id="https://example.org/cases/caseIA2/invitations/1",
            actor="https://example.org/users/owner",
            object=invitee,
            target=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(invite)

        accept = RmAcceptInviteToCase(
            actor=invitee_id,
            object=invite,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        handlers.accept_invite_actor_to_case(mock_dispatchable, dl)

        participant_id = case.actor_participant_index.get(invitee_id)
        assert participant_id is not None
        participant_obj = dl.get(id_=participant_id)
        assert participant_obj is not None
        assert embargo.as_id in participant_obj.accepted_embargo_ids

    def test_accept_invite_actor_to_case_records_case_event(self, monkeypatch):
        """accept_invite_actor_to_case appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            RmAcceptInviteToCase,
            RmInviteToCase,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        invitee_id = "https://example.org/users/coordinator"
        invitee = as_Actor(id=invitee_id)
        case = VulnerabilityCase(
            id="https://example.org/cases/caseIA3",
            name="TEST-ACCEPT-INVITE-EVENT",
        )
        invite = RmInviteToCase(
            id="https://example.org/cases/caseIA3/invitations/1",
            actor="https://example.org/users/owner",
            object=invitee,
            target=case,
        )
        dl.create(case)
        dl.create(invite)

        accept = RmAcceptInviteToCase(
            actor=invitee_id,
            object=invite,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        assert len(case.events) == 0

        handlers.accept_invite_actor_to_case(mock_dispatchable, dl)

        assert len(case.events) >= 1
        event_types = [e.event_type for e in case.events]
        assert "participant_joined" in event_types


class TestEmbargoHandlers:
    """Tests for embargo management handlers."""

    def test_create_embargo_event_stores_event(self, monkeypatch):
        """create_embargo_event persists the EmbargoEvent to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cem1",
            name="Create Embargo Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_cem1/embargo_events/embargo1",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_EMBARGO_EVENT
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_embargo_event(mock_dispatchable, dl)

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_create_embargo_event_idempotent(self, monkeypatch):
        """create_embargo_event skips storing a duplicate EmbargoEvent."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cem2",
            name="Create Embargo Idempotent",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_cem2/embargo_events/embargo2",
            content="Proposed embargo",
        )
        activity = as_Create(
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_EMBARGO_EVENT
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_embargo_event(mock_dispatchable, dl)
        handlers.create_embargo_event(
            mock_dispatchable, dl
        )  # second call no-op

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_add_embargo_event_to_case_activates_embargo(self, monkeypatch):
        """add_embargo_event_to_case sets the active embargo on the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import AddEmbargoToCase
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.bt.embargo_management.states import EM

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em1",
            name="EM Test Case",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em1/embargo_events/e1",
            content="Embargo test",
        )
        dl.create(case)
        dl.create(embargo)

        activity = AddEmbargoToCase(
            actor="https://example.org/users/vendor",
            object=embargo,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ADD_EMBARGO_EVENT_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.add_embargo_event_to_case(mock_dispatchable, dl)

        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_invite_to_embargo_on_case_stores_proposal(self, monkeypatch):
        """invite_to_embargo_on_case persists the EmProposeEmbargo activity."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import EmProposeEmbargo
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)

        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em2/embargo_events/e2",
            content="Proposed embargo",
        )
        proposal = EmProposeEmbargo(
            id="https://example.org/cases/case_em2/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context="https://example.org/cases/case_em2",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.INVITE_TO_EMBARGO_ON_CASE
        )
        mock_dispatchable.payload = _make_payload(proposal)

        handlers.invite_to_embargo_on_case(mock_dispatchable, dl)

        stored = dl.get(proposal.as_type.value, proposal.as_id)
        assert stored is not None

    def test_accept_invite_to_embargo_on_case_activates_embargo(
        self, monkeypatch
    ):
        """accept_invite_to_embargo_on_case activates the embargo on the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargo,
            EmProposeEmbargo,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.bt.embargo_management.states import EM

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em3",
            name="EM Accept Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em3/embargo_events/e3",
            content="Embargo",
        )
        # Use inline objects (not string IDs) so rehydration skips DataLayer lookup
        proposal = EmProposeEmbargo(
            id="https://example.org/cases/case_em3/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargo(
            actor="https://example.org/users/coordinator",
            object=proposal,
            context=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        handlers.accept_invite_to_embargo_on_case(mock_dispatchable, dl)

        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_accept_invite_to_embargo_records_embargo_on_participant(
        self, monkeypatch
    ):
        """accept_invite_to_embargo_on_case records embargo ID in participant.accepted_embargo_ids (CM-10-002, CM-10-003)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargo,
            EmProposeEmbargo,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        coordinator_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id="https://example.org/cases/case_em5",
            name="EM Accept Participant Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em5/embargo_events/e5",
            content="Embargo",
        )
        participant = CaseParticipant(
            id="https://example.org/cases/case_em5/participants/coord",
            attributed_to=coordinator_id,
            context=case.as_id,
        )
        case.add_participant(participant)
        proposal = EmProposeEmbargo(
            id="https://example.org/cases/case_em5/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(participant)
        dl.create(proposal)

        accept = EmAcceptEmbargo(
            actor=coordinator_id,
            object=proposal,
            context=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        handlers.accept_invite_to_embargo_on_case(mock_dispatchable, dl)

        updated_participant = dl.get(id_=participant.as_id)
        assert updated_participant is not None
        assert embargo.as_id in updated_participant.accepted_embargo_ids

    def test_accept_invite_to_embargo_records_case_event(self, monkeypatch):
        """accept_invite_to_embargo_on_case appends a trusted-timestamp event to case.events (CM-02-009)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.embargo import (
            EmAcceptEmbargo,
            EmProposeEmbargo,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_em6",
            name="EM Accept Event Test",
        )
        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em6/embargo_events/e6",
            content="Embargo",
        )
        proposal = EmProposeEmbargo(
            id="https://example.org/cases/case_em6/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context=case,
        )
        dl.create(case)
        dl.create(embargo)
        dl.create(proposal)

        accept = EmAcceptEmbargo(
            actor="https://example.org/users/coordinator",
            object=proposal,
            context=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE
        )
        mock_dispatchable.payload = _make_payload(accept)

        assert len(case.events) == 0

        handlers.accept_invite_to_embargo_on_case(mock_dispatchable, dl)

        assert len(case.events) >= 1
        event_types = [e.event_type for e in case.events]
        assert "embargo_accepted" in event_types

    def test_reject_invite_to_embargo_on_case_logs_rejection(self):
        """reject_invite_to_embargo_on_case logs without raising."""
        from vultron.wire.as2.vocab.activities.embargo import (
            EmProposeEmbargo,
            EmRejectEmbargo,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        embargo = EmbargoEvent(
            id="https://example.org/cases/case_em4/embargo_events/e4",
            content="Embargo",
        )
        proposal = EmProposeEmbargo(
            id="https://example.org/cases/case_em4/embargo_proposals/1",
            actor="https://example.org/users/vendor",
            object=embargo,
            context="https://example.org/cases/case_em4",
        )
        reject = EmRejectEmbargo(
            actor="https://example.org/users/coordinator",
            object=proposal,
            context="https://example.org/cases/case_em4",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE
        )
        mock_dispatchable.payload = _make_payload(reject)

        result = handlers.reject_invite_to_embargo_on_case(
            mock_dispatchable, MagicMock()
        )
        assert result is None


class TestNoteHandlers:
    """Tests for note management handlers."""

    def test_create_note_stores_note(self, monkeypatch):
        """create_note persists the Note to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note

        dl = TinyDbDataLayer(db_path=None)

        note = as_Note(
            id="https://example.org/notes/note1",
            content="Test note content",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object=note,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_NOTE
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_note(mock_dispatchable, dl)

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_create_note_idempotent(self, monkeypatch):
        """create_note skips storing a duplicate Note."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note

        dl = TinyDbDataLayer(db_path=None)

        note = as_Note(
            id="https://example.org/notes/note2",
            content="Duplicate note",
        )
        activity = as_Create(
            actor="https://example.org/users/finder",
            object=note,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_NOTE
        mock_dispatchable.payload = _make_payload(activity)

        dl.create(note)
        handlers.create_note(mock_dispatchable, dl)

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_add_note_to_case_appends_note(self, monkeypatch):
        """add_note_to_case appends note ID to case.notes and persists."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import AddNoteToCase
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_n1",
            name="Note Case",
        )
        note = as_Note(
            id="https://example.org/notes/note3",
            content="A note",
        )
        dl.create(case)
        dl.create(note)

        activity = AddNoteToCase(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.ADD_NOTE_TO_CASE
        mock_dispatchable.payload = _make_payload(activity)

        handlers.add_note_to_case(mock_dispatchable, dl)

        assert note.as_id in case.notes

    def test_add_note_to_case_idempotent(self, monkeypatch):
        """add_note_to_case skips adding a note already in the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import AddNoteToCase
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note4",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n2",
            name="Note Case Idempotent",
            notes=[note.as_id],
        )
        dl.create(case)
        dl.create(note)

        activity = AddNoteToCase(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.ADD_NOTE_TO_CASE
        mock_dispatchable.payload = _make_payload(activity)

        handlers.add_note_to_case(mock_dispatchable, dl)

        assert case.notes.count(note.as_id) == 1

    def test_remove_note_from_case_removes_note(self, monkeypatch):
        """remove_note_from_case removes note ID from case.notes and persists."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note5",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n3",
            name="Remove Note Case",
            notes=[note.as_id],
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REMOVE_NOTE_FROM_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.remove_note_from_case(mock_dispatchable, dl)

        assert note.as_id not in case.notes

    def test_remove_note_from_case_idempotent(self, monkeypatch):
        """remove_note_from_case is idempotent when note not in case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.base.objects.object_types import as_Note
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        note = as_Note(
            id="https://example.org/notes/note6",
            content="A note",
        )
        case = VulnerabilityCase(
            id="https://example.org/cases/case_n4",
            name="Remove Note Idempotent",
        )
        dl.create(case)
        dl.create(note)

        activity = as_Remove(
            actor="https://example.org/users/finder",
            object=note,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REMOVE_NOTE_FROM_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        result = handlers.remove_note_from_case(mock_dispatchable, dl)
        assert result is None


class TestStatusHandlers:
    """Tests for case status and participant status handlers."""

    def test_create_case_status_stores_status(self, monkeypatch):
        """create_case_status persists the CaseStatus to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import CreateCaseStatus
        from vultron.wire.as2.vocab.objects.case_status import CaseStatus
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs1",
            name="Case Status Test",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs1/statuses/s1",
            context=case.as_id,
        )
        activity = CreateCaseStatus(
            actor="https://example.org/users/vendor",
            object=status,
            context=case.as_id,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_CASE_STATUS
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_case_status(mock_dispatchable, dl)

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_create_case_status_idempotent(self, monkeypatch):
        """create_case_status skips storing a duplicate CaseStatus."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import CreateCaseStatus
        from vultron.wire.as2.vocab.objects.case_status import CaseStatus
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs2",
            name="Case Status Idempotent",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs2/statuses/s2",
            context=case.as_id,
        )
        dl.create(status)

        activity = CreateCaseStatus(
            actor="https://example.org/users/vendor",
            object=status,
            context=case.as_id,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.CREATE_CASE_STATUS
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_case_status(mock_dispatchable, dl)

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_add_case_status_to_case_appends_status(self, monkeypatch):
        """add_case_status_to_case appends status ID to case.case_statuses."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import AddStatusToCase
        from vultron.wire.as2.vocab.objects.case_status import CaseStatus
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_cs3",
            name="Add Status Case",
        )
        status = CaseStatus(
            id="https://example.org/cases/case_cs3/statuses/s3",
            context=case.as_id,
        )
        dl.create(case)
        dl.create(status)

        activity = AddStatusToCase(
            actor="https://example.org/users/vendor",
            object=status,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ADD_CASE_STATUS_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.add_case_status_to_case(mock_dispatchable, dl)

        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_statuses
        ]
        assert status.as_id in status_ids

    def test_create_participant_status_stores_status(self, monkeypatch):
        """create_participant_status persists the ParticipantStatus."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case_participant import (
            CreateStatusForParticipant,
        )
        from vultron.wire.as2.vocab.objects.case_status import (
            ParticipantStatus,
        )

        dl = TinyDbDataLayer(db_path=None)

        pstatus = ParticipantStatus(
            id="https://example.org/cases/case_ps1/participants/p1/statuses/s1",
            context="https://example.org/cases/case_ps1",
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case_ps1 = VulnerabilityCase(
            id="https://example.org/cases/case_ps1",
            name="PS Case 1",
        )
        activity = CreateStatusForParticipant(
            actor="https://example.org/users/vendor",
            object=pstatus,
            context=case_ps1,
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.CREATE_PARTICIPANT_STATUS
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.create_participant_status(mock_dispatchable, dl)

        stored = dl.get(pstatus.as_type.value, pstatus.as_id)
        assert stored is not None

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch
    ):
        """add_participant_status_to_participant appends status to participant."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case_participant import (
            AddStatusToParticipant,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.case_status import (
            ParticipantStatus,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        participant = CaseParticipant(
            id="https://example.org/cases/case_ps2/participants/p2",
            context="https://example.org/cases/case_ps2",
            attributed_to="https://example.org/users/vendor",
        )
        pstatus = ParticipantStatus(
            id="https://example.org/cases/case_ps2/participants/p2/statuses/s2",
            context="https://example.org/cases/case_ps2",
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        case_ps2 = VulnerabilityCase(
            id="https://example.org/cases/case_ps2",
            name="PS Case 2",
        )
        dl.create(participant)
        dl.create(pstatus)

        activity = AddStatusToParticipant(
            actor="https://example.org/users/vendor",
            object=pstatus,
            target=participant,
            context=case_ps2,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.add_participant_status_to_participant(mock_dispatchable, dl)

        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_statuses
        ]
        assert pstatus.as_id in status_ids


class TestSuggestActorHandlers:
    """Tests for suggest_actor_to_case, accept/reject suggest_actor handlers."""

    def test_suggest_actor_to_case_persists_recommendation(self, monkeypatch):
        """suggest_actor_to_case persists the RecommendActor offer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.actor import RecommendActor
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id="https://example.org/cases/case_sa1",
            name="SA Case 1",
        )
        activity = RecommendActor(
            actor="https://example.org/users/finder",
            object=coordinator,
            target=case,
            to="https://example.org/users/vendor",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.SUGGEST_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.suggest_actor_to_case(mock_dispatchable, dl)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_suggest_actor_to_case_idempotent(self, monkeypatch):
        """suggest_actor_to_case is idempotent — second call is a no-op."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.actor import RecommendActor
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id="https://example.org/cases/case_sa2",
            name="SA Case 2",
        )
        activity = RecommendActor(
            actor="https://example.org/users/finder",
            object=coordinator,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.SUGGEST_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.suggest_actor_to_case(mock_dispatchable, dl)
        handlers.suggest_actor_to_case(mock_dispatchable, dl)

        # Second call should be a no-op; record is still present (not duplicated)
        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_accept_suggest_actor_to_case_persists_acceptance(
        self, monkeypatch
    ):
        """accept_suggest_actor_to_case persists the AcceptActorRecommendation."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.actor import (
            AcceptActorRecommendation,
            RecommendActor,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)

        coordinator = as_Actor(id="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id="https://example.org/cases/case_sa3",
            name="SA Case 3",
        )
        recommendation = RecommendActor(
            actor="https://example.org/users/finder",
            object=coordinator,
            target=case,
        )
        activity = AcceptActorRecommendation(
            actor="https://example.org/users/vendor",
            object=recommendation,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_SUGGEST_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.accept_suggest_actor_to_case(mock_dispatchable, dl)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_reject_suggest_actor_to_case_logs_rejection(
        self, monkeypatch, caplog
    ):
        """reject_suggest_actor_to_case logs rejection without state change."""
        import logging

        from vultron.wire.as2.vocab.activities.actor import (
            RecommendActor,
            RejectActorRecommendation,
        )
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor

        coordinator = as_Actor(id="https://example.org/users/coordinator")
        case = VulnerabilityCase(
            id="https://example.org/cases/case_sa4",
            name="SA Case 4",
        )
        recommendation = RecommendActor(
            actor="https://example.org/users/finder",
            object=coordinator,
            target=case,
        )
        activity = RejectActorRecommendation(
            actor="https://example.org/users/vendor",
            object=recommendation,
            target=case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REJECT_SUGGEST_ACTOR_TO_CASE
        )
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.INFO):
            handlers.reject_suggest_actor_to_case(
                mock_dispatchable, MagicMock()
            )

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestOwnershipTransferHandlers:
    """Tests for offer/accept/reject ownership transfer handlers."""

    def test_offer_case_ownership_transfer_persists_offer(self, monkeypatch):
        """offer_case_ownership_transfer persists the offer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            OfferCaseOwnershipTransfer,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            id="https://example.org/cases/case_ot1",
            name="OT Case 1",
        )
        activity = OfferCaseOwnershipTransfer(
            actor="https://example.org/users/vendor",
            object=case,
            target="https://example.org/users/coordinator",
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.offer_case_ownership_transfer(mock_dispatchable, dl)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, monkeypatch
    ):
        """accept_case_ownership_transfer updates case.attributed_to to new owner."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import (
            AcceptCaseOwnershipTransfer,
            OfferCaseOwnershipTransfer,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_ot2",
            name="OT Case 2",
            attributed_to="https://example.org/users/vendor",
        )
        dl.create(case)

        offer = OfferCaseOwnershipTransfer(
            id="https://example.org/activities/offer_ot2",
            actor="https://example.org/users/vendor",
            object=case,
            target="https://example.org/users/coordinator",
        )
        dl.create(offer)

        activity = AcceptCaseOwnershipTransfer(
            actor="https://example.org/users/coordinator",
            object=offer,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER
        )
        mock_dispatchable.payload = _make_payload(activity)

        handlers.accept_case_ownership_transfer(mock_dispatchable, dl)

        updated_record = dl.get(case.as_type.value, case.as_id)
        assert updated_record is not None
        data = updated_record.get("data_", updated_record)
        assert (
            data.get("attributed_to")
            == "https://example.org/users/coordinator"
        )

    def test_reject_case_ownership_transfer_logs_rejection(
        self, monkeypatch, caplog
    ):
        """reject_case_ownership_transfer logs rejection; ownership unchanged."""
        import logging

        from vultron.wire.as2.vocab.activities.case import (
            OfferCaseOwnershipTransfer,
            RejectCaseOwnershipTransfer,
        )

        case = VulnerabilityCase(
            id="https://example.org/cases/case_ot3",
            name="OT Case 3",
        )
        offer = OfferCaseOwnershipTransfer(
            id="https://example.org/activities/offer_ot3",
            actor="https://example.org/users/vendor",
            object=case,
            target="https://example.org/users/coordinator",
        )
        activity = RejectCaseOwnershipTransfer(
            actor="https://example.org/users/coordinator",
            object=offer,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = (
            MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER
        )
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.INFO):
            handlers.reject_case_ownership_transfer(
                mock_dispatchable, MagicMock()
            )

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestUpdateCaseHandler:
    """Tests for update_case handler."""

    def test_update_case_applies_scalar_updates(self, monkeypatch, caplog):
        """update_case applies name/summary/content updates from a full object."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc1",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated Name",
            content="New content",
            attributed_to=owner_id,
        )
        activity = UpdateCase(
            actor=owner_id,
            object=updated_case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.INFO):
            handlers.update_case(mock_dispatchable, dl)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated Name"
        assert stored.content == "New content"

    def test_update_case_rejects_non_owner(self, monkeypatch, caplog):
        """update_case logs a warning and skips if actor is not the case owner."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        non_owner_id = "https://example.org/users/other"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc2",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Hijacked Name",
            attributed_to=owner_id,
        )
        activity = UpdateCase(
            actor=non_owner_id,
            object=updated_case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            handlers.update_case(mock_dispatchable, dl)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Original Name"
        assert any("not the owner" in r.message for r in caplog.records)

    def test_update_case_idempotent(self, monkeypatch):
        """update_case with same data produces the same result (last-write-wins)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc3",
            name="Original",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCase(
            actor=owner_id,
            object=updated_case,
        )
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        handlers.update_case(mock_dispatchable, dl)
        handlers.update_case(mock_dispatchable, dl)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated"

    def test_update_case_warns_when_participant_has_not_accepted_embargo(
        self, monkeypatch, caplog
    ):
        """update_case logs WARNING per CM-10-004 when a participant has not accepted the active embargo."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        embargo = EmbargoEvent(id="https://example.org/embargoes/em1")
        dl.create(embargo)

        participant = CaseParticipant(
            id="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/uc4",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc4",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.as_id,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCase(actor=owner_id, object=updated_case)
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            handlers.update_case(mock_dispatchable, dl)

        assert any(
            "has not accepted" in r.message and "CM-10-004" in r.message
            for r in caplog.records
        )

    def test_update_case_no_warning_when_all_participants_accepted_embargo(
        self, monkeypatch, caplog
    ):
        """update_case does NOT warn when all participants have accepted the active embargo (CM-10-004)."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/bob"
        embargo = EmbargoEvent(id="https://example.org/embargoes/em2")
        dl.create(embargo)

        participant = CaseParticipant(
            id="https://example.org/participants/p2",
            attributed_to=actor_id,
            context="https://example.org/cases/uc5",
            accepted_embargo_ids=[embargo.as_id],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc5",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.as_id,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCase(actor=owner_id, object=updated_case)
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            handlers.update_case(mock_dispatchable, dl)

        assert not any("has not accepted" in r.message for r in caplog.records)

    def test_update_case_no_warning_when_no_active_embargo(
        self, monkeypatch, caplog
    ):
        """update_case does NOT warn when there is no active embargo (CM-10-004)."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCase
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.data.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/carol"

        participant = CaseParticipant(
            id="https://example.org/participants/p3",
            attributed_to=actor_id,
            context="https://example.org/cases/uc6",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc6",
            name="Original",
            attributed_to=owner_id,
            active_embargo=None,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCase(actor=owner_id, object=updated_case)
        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.UPDATE_CASE
        mock_dispatchable.payload = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            handlers.update_case(mock_dispatchable, dl)

        assert not any("has not accepted" in r.message for r in caplog.records)
