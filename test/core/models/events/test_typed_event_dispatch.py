"""Typed-dispatch tests: extract_event() returns the correct per-semantic subclass.

Spec: SE-03-001 (semantic-extraction), CS-10-002 (FooReceivedEvent naming).
Covers AC4 of ISSUE-2489: new typed-dispatch tests for ≥3 representative semantics.
"""

import pytest

from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    accept_case_proposal_activity,
    recommend_actor_activity,
)
from vultron.wire.as2.factories.report import rm_create_report_activity
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-1"
_CASE_ACTOR_URI = "https://example.org/services/case-actor-1"


class TestTypedEventDispatch:
    """extract_event() returns the narrowed per-semantic subclass, not bare VultronEvent."""

    @pytest.mark.spec("SE-03-001")
    @pytest.mark.spec("CS-10-002")
    def test_create_report_returns_create_report_received_event(self):
        from vultron.core.models.events.report import CreateReportReceivedEvent

        activity = rm_create_report_activity(gen_report(), actor=_ACTOR_URI)
        event = extract_event(activity)

        assert isinstance(event, CreateReportReceivedEvent)

    @pytest.mark.spec("SE-03-001")
    @pytest.mark.spec("CS-10-002")
    def test_accept_case_proposal_returns_accept_case_proposal_received_event(
        self,
    ):
        from vultron.core.models.events.case_proposal import (
            AcceptCaseProposalReceivedEvent,
        )

        proposal = as_CaseProposal(
            attributed_to=_ACTOR_URI,
            object_=gen_report(),
            target=_CASE_ACTOR_URI,
        )
        activity = accept_case_proposal_activity(
            actor_id=_CASE_ACTOR_URI,
            proposal=proposal,
            to=[_ACTOR_URI],
        )
        event = extract_event(activity)

        assert isinstance(event, AcceptCaseProposalReceivedEvent)

    @pytest.mark.spec("SE-03-001")
    @pytest.mark.spec("CS-10-002")
    def test_offer_actor_to_case_returns_offer_actor_to_case_received_event(
        self,
    ):
        from vultron.core.models.events.actor import (
            OfferActorToCaseReceivedEvent,
        )

        recommended = as_Actor(id_="https://example.org/actors/vendor-new")
        activity = recommend_actor_activity(
            recommended,
            target=_CASE_URI,
            actor=_ACTOR_URI,
            to=[_CASE_ACTOR_URI],
        )
        event = extract_event(activity)

        assert isinstance(event, OfferActorToCaseReceivedEvent)

    @pytest.mark.spec("SE-03-001")
    @pytest.mark.spec("CS-10-002")
    def test_event_semantic_type_matches_subclass_literal(self):
        """semantic_type on the returned event matches the subclass's narrowed Literal."""
        from vultron.core.models.events.report import CreateReportReceivedEvent
        from vultron.core.models.events.base import MessageSemantics

        activity = rm_create_report_activity(gen_report(), actor=_ACTOR_URI)
        event = extract_event(activity)

        assert isinstance(event, CreateReportReceivedEvent)
        assert event.semantic_type == MessageSemantics.CREATE_REPORT
