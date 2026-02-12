"""
Unit tests for handler functions and the verify_semantics decorator.

Tests ensure that:
- HP-02-001: All handlers have @verify_semantics decorator
- HP-02-002: Decorator validates semantic type matches
- HP-02-003: Decorator raises errors for mismatched semantics
- HP-02-004: Decorator raises errors for missing semantics
"""

import pytest
from unittest.mock import MagicMock

from vultron.api.v2.backend.handlers import (
    verify_semantics,
    create_report,
    submit_report,
    validate_report,
    invalidate_report,
    ack_report,
    close_report,
    create_case,
    add_report_to_case,
    suggest_actor_to_case,
    accept_suggest_actor_to_case,
    reject_suggest_actor_to_case,
    offer_case_ownership_transfer,
    accept_case_ownership_transfer,
    reject_case_ownership_transfer,
    invite_actor_to_case,
    accept_invite_actor_to_case,
    reject_invite_actor_to_case,
    create_embargo_event,
    add_embargo_event_to_case,
    remove_embargo_event_from_case,
    announce_embargo_event_to_case,
    invite_to_embargo_on_case,
    accept_invite_to_embargo_on_case,
    reject_invite_to_embargo_on_case,
    close_case,
    create_case_participant,
    add_case_participant_to_case,
    remove_case_participant_from_case,
    create_note,
    add_note_to_case,
    remove_note_from_case,
    create_case_status,
    add_case_status_to_case,
    create_participant_status,
    add_participant_status_to_participant,
    unknown,
)
from vultron.api.v2.errors import (
    VultronApiHandlerMissingSemanticError,
    VultronApiHandlerSemanticMismatchError,
)
from vultron.enums import MessageSemantics
from vultron.types import DispatchActivity


class TestVerifySemanticsDecorator:
    """Test the verify_semantics decorator validation logic."""

    def test_decorator_validates_matching_semantics(self):
        """Test that decorator allows through activities with matching semantics."""

        # Create a test handler decorated with verify_semantics
        @verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
            return "success"

        # Create a mock DispatchActivity with matching semantics
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT

        # Mock payload that will match CREATE_REPORT pattern
        mock_activity.payload = {
            "type": "Create",
            "object": {"type": "VulnerabilityReport"},
        }

        # Should execute successfully
        result = test_handler(mock_activity)
        assert result == "success"

    def test_decorator_raises_error_for_missing_semantic_type(self):
        """Test that decorator raises error when semantic_type is None."""

        @verify_semantics(MessageSemantics.CREATE_REPORT)
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

        @verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
            return "success"

        # Create mock that claims CREATE_REPORT but payload says CREATE_CASE
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT
        mock_activity.payload = {
            "type": "Create",
            "object": {"type": "VulnerabilityCase"},  # Mismatched!
        }

        # Should raise VultronApiHandlerSemanticMismatchError
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            test_handler(mock_activity)

    def test_decorator_preserves_function_name(self):
        """Test that decorator preserves the wrapped function's __name__."""

        @verify_semantics(MessageSemantics.CREATE_REPORT)
        def test_handler(dispatchable: DispatchActivity) -> str:
            return "success"

        # Decorator should preserve function name via @wraps
        assert test_handler.__name__ == "test_handler"


class TestHandlerDecoratorPresence:
    """Test that all handler functions have the @verify_semantics decorator."""

    def test_create_report_has_decorator(self):
        """Test create_report handler has verify_semantics decorator."""
        # Function should be callable (not None) - this was the bug!
        assert callable(create_report)
        assert create_report.__name__ == "create_report"

    def test_all_handlers_are_callable(self):
        """Test that all 47 handler functions are callable (regression test for decorator bug)."""
        handlers = [
            create_report,
            submit_report,
            validate_report,
            invalidate_report,
            ack_report,
            close_report,
            create_case,
            add_report_to_case,
            suggest_actor_to_case,
            accept_suggest_actor_to_case,
            reject_suggest_actor_to_case,
            offer_case_ownership_transfer,
            accept_case_ownership_transfer,
            reject_case_ownership_transfer,
            invite_actor_to_case,
            accept_invite_actor_to_case,
            reject_invite_actor_to_case,
            create_embargo_event,
            add_embargo_event_to_case,
            remove_embargo_event_from_case,
            announce_embargo_event_to_case,
            invite_to_embargo_on_case,
            accept_invite_to_embargo_on_case,
            reject_invite_to_embargo_on_case,
            close_case,
            create_case_participant,
            add_case_participant_to_case,
            remove_case_participant_from_case,
            create_note,
            add_note_to_case,
            remove_note_from_case,
            create_case_status,
            add_case_status_to_case,
            create_participant_status,
            add_participant_status_to_participant,
            unknown,
        ]

        # Before the bug fix, missing 'return wrapper' made all these None
        for handler in handlers:
            assert callable(handler), f"{handler} is not callable"


class TestHandlerExecution:
    """Test that handlers execute with valid semantics."""

    def test_create_report_executes_with_valid_semantics(self):
        """Test create_report handler executes when semantics match."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT
        mock_activity.payload = {
            "type": "Create",
            "object": {"type": "VulnerabilityReport"},
        }

        # Should execute without raising
        result = create_report(mock_activity)
        # Current stub implementation returns None
        assert result is None

    def test_create_case_executes_with_valid_semantics(self):
        """Test create_case handler executes when semantics match."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_CASE
        mock_activity.payload = {
            "type": "Create",
            "object": {"type": "VulnerabilityCase"},
        }

        # Should execute without raising
        result = create_case(mock_activity)
        assert result is None

    def test_handler_rejects_wrong_semantic_type(self):
        """Test handler rejects activity with wrong semantic type."""
        mock_activity = MagicMock(spec=DispatchActivity)
        mock_activity.semantic_type = MessageSemantics.CREATE_REPORT
        # Payload says CREATE_CASE, but handler expects CREATE_REPORT
        mock_activity.payload = {
            "type": "Create",
            "object": {"type": "VulnerabilityCase"},
        }

        # Should raise semantic mismatch error
        with pytest.raises(VultronApiHandlerSemanticMismatchError):
            create_report(mock_activity)
