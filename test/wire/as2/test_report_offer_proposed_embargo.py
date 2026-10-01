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

"""A Reporter's proposed embargo rides on the report Offer and the CaseProposal.

EP-04-004: the Offer(VulnerabilityReport) carries a proposed ``EmbargoEvent``
whose ``context`` is the report (EP-04-009).  CP-01-008: the CaseProposal
carries that Offer whole under ``inReplyTo``, so the case-actor — which never
saw the Offer — receives the Reporter's terms as the Reporter stated them.
Extraction surfaces the terms on both received events (ADR-0035).  #3392.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.models.events.report import SubmitReportReceivedEvent
from vultron.semantic_registry import extract_event, find_matching_semantics
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    rm_submit_report_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Offer,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_FINDER = "https://example.org/actors/finder"
_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/case-actors/alpha"
_CASE = "https://example.org/cases/1"
_END = datetime(2099, 6, 1, tzinfo=UTC)


def _report() -> as_VulnerabilityReport:
    return as_VulnerabilityReport(
        id_="https://example.org/reports/r-001",
        attributed_to=_FINDER,
        content="An overflow in the widget parser.",
    )


def _proposal_for(report: as_VulnerabilityReport) -> EmbargoEvent:
    return EmbargoEvent(
        id_=f"{report.id_}/embargo_proposals/1",
        context=report.id_,
        end_time=_END,
    )


def _offer(report: as_VulnerabilityReport | None = None) -> as_Offer:
    report = report or _report()
    return rm_submit_report_activity(
        report,
        to=_VENDOR,
        actor=_FINDER,
        proposed_embargo=_proposal_for(report),
    )


def _wire(activity) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(
        activity.model_dump_json(by_alias=True, serialize_as_any=True)
    )
    return body


# ---------------------------------------------------------------------------
# The Offer
# ---------------------------------------------------------------------------


@pytest.mark.spec("EP-04-004")
def test_factory_carries_the_proposal_under_its_wire_name() -> None:
    offer = _offer()
    body = _wire(offer)
    assert body["proposedEmbargo"]["type"] == "EmbargoEvent"
    assert body["proposedEmbargo"]["context"] == _report().id_
    assert body["proposedEmbargo"]["endTime"] == "2099-06-01T00:00:00+00:00"


@pytest.mark.spec("EP-04-009")
def test_factory_refuses_a_proposal_about_something_else() -> None:
    """Before a case exists the subject is the report; a stray context is a bug."""
    report = _report()
    other = EmbargoEvent(context=_CASE, end_time=_END)
    with pytest.raises(VultronActivityConstructionError, match="EP-04-009"):
        rm_submit_report_activity(
            report, to=_VENDOR, actor=_FINDER, proposed_embargo=other
        )


@pytest.mark.spec("EP-04-009")
def test_embargo_event_with_a_report_context_validates() -> None:
    event = _proposal_for(_report())
    assert event.context == _report().id_


@pytest.mark.spec("EP-04-004")
def test_offer_with_a_proposal_survives_the_inbound_parse() -> None:
    """The nested EmbargoEvent comes back as the core class, terms intact."""
    parsed = parse_activity(_wire(_offer()))
    assert isinstance(parsed, as_Offer)
    proposal = parsed.proposed_embargo
    assert isinstance(proposal, EmbargoEvent)
    assert proposal.context == _report().id_
    assert proposal.end_time == _END


@pytest.mark.spec("EP-04-004")
def test_extraction_surfaces_the_proposal_on_the_submit_report_event() -> None:
    event = extract_event(parse_activity(_wire(_offer())))
    assert isinstance(event, SubmitReportReceivedEvent)
    assert event.semantic_type is MessageSemantics.SUBMIT_REPORT
    assert isinstance(event.proposed_embargo, EmbargoEvent)
    assert event.proposed_embargo.end_time == _END


def test_an_offer_without_a_proposal_extracts_none() -> None:
    offer = rm_submit_report_activity(_report(), to=_VENDOR, actor=_FINDER)
    event = extract_event(parse_activity(_wire(offer)))
    assert isinstance(event, SubmitReportReceivedEvent)
    assert event.proposed_embargo is None


def test_a_proposal_named_by_reference_is_read_as_absent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sender inlines what it introduces (ADR-0107); a bare id is not terms."""
    body = _wire(_offer())
    body["proposedEmbargo"] = "https://example.org/embargoes/somewhere-else"
    with caplog.at_level(logging.WARNING):
        event = extract_event(parse_activity(body))
    assert isinstance(event, SubmitReportReceivedEvent)
    assert event.proposed_embargo is None
    assert any("by reference" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# The CaseProposal carrying the Offer
# ---------------------------------------------------------------------------


def _case_proposal(offer: as_Offer | None = None) -> as_CaseProposal:
    report = _report()
    offer = offer if offer is not None else _offer(report)
    return as_CaseProposal(
        id_="https://example.org/proposals/p-001",
        attributed_to=_VENDOR,
        object_=report,
        target=_CASE_ACTOR,
        offer_id=offer.id_,
        offer_actor_id=_FINDER,
        in_reply_to=offer,
    )


@pytest.mark.spec("CP-01-008")
def test_case_proposal_embeds_the_offer_and_round_trips_through_the_parser():
    """An activity nested inside an object: the first such shape in the vocab."""
    activity = as_Create(
        actor=_VENDOR, object_=_case_proposal(), to=[_CASE_ACTOR]
    )
    body = _wire(activity)
    assert body["object"]["inReplyTo"]["type"] == "Offer"
    assert body["object"]["inReplyTo"]["proposedEmbargo"]["type"] == (
        "EmbargoEvent"
    )

    parsed = parse_activity(body)
    proposal = getattr(parsed, "object_", None)
    assert isinstance(proposal, as_CaseProposal)
    assert isinstance(proposal.in_reply_to, as_Offer)
    assert proposal.in_reply_to.id_ == proposal.offer_id
    nested = proposal.in_reply_to.proposed_embargo
    assert isinstance(nested, EmbargoEvent)
    assert nested.context == _report().id_


@pytest.mark.spec("CP-01-008")
def test_case_proposal_refuses_provenance_that_names_a_different_offer():
    offer = _offer()
    with pytest.raises(ValueError, match="CP-01-008"):
        as_CaseProposal(
            attributed_to=_VENDOR,
            object_=_report(),
            target=_CASE_ACTOR,
            offer_id="urn:uuid:00000000-0000-4000-8000-000000000000",
            in_reply_to=offer,
        )


@pytest.mark.spec("CP-01-008")
def test_case_proposal_without_the_offer_still_validates():
    proposal = as_CaseProposal(
        attributed_to=_VENDOR, object_=_report(), target=_CASE_ACTOR
    )
    assert proposal.in_reply_to is None


@pytest.mark.spec("EP-04-004")
def test_extraction_surfaces_the_proposal_on_the_case_proposal_event():
    activity = as_Create(
        actor=_VENDOR, object_=_case_proposal(), to=[_CASE_ACTOR]
    )
    event = extract_event(parse_activity(_wire(activity)))
    assert isinstance(event, CreateCaseProposalReceivedEvent)
    assert isinstance(event.proposed_embargo, EmbargoEvent)
    assert event.proposed_embargo.context == _report().id_
    assert event.proposed_embargo.end_time == _END


def test_case_proposal_without_terms_extracts_none():
    offer = rm_submit_report_activity(_report(), to=_VENDOR, actor=_FINDER)
    activity = as_Create(
        actor=_VENDOR, object_=_case_proposal(offer), to=[_CASE_ACTOR]
    )
    event = extract_event(parse_activity(_wire(activity)))
    assert isinstance(event, CreateCaseProposalReceivedEvent)
    assert event.proposed_embargo is None


# ---------------------------------------------------------------------------
# VAM-05-001: Create(EmbargoEvent) may name a report as its subject
# ---------------------------------------------------------------------------


@pytest.mark.spec("VAM-05-001")
@pytest.mark.parametrize(
    "context_obj",
    [
        pytest.param(_report(), id="report"),
        pytest.param(
            VulnerabilityCase(id_=_CASE, attributed_to=_VENDOR), id="case"
        ),
    ],
)
def test_create_embargo_event_dispatches_with_either_subject(context_obj):
    event = EmbargoEvent(context=context_obj.id_, end_time=_END)
    activity = as_Create(actor=_VENDOR, object_=event, context=context_obj)
    assert (
        find_matching_semantics(activity)
        is MessageSemantics.CREATE_EMBARGO_EVENT
    )


@pytest.mark.spec("CP-01-008")
def test_case_proposal_refuses_a_sender_that_is_not_the_inline_offers_actor():
    offer = _offer()
    with pytest.raises(ValueError, match="offerActorId"):
        as_CaseProposal(
            attributed_to=_VENDOR,
            object_=_report(),
            target=_CASE_ACTOR,
            offer_id=offer.id_,
            offer_actor_id="https://example.org/actors/someone-else",
            in_reply_to=offer,
        )


@pytest.mark.spec("EP-04-004")
def test_a_generic_event_shaped_proposal_is_projected_to_embargo_terms() -> (
    None
):
    """A sender that types the proposal as a plain AS2 ``Event`` is read the
    same way an ``Invite(Event)``'s object is: end and context become an
    ``EmbargoEvent``."""
    report = _report()
    body = _wire(_offer(report))
    body["proposedEmbargo"] = {
        "type": "Event",
        "id": f"{report.id_}/embargo_proposals/generic",
        "context": report.id_,
        "endTime": _END.isoformat(),
    }
    event = extract_event(parse_activity(body))
    assert isinstance(event, SubmitReportReceivedEvent)
    terms = event.proposed_embargo
    assert isinstance(terms, EmbargoEvent)
    assert terms.id_ == f"{report.id_}/embargo_proposals/generic"
    assert terms.context == report.id_
    assert terms.end_time == _END


@pytest.mark.spec("CP-01-008")
@pytest.mark.spec("EP-04-009")
def test_case_proposal_refuses_an_offer_for_a_different_report():
    """The inline Offer must be the one that brought *this* report; otherwise
    the case-actor would read another report's proposed terms."""
    other = as_VulnerabilityReport(
        id_="https://example.org/reports/r-999",
        attributed_to=_FINDER,
        content="A different report.",
    )
    offer = _offer(other)
    with pytest.raises(ValueError, match="not the report"):
        as_CaseProposal(
            attributed_to=_VENDOR,
            object_=_report(),
            target=_CASE_ACTOR,
            offer_id=offer.id_,
            offer_actor_id=_FINDER,
            in_reply_to=offer,
        )
