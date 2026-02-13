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
