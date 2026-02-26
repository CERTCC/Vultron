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
from vultron.as_vocab.base.objects.activities.transitive import as_Create
from vultron.as_vocab.objects.vulnerability_case import VulnerabilityCase
from vultron.as_vocab.objects.vulnerability_report import VulnerabilityReport
from vultron.enums import MessageSemantics
from vultron.types import DispatchActivity


class TestVerifySemanticsDecorator:
    """Test the verify_semantics decorator validation logic."""

    def test_decorator_validates_matching_semantics(self):
        """Test that decorator allows through activities with matching semantics."""

        # Create a test handler decorated with verify_semantics
        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
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
        mock_activity.payload = create_activity

        # Should execute successfully
        result = test_handler(mock_activity)
        assert result == "success"

    def test_decorator_raises_error_for_missing_semantic_type(self):
        """Test that decorator raises error when semantic_type is None."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
            return "success"

        # Create mock with None semantic_type
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = None

        # Should raise VultronApiHandlerMissingSemanticError
        with pytest.raises(VultronApiHandlerMissingSemanticError):
            test_handler(mock_activity)

    def test_decorator_raises_error_for_semantic_mismatch(self):
        """Test that decorator raises error when semantic types don't match."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
            return "success"

        # Create mock that claims CREATE_REPORT but payload says CREATE_CASE
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT

        # Create proper as_Create activity with VulnerabilityCase object (mismatched!)
        case = VulnerabilityCase(
            name="TEST-CASE-001", content="Test vulnerability case"
        )
        create_case_activity = as_Create(
            actor="https://example.org/users/tester", object=case
        )
        mock_activity.payload = create_case_activity

        # Should raise VultronApiHandlerSemanticMismatchError
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            test_handler(mock_activity)

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves the wrapped function's __name__."""

        @handlers.verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
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
        mock_activity.payload = create_activity

        # Should execute without raising
        result = handlers.create_report(mock_activity)
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
        mock_activity.payload = create_activity

        # Should execute without raising
        result = handlers.create_case(mock_activity)
        assert result is None

    def test_handler_rejects_wrong_semantic_type(self):
        """Test handler rejects activity with wrong semantic type."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT

        # Create proper as_Create activity with VulnerabilityCase object
        # Payload says CREATE_CASE, but handler expects CREATE_REPORT
        case = VulnerabilityCase(
            name="TEST-CASE-003", content="Test vulnerability case"
        )
        create_activity = as_Create(
            actor="https://example.org/users/tester", object=case
        )
        mock_activity.payload = create_activity

        # Should raise semantic mismatch error
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            handlers.create_report(mock_activity)


class TestInviteActorHandlers:
    """Tests for invite_actor_to_case, accept_invite_actor_to_case,
    reject_invite_actor_to_case, and remove_case_participant_from_case."""

    def test_invite_actor_to_case_stores_invite(self, monkeypatch):
        """invite_actor_to_case persists the Invite activity to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import RmInviteToCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

        invite = RmInviteToCase(
            id="https://example.org/cases/case1/invitations/1",
            actor="https://example.org/users/owner",
            object="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.INVITE_ACTOR_TO_CASE
        mock_dispatchable.payload = invite

        handlers.invite_actor_to_case(mock_dispatchable)

        stored = dl.get(invite.as_type.value, invite.as_id)
        assert stored is not None

    def test_invite_actor_to_case_idempotent(self, monkeypatch):
        """invite_actor_to_case skips storing a duplicate Invite."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import RmInviteToCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

        invite = RmInviteToCase(
            id="https://example.org/cases/case1/invitations/2",
            actor="https://example.org/users/owner",
            object="https://example.org/users/coordinator",
            target="https://example.org/cases/case1",
        )

        mock_dispatchable = MagicMock(spec=DispatchActivity)
        mock_dispatchable.semantic_type = MessageSemantics.INVITE_ACTOR_TO_CASE
        mock_dispatchable.payload = invite

        handlers.invite_actor_to_case(mock_dispatchable)
        handlers.invite_actor_to_case(
            mock_dispatchable
        )  # second call is no-op

        stored = dl.get(invite.as_type.value, invite.as_id)
        assert stored is not None

    def test_reject_invite_actor_to_case_logs_rejection(self):
        """reject_invite_actor_to_case logs without raising."""
        from vultron.as_vocab.activities.case import (
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
        mock_dispatchable.payload = reject

        result = handlers.reject_invite_actor_to_case(mock_dispatchable)
        assert result is None

    def test_remove_case_participant_from_case(self, monkeypatch):
        """remove_case_participant_from_case removes the participant from case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.as_vocab.objects.case_participant import CaseParticipant
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = remove_activity

        handlers.remove_case_participant_from_case(mock_dispatchable)

        assert participant.as_id not in [
            (p.as_id if hasattr(p, "as_id") else p)
            for p in case.case_participants
        ]

    def test_remove_case_participant_idempotent(self, monkeypatch):
        """remove_case_participant_from_case is idempotent when participant absent."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.as_vocab.objects.case_participant import CaseParticipant
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = remove_activity

        result = handlers.remove_case_participant_from_case(mock_dispatchable)
        assert result is None


class TestEmbargoHandlers:
    """Tests for embargo management handlers."""

    def test_create_embargo_event_stores_event(self, monkeypatch):
        """create_embargo_event persists the EmbargoEvent to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.create_embargo_event(mock_dispatchable)

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_create_embargo_event_idempotent(self, monkeypatch):
        """create_embargo_event skips storing a duplicate EmbargoEvent."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.create_embargo_event(mock_dispatchable)
        handlers.create_embargo_event(mock_dispatchable)  # second call no-op

        stored = dl.get(embargo.as_type.value, embargo.as_id)
        assert stored is not None

    def test_add_embargo_event_to_case_activates_embargo(self, monkeypatch):
        """add_embargo_event_to_case sets the active embargo on the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.embargo import AddEmbargoToCase
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.bt.embargo_management.states import EM

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.add_embargo_event_to_case(mock_dispatchable)

        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_invite_to_embargo_on_case_stores_proposal(self, monkeypatch):
        """invite_to_embargo_on_case persists the EmProposeEmbargo activity."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.embargo import EmProposeEmbargo
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = proposal

        handlers.invite_to_embargo_on_case(mock_dispatchable)

        stored = dl.get(proposal.as_type.value, proposal.as_id)
        assert stored is not None

    def test_accept_invite_to_embargo_on_case_activates_embargo(
        self, monkeypatch
    ):
        """accept_invite_to_embargo_on_case activates the embargo on the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.embargo import (
            EmAcceptEmbargo,
            EmProposeEmbargo,
        )
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )
        from vultron.bt.embargo_management.states import EM

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = accept

        handlers.accept_invite_to_embargo_on_case(mock_dispatchable)

        assert case.active_embargo is not None
        assert case.current_status.em_state == EM.ACTIVE

    def test_reject_invite_to_embargo_on_case_logs_rejection(self):
        """reject_invite_to_embargo_on_case logs without raising."""
        from vultron.as_vocab.activities.embargo import (
            EmProposeEmbargo,
            EmRejectEmbargo,
        )
        from vultron.as_vocab.objects.embargo_event import EmbargoEvent

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
        mock_dispatchable.payload = reject

        result = handlers.reject_invite_to_embargo_on_case(mock_dispatchable)
        assert result is None


class TestNoteHandlers:
    """Tests for note management handlers."""

    def test_create_note_stores_note(self, monkeypatch):
        """create_note persists the Note to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.as_vocab.base.objects.object_types import as_Note

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.create_note(mock_dispatchable)

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_create_note_idempotent(self, monkeypatch):
        """create_note skips storing a duplicate Note."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Create,
        )
        from vultron.as_vocab.base.objects.object_types import as_Note

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        dl.create(note)
        handlers.create_note(mock_dispatchable)

        stored = dl.get(note.as_type.value, note.as_id)
        assert stored is not None

    def test_add_note_to_case_appends_note(self, monkeypatch):
        """add_note_to_case appends note ID to case.notes and persists."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import AddNoteToCase
        from vultron.as_vocab.base.objects.object_types import as_Note
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.add_note_to_case(mock_dispatchable)

        assert note.as_id in case.notes

    def test_add_note_to_case_idempotent(self, monkeypatch):
        """add_note_to_case skips adding a note already in the case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import AddNoteToCase
        from vultron.as_vocab.base.objects.object_types import as_Note
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.add_note_to_case(mock_dispatchable)

        assert case.notes.count(note.as_id) == 1

    def test_remove_note_from_case_removes_note(self, monkeypatch):
        """remove_note_from_case removes note ID from case.notes and persists."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.as_vocab.base.objects.object_types import as_Note
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.remove_note_from_case(mock_dispatchable)

        assert note.as_id not in case.notes

    def test_remove_note_from_case_idempotent(self, monkeypatch):
        """remove_note_from_case is idempotent when note not in case."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.as_vocab.base.objects.object_types import as_Note
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        result = handlers.remove_note_from_case(mock_dispatchable)
        assert result is None


class TestStatusHandlers:
    """Tests for case status and participant status handlers."""

    def test_create_case_status_stores_status(self, monkeypatch):
        """create_case_status persists the CaseStatus to the DataLayer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import CreateCaseStatus
        from vultron.as_vocab.objects.case_status import CaseStatus
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.create_case_status(mock_dispatchable)

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_create_case_status_idempotent(self, monkeypatch):
        """create_case_status skips storing a duplicate CaseStatus."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import CreateCaseStatus
        from vultron.as_vocab.objects.case_status import CaseStatus
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.create_case_status(mock_dispatchable)

        stored = dl.get(status.as_type.value, status.as_id)
        assert stored is not None

    def test_add_case_status_to_case_appends_status(self, monkeypatch):
        """add_case_status_to_case appends status ID to case.case_status."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import AddStatusToCase
        from vultron.as_vocab.objects.case_status import CaseStatus
        from vultron.as_vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.add_case_status_to_case(mock_dispatchable)

        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s) for s in case.case_status
        ]
        assert status.as_id in status_ids

    def test_create_participant_status_stores_status(self, monkeypatch):
        """create_participant_status persists the ParticipantStatus."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case_participant import (
            CreateStatusForParticipant,
        )
        from vultron.as_vocab.objects.case_status import ParticipantStatus

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

        pstatus = ParticipantStatus(
            id="https://example.org/cases/case_ps1/participants/p1/statuses/s1",
            context="https://example.org/cases/case_ps1",
        )
        from vultron.as_vocab.objects.vulnerability_case import (
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
        mock_dispatchable.payload = activity

        handlers.create_participant_status(mock_dispatchable)

        stored = dl.get(pstatus.as_type.value, pstatus.as_id)
        assert stored is not None

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch
    ):
        """add_participant_status_to_participant appends status to participant."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case_participant import (
            AddStatusToParticipant,
        )
        from vultron.as_vocab.objects.case_participant import CaseParticipant
        from vultron.as_vocab.objects.case_status import ParticipantStatus

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        from vultron.as_vocab.objects.vulnerability_case import (
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
        mock_dispatchable.payload = activity

        handlers.add_participant_status_to_participant(mock_dispatchable)

        status_ids = [
            (s.as_id if hasattr(s, "as_id") else s)
            for s in participant.participant_status
        ]
        assert pstatus.as_id in status_ids


class TestSuggestActorHandlers:
    """Tests for suggest_actor_to_case, accept/reject suggest_actor handlers."""

    def test_suggest_actor_to_case_persists_recommendation(self, monkeypatch):
        """suggest_actor_to_case persists the RecommendActor offer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.actor import RecommendActor
        from vultron.as_vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.suggest_actor_to_case(mock_dispatchable)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_suggest_actor_to_case_idempotent(self, monkeypatch):
        """suggest_actor_to_case is idempotent — second call is a no-op."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.actor import RecommendActor
        from vultron.as_vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.suggest_actor_to_case(mock_dispatchable)
        handlers.suggest_actor_to_case(mock_dispatchable)

        # Second call should be a no-op; record is still present (not duplicated)
        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_accept_suggest_actor_to_case_persists_acceptance(
        self, monkeypatch
    ):
        """accept_suggest_actor_to_case persists the AcceptActorRecommendation."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.actor import (
            AcceptActorRecommendation,
            RecommendActor,
        )
        from vultron.as_vocab.base.objects.actors import as_Actor

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.accept_suggest_actor_to_case(mock_dispatchable)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_reject_suggest_actor_to_case_logs_rejection(
        self, monkeypatch, caplog
    ):
        """reject_suggest_actor_to_case logs rejection without state change."""
        import logging

        from vultron.as_vocab.activities.actor import (
            RecommendActor,
            RejectActorRecommendation,
        )
        from vultron.as_vocab.base.objects.actors import as_Actor

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
        mock_dispatchable.payload = activity

        with caplog.at_level(logging.INFO):
            handlers.reject_suggest_actor_to_case(mock_dispatchable)

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestOwnershipTransferHandlers:
    """Tests for offer/accept/reject ownership transfer handlers."""

    def test_offer_case_ownership_transfer_persists_offer(self, monkeypatch):
        """offer_case_ownership_transfer persists the offer."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import OfferCaseOwnershipTransfer

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )

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
        mock_dispatchable.payload = activity

        handlers.offer_case_ownership_transfer(mock_dispatchable)

        stored = dl.get(activity.as_type.value, activity.as_id)
        assert stored is not None

    def test_accept_case_ownership_transfer_updates_attributed_to(
        self, monkeypatch
    ):
        """accept_case_ownership_transfer updates case.attributed_to to new owner."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import (
            AcceptCaseOwnershipTransfer,
            OfferCaseOwnershipTransfer,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.accept_case_ownership_transfer(mock_dispatchable)

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

        from vultron.as_vocab.activities.case import (
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
        mock_dispatchable.payload = activity

        with caplog.at_level(logging.INFO):
            handlers.reject_case_ownership_transfer(mock_dispatchable)

        assert any("rejected" in r.message.lower() for r in caplog.records)


class TestUpdateCaseHandler:
    """Tests for update_case handler."""

    def test_update_case_applies_scalar_updates(self, monkeypatch, caplog):
        """update_case applies name/summary/content updates from a full object."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        with caplog.at_level(logging.INFO):
            handlers.update_case(mock_dispatchable)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated Name"
        assert stored.content == "New content"

    def test_update_case_rejects_non_owner(self, monkeypatch, caplog):
        """update_case logs a warning and skips if actor is not the case owner."""
        import logging

        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        with caplog.at_level(logging.WARNING):
            handlers.update_case(mock_dispatchable)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Original Name"
        assert any("not the owner" in r.message for r in caplog.records)

    def test_update_case_idempotent(self, monkeypatch):
        """update_case with same data produces the same result (last-write-wins)."""
        from vultron.api.v2.datalayer.tinydb_backend import TinyDbDataLayer
        from vultron.as_vocab.activities.case import UpdateCase

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.api.v2.datalayer.tinydb_backend.get_datalayer",
            lambda **_: dl,
        )
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
        mock_dispatchable.payload = activity

        handlers.update_case(mock_dispatchable)
        handlers.update_case(mock_dispatchable)

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated"
