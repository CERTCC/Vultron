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

"""The core ``CaseProposal`` and its ``caseInputs`` (CP-01-022, CP-01-023).

``as_CaseProposal`` is the core class (ARCH-25-003), so a ``by_alias`` dump
is its AS2 form and the wire parser builds the core class back.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from test.support.objects import authored_at, make
from test.support.signing import signed_body
from vultron.core.models.actor import VultronOrganization
from vultron.core.models.case_proposal import (
    CaseProposal,
    ProposedCaseInputs,
    ProposedVulnerabilityItem,
)
from vultron.core.models.case_reference import CaseReferenceLink
from vultron.core.models.events.case_proposal import (
    CreateCaseProposalReceivedEvent,
)
from vultron.core.models.vulnerability_item import (
    NoteCategory,
    VulnerabilityItemId,
    VulnerabilityItemNote,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import rm_submit_report_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_FINDER = "https://example.org/actors/finder"
_VENDOR = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/case-actors/alpha"
_DATE = datetime(2099, 6, 1, tzinfo=UTC)


def _inputs() -> ProposedCaseInputs:
    return ProposedCaseInputs(
        name="Overflow in the parser",
        summary="A crafted file overflows the parser.",
        exploit_public=True,
        attacks_observed=False,
        proposed_items=[
            ProposedVulnerabilityItem(
                ids=[VulnerabilityItemId.cve("CVE-2026-0001")],
                name="Overflow",
                vul_notes=[
                    VulnerabilityItemNote(
                        category=NoteCategory.SUMMARY, content="Bad."
                    )
                ],
                reference_links=[
                    CaseReferenceLink(
                        href="https://example.org/advisory", name="Advisory"
                    )
                ],
            )
        ],
        reference_links=[CaseReferenceLink(href="https://example.org/doc")],
        disclosure_date=_DATE,
    )


def _report() -> as_VulnerabilityReport:
    return make(
        as_VulnerabilityReport,
        id_="https://example.org/reports/r-001",
        attributed_to=_FINDER,
        content="An overflow in the widget parser.",
    )


def _proposal(inputs: ProposedCaseInputs | None) -> CaseProposal:
    report = _report()
    offer = rm_submit_report_activity(
        report, to=_VENDOR, actor=_FINDER, at=authored_at()
    )
    return make(
        CaseProposal,
        id_="https://example.org/proposals/p-001",
        attributed_to=_VENDOR,
        object_=report,
        target=_CASE_ACTOR,
        in_reply_to=offer,
        case_inputs=inputs,
    )


def _create_body(proposal: CaseProposal) -> dict[str, Any]:
    activity = make(
        as_Create,
        actor=make(VultronOrganization, id_=_VENDOR),
        object_=proposal,
        to=[_CASE_ACTOR],
    )
    body: dict[str, Any] = json.loads(
        activity.model_dump_json(by_alias=True, serialize_as_any=True)
    )
    return signed_body(body)


@pytest.mark.spec("ARCH-25-003")
def test_the_wire_name_is_the_core_class() -> None:
    assert as_CaseProposal is CaseProposal


@pytest.mark.spec("CP-01-022")
def test_case_inputs_dump_under_their_wire_names() -> None:
    body = json.loads(_proposal(_inputs()).model_dump_json(by_alias=True))
    inputs = body["caseInputs"]
    assert inputs["exploitPublic"] is True
    assert inputs["attacksObserved"] is False
    assert inputs["disclosureDate"] == "2099-06-01T00:00:00.000000+00:00"
    item = inputs["proposedItems"][0]
    assert item["ids"] == [
        {"systemName": "CVE", "identifier": "CVE-2026-0001"}
    ]
    assert item["vulNotes"][0]["content"] == "Bad."
    assert item["referenceLinks"][0]["href"] == "https://example.org/advisory"
    assert inputs["referenceLinks"][0]["type"] == "Link"


@pytest.mark.spec("CP-01-022")
def test_case_inputs_round_trip_through_a_dump() -> None:
    proposal = _proposal(_inputs())
    again = CaseProposal.model_validate(
        json.loads(proposal.model_dump_json(by_alias=True))
    )
    assert again.case_inputs == _inputs()
    assert again.in_reply_to is not None


@pytest.mark.spec("CP-01-022", "CP-01-028")
def test_case_inputs_survive_the_parser_and_reach_the_event() -> None:
    """A received proposal's caseInputs reach core whole, and the edge reads
    no CSAF document for it (CP-01-028)."""
    parsed = parse_activity(_create_body(_proposal(_inputs())))
    proposal = getattr(parsed, "object_", None)
    assert isinstance(proposal, CaseProposal)
    assert proposal.case_inputs == _inputs()

    event = extract_event(parsed)
    assert isinstance(event, CreateCaseProposalReceivedEvent)
    assert event.case_inputs == _inputs()
    assert event.claims_readings == []


@pytest.mark.spec("CP-01-022")
def test_a_proposal_without_case_inputs_omits_them() -> None:
    proposal = _proposal(None)
    body = json.loads(
        proposal.model_dump_json(by_alias=True, exclude_none=True)
    )
    assert "caseInputs" not in body
    event = extract_event(parse_activity(_create_body(proposal)))
    assert isinstance(event, CreateCaseProposalReceivedEvent)
    assert event.case_inputs is None


@pytest.mark.spec("CP-01-027")
def test_case_inputs_state_no_public_flag() -> None:
    """P is judged when the case is built, so caseInputs has no field for it."""
    with pytest.raises(ValidationError, match="public"):
        ProposedCaseInputs.model_validate({"public": True})


@pytest.mark.spec("CP-01-023")
def test_case_inputs_refuse_a_disclosure_date_with_no_time_zone() -> None:
    with pytest.raises(ValidationError):
        ProposedCaseInputs(disclosure_date=datetime(2099, 6, 1))  # noqa: DTZ001


@pytest.mark.spec("CP-01-022")
def test_a_proposed_item_has_no_id_or_time_of_its_own() -> None:
    """The CASE_MANAGER mints the item's id and stamps its time."""
    with pytest.raises(ValidationError):
        ProposedVulnerabilityItem.model_validate({"id": "https://x/1"})
    with pytest.raises(ValidationError):
        ProposedVulnerabilityItem.model_validate({"published": _DATE})


@pytest.mark.spec("CP-01-007")
def test_in_reply_to_refuses_an_object_that_is_not_an_offer() -> None:
    with pytest.raises(ValidationError, match="CP-01-007"):
        make(
            CaseProposal,
            attributed_to=_VENDOR,
            object_=_report(),
            target=_CASE_ACTOR,
            in_reply_to=_report(),
        )
