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
"""
Unit tests for vultron.wire.as2.factories.case.

Spec coverage:
- AF-01-002: Factory functions return plain AS2 base types.
- AF-01-003: Explicit, domain-typed parameters for protocol-significant fields.
- AF-04-001: Factory functions wrap ValidationError in
  VultronActivityConstructionError.
- AF-04-002: All factory functions re-exported from factories/__init__.py.
- CM-17-002: The stub carries the embargo in force (EM ACTIVE or REVISE).
- CM-17-011, CM-17-024: The stub Invite embeds the full active embargo, or is refused.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.support.case_owner import CASE_OWNER_ID
from test.support.embargo_register import register
from test.support.future_dates import FAR_FUTURE, days_from_now
from test.support.objects import authored_at, make
from test.support.signing import signed_body
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_preview import (
    preview_current_status,
    preview_em_state,
    preview_embargo_id,
    preview_in_force_embargo,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.preview_object import is_loose_form_of
from vultron.core.states.em import EM
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    accept_case_ownership_transfer_activity,
    add_note_to_case_activity,
    add_report_to_case_activity,
    add_status_to_case_activity,
    announce_vulnerability_case_activity,
    create_case_activity,
    offer_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    rm_accept_invite_to_case_activity,
    rm_close_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
    rm_invite_to_case_activity,
    rm_reject_invite_to_case_activity,
    undo_case_ownership_transfer_activity,
    update_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import as_TypedReference, case_reference
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
    as_Announce,
    as_Create,
    as_Ignore,
    as_Invite,
    as_Join,
    as_Leave,
    as_Offer,
    as_Reject,
    as_Undo,
    as_Update,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor, as_Person
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview
from vultron.wire.as2.vocab.objects.case_status import as_CaseStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

_ACTOR_URI = "https://example.org/actors/alice"
_CASE_URI = "https://example.org/cases/case-001"
_TARGET_URI = "https://example.org/actors/bob"
_CASE_ACTOR_URI = "https://example.org/actors/case-actor"


@pytest.fixture
def sample_case() -> as_VulnerabilityCase:
    return make(
        as_VulnerabilityCase, attributed_to=CASE_OWNER_ID, name="Test Case"
    )


@pytest.fixture
def sample_report() -> as_VulnerabilityReport:
    return make(as_VulnerabilityReport, name="Test Report")


@pytest.fixture
def sample_status() -> as_CaseStatus:
    # ``context`` is required on the core class (fail-fast, ARCH-10-001); the
    # deleted wire class allowed it absent (ARCH-12-002 leniency).
    return make(
        as_CaseStatus, context="https://example.org/cases/case-factories-01"
    )


@pytest.fixture
def sample_note() -> as_Note:
    return make(as_Note, content="Test note content")


@pytest.fixture
def sample_actor() -> as_Person:
    return make(as_Person, name="Alice", id_=_ACTOR_URI)


@pytest.fixture
def sample_offer(sample_case) -> as_Offer:
    """OfferCaseOwnershipTransferActivity — used for Accept/Reject tests."""
    return offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )


@pytest.fixture
def sample_proposal(sample_case) -> as_Offer:
    """The owner's ownership-transfer proposal — used for Undo tests."""
    return propose_case_ownership_transfer_activity(
        sample_case, target=_TARGET_URI, actor=_ACTOR_URI, at=authored_at()
    )


def _invitable_case() -> as_VulnerabilityCase:
    """The case a stub Invite is built from: it carries a ``stub_summary``."""
    return make(
        as_VulnerabilityCase,
        id_=_CASE_URI,
        name="Test Case",
        stub_summary="A case to join",
        attributed_to=CASE_OWNER_ID,
    )


@pytest.fixture
def sample_invite(sample_actor) -> as_Invite:
    """RmInviteToCaseActivity — used for Accept/Reject invite tests."""
    return rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )


# ---------------------------------------------------------------------------
# add_report_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_report_to_case_returns_add(sample_report):
    result = add_report_to_case_activity(
        report=sample_report, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Add)


def test_add_report_to_case_object_is_report(sample_report):
    result = add_report_to_case_activity(
        report=sample_report, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_report


def test_add_report_to_case_target_is_set(sample_report):
    result = add_report_to_case_activity(
        report=sample_report,
        target=_CASE_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_report_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_report_to_case_activity(
            report="not-a-report",  # type: ignore[arg-type]
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_status_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_status_to_case_returns_add(sample_status):
    result = add_status_to_case_activity(
        status=sample_status,
        case=_CASE_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert isinstance(result, as_Add)


def test_add_status_to_case_object_is_status(sample_status):
    result = add_status_to_case_activity(
        status=sample_status,
        case=_CASE_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.object_ == sample_status


@pytest.mark.spec("VAM-08-002")
def test_add_status_to_case_targets_its_status_history(sample_status):
    """ADR-0204: the target is <case>/statuses, the context the case."""
    result = add_status_to_case_activity(
        status=sample_status,
        case=_CASE_URI,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == f"{_CASE_URI}/statuses"
    assert result.context == _CASE_URI


def test_add_status_to_case_refuses_another_cases_context(sample_status):
    """The case's status joins its own case's history, not another's."""
    with pytest.raises(VultronActivityConstructionError):
        add_status_to_case_activity(
            status=sample_status,
            case=_CASE_URI,
            context="https://example.org/cases/other",
            actor=_ACTOR_URI,
            at=authored_at(),
        )


def test_add_status_to_case_without_a_case_raises(sample_status):
    with pytest.raises(VultronActivityConstructionError):
        add_status_to_case_activity(
            status=sample_status, case="", actor=_ACTOR_URI, at=authored_at()
        )


@pytest.mark.spec("AF-04-001")
def test_add_status_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_status_to_case_activity(
            status="not-a-status",  # type: ignore[arg-type]
            case=_CASE_URI,
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# create_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_create_case_returns_create(sample_case):
    result = create_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Create)


def test_create_case_object_is_case(sample_case):
    result = create_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_case


def test_create_case_kwargs_forwarded(sample_case):
    result = create_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.actor == _ACTOR_URI


@pytest.mark.spec("AF-04-001")
def test_create_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        create_case_activity(case="not-a-case", at=authored_at())  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# add_note_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_add_note_to_case_returns_add(sample_note):
    result = add_note_to_case_activity(
        note=sample_note, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Add)


def test_add_note_to_case_object_is_note(sample_note):
    result = add_note_to_case_activity(
        note=sample_note, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_note


def test_add_note_to_case_target_is_set(sample_note):
    result = add_note_to_case_activity(
        note=sample_note, target=_CASE_URI, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.target == _CASE_URI


@pytest.mark.spec("AF-04-001")
def test_add_note_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_note_to_case_activity(note=42, at=authored_at())  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# update_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_update_case_returns_update(sample_case):
    result = update_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Update)


def test_update_case_object_is_case(sample_case):
    result = update_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_update_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        update_case_activity(case="not-a-case", at=authored_at())  # type: ignore[arg-type]
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_engage_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_engage_case_returns_join(sample_case):
    result = rm_engage_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Join)


@pytest.mark.spec("AKM-03-004")
def test_rm_engage_case_object_names_the_case(sample_case):
    """The case travels as its typed reference, never a copy (ADR-0165)."""
    result = rm_engage_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == case_reference(sample_case.id_)


@pytest.mark.spec("AKM-03-004")
def test_rm_engage_case_takes_the_case_id(sample_case):
    """Given only the case id, the factory names the same case."""
    by_id = rm_engage_case_activity(
        case=sample_case.id_, actor=_ACTOR_URI, at=authored_at()
    )
    held = rm_engage_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert by_id.object_ == held.object_


@pytest.mark.spec("AF-04-001")
def test_rm_engage_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_engage_case_activity(case="", at=authored_at())
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_defer_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_defer_case_returns_ignore(sample_case):
    result = rm_defer_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Ignore)


@pytest.mark.spec("AKM-03-004")
def test_rm_defer_case_object_names_the_case(sample_case):
    """The case travels as its typed reference, never a copy (ADR-0165)."""
    result = rm_defer_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == case_reference(sample_case.id_)


@pytest.mark.spec("AKM-03-004")
def test_rm_defer_case_takes_the_case_id(sample_case):
    """Given only the case id, the factory names the same case."""
    by_id = rm_defer_case_activity(
        case=sample_case.id_, actor=_ACTOR_URI, at=authored_at()
    )
    held = rm_defer_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert by_id.object_ == held.object_


@pytest.mark.spec("AF-04-001")
def test_rm_defer_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_defer_case_activity(case="", at=authored_at())
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_close_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_close_case_returns_leave(sample_case):
    result = rm_close_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Leave)


@pytest.mark.spec("AKM-03-004")
def test_rm_close_case_object_names_the_case(sample_case):
    """The case travels as its typed reference, never a copy (ADR-0165)."""
    result = rm_close_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == case_reference(sample_case.id_)


@pytest.mark.spec("AKM-03-004")
def test_rm_close_case_takes_the_case_id(sample_case):
    """Given only the case id, the factory names the same case."""
    by_id = rm_close_case_activity(
        case=sample_case.id_, actor=_ACTOR_URI, at=authored_at()
    )
    held = rm_close_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert by_id.object_ == held.object_


@pytest.mark.spec("AF-04-001")
def test_rm_close_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_close_case_activity(case="", at=authored_at())
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# offer_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_offer_ownership_transfer_returns_offer(sample_case):
    result = offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Offer)


@pytest.mark.spec("AKM-03-004")
def test_offer_ownership_transfer_object_names_the_case(sample_case):
    """The case travels as its typed reference, never a copy (ADR-0165)."""
    result = offer_case_ownership_transfer_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == case_reference(sample_case.id_)


def test_offer_ownership_transfer_target_is_set(sample_case, sample_actor):
    result = offer_case_ownership_transfer_activity(
        case=sample_case,
        target=sample_actor,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == sample_actor


@pytest.mark.spec("DL-08-003")
def test_offer_ownership_transfer_wraps_a_bare_transferee_id(sample_case):
    """A transferee named by URI travels inline as an Actor (#4843)."""
    transferee = "https://example.org/actors/transferee"
    result = offer_case_ownership_transfer_activity(
        case=sample_case, target=transferee, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result.target, as_Actor)
    assert result.target.id_ == transferee
    wire = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert wire["target"]["id"] == transferee


@pytest.mark.spec("AF-04-001")
def test_offer_ownership_transfer_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        offer_case_ownership_transfer_activity(case="", at=authored_at())
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# accept_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("RF-02-001")
def test_accept_ownership_transfer_returns_accept(sample_offer):
    result = accept_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Accept)
    assert result.type_ == "Accept"


def test_accept_ownership_transfer_object_is_offer(sample_offer):
    result = accept_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_offer


@pytest.mark.spec("AF-04-001")
def test_accept_ownership_transfer_plain_offer_raises(sample_report):
    """A plain as_Offer (not from offer_case_ownership_transfer_activity) must fail."""
    plain_offer = make(as_Offer, actor=_ACTOR_URI, object_=sample_report)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        accept_case_ownership_transfer_activity(
            offer=plain_offer, at=authored_at()
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# reject_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("RF-03-001")
def test_reject_ownership_transfer_returns_reject(sample_offer):
    result = reject_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Reject)
    assert result.type_ == "Reject"


def test_reject_ownership_transfer_object_is_offer(sample_offer):
    result = reject_case_ownership_transfer_activity(
        offer=sample_offer, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_offer


@pytest.mark.spec("AF-04-001")
def test_reject_ownership_transfer_plain_offer_raises(sample_report):
    plain_offer = make(as_Offer, actor=_ACTOR_URI, object_=sample_report)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        reject_case_ownership_transfer_activity(
            offer=plain_offer, at=authored_at()
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# undo_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("CM-21-015")
def test_undo_ownership_transfer_returns_undo(sample_proposal):
    result = undo_case_ownership_transfer_activity(
        proposal=sample_proposal, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Undo)


def test_undo_ownership_transfer_object_is_the_proposal(sample_proposal):
    result = undo_case_ownership_transfer_activity(
        proposal=sample_proposal, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_proposal


@pytest.mark.spec("AF-04-001")
def test_undo_ownership_transfer_plain_offer_raises(sample_offer):
    """The Offer itself is not withdrawn; the owner's proposal is (ADR-0148)."""
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        undo_case_ownership_transfer_activity(
            proposal=sample_offer, at=authored_at()
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# propose_case_ownership_transfer_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-21-005")
@pytest.mark.spec("CM-21-016")
@pytest.mark.spec("CM-21-025")
def test_proposal_nests_the_offer_the_case_manager_will_make(sample_case):
    """Offer(Offer(VulnerabilityCase)), context the case: the inner Offer names
    the case, the transferee and the deadline (ADR-0148)."""
    deadline = FAR_FUTURE  # far-future; tests round-trip, not a specific value
    result = propose_case_ownership_transfer_activity(
        sample_case,
        target=_TARGET_URI,
        end_time=deadline,
        actor=_ACTOR_URI,
        to=[_CASE_ACTOR_URI],
        at=authored_at(),
    )

    assert isinstance(result, as_Offer)
    assert result.context == sample_case.id_
    inner = result.object_
    assert isinstance(inner, as_Offer)
    assert inner.object_ == case_reference(sample_case.id_)
    assert isinstance(inner.target, as_Actor)
    assert inner.target.id_ == _TARGET_URI
    assert inner.end_time == deadline
    assert result.end_time is None


# ---------------------------------------------------------------------------
# rm_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_rm_invite_to_case_returns_invite(sample_actor):
    result = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert isinstance(result, as_Invite)


def test_rm_invite_to_case_target_is_the_invitee(sample_actor):
    result = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.target == sample_actor


@pytest.mark.spec("CM-11-013")
@pytest.mark.spec("VAM-04-004")
def test_rm_invite_to_case_object_is_the_previewed_case_reference(
    sample_actor,
):
    """The object names the case by its id and carries its preview, the
    stub; ``context`` is the case (ADR-0205)."""
    result = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    wire = json.loads(result.model_dump_json(by_alias=True, exclude_none=True))
    assert wire["object"]["type"] == "VulnerabilityCase"
    assert wire["object"]["id"] == _CASE_URI
    assert wire["object"]["preview"]["type"] == "CasePreview"
    assert "caseId" not in wire["object"]["preview"]
    assert wire["context"] == _CASE_URI


@pytest.mark.spec("AF-04-001")
@pytest.mark.spec("CM-17-010")
def test_stub_invite_refuses_a_bare_case_uri(sample_actor):
    """A case named by URI alone gives the factory no preview to build, so
    the stub Invite is refused rather than sent without one (ADR-0205)."""
    with pytest.raises(VultronActivityConstructionError, match="ADR-0205"):
        rm_invite_to_case_activity(
            invitee=sample_actor,
            case=_CASE_URI,  # type: ignore[arg-type]
            actor=_ACTOR_URI,
            at=authored_at(),
        )


def _invite_stub_wire(sample_actor) -> dict:
    """The serialised stub an Invite carries for a case with no embargo.

    The case holds content of every kind the preview withholds: its own
    ``summary`` and ``content``, a report, a note and a reference.
    """
    case = make(
        as_VulnerabilityCase,
        id_=_CASE_URI,
        name="CVE-2025-0001 in widget",
        summary="A summary of the case",
        content="The full write-up the invitee must not see",
        stub_summary="RCE in widget — details withheld pending disclosure",
        attributed_to=_ACTOR_URI,
        vulnerability_reports=["https://example.org/reports/r1"],
        notes=["https://example.org/notes/n1"],
        case_references=["https://example.org/references/ref1"],
    )
    result = rm_invite_to_case_activity(
        invitee=sample_actor, case=case, actor=_ACTOR_URI, at=authored_at()
    )
    wire = json.loads(result.model_dump_json(by_alias=True, exclude_none=True))
    stub: dict[str, Any] = wire["object"]["preview"]
    return stub


#: What the stub shows of a case that holds a value in each withheld field.
_REDACTED_CONTENT = (
    "content",
    "vulnerabilityReports",
    "notes",
    "caseReferences",
)


@pytest.mark.spec("MV-12-004")
@pytest.mark.spec("CM-17-005")
def test_rm_invite_stub_marks_the_case_content_it_withholds(sample_actor):
    """Each withheld value the case holds is marked, never sent.

    The case's own ``summary`` gives way to the stub summary, and its
    content, reports, notes and references each travel as one ``Redacted``
    marker: the invitee learns they exist and sees none of them
    (MV-12-004).  A field the case holds no value for is left out, not
    marked: the case here has no participants beyond its default, no
    parent case and no ``tag``.
    """
    stub = _invite_stub_wire(sample_actor)
    assert stub["summary"] != "A summary of the case"
    for key in _REDACTED_CONTENT:
        assert stub[key] == {"type": "Redacted"}, key
    assert "The full write-up" not in json.dumps(stub)
    for key in ("parentCases", "childCases", "siblingCases", "tag"):
        assert key not in stub, key


@pytest.mark.spec("CM-17-010")
def test_rm_invite_stub_shows_the_owner_name_and_status(sample_actor):
    """The stub shows its summary, the Case Owner, the case name and its
    current status beside its identity (CM-17-010, CM-17-013)."""
    stub = _invite_stub_wire(sample_actor)
    assert isinstance(stub["summary"], str)
    assert stub["summary"].strip()
    assert stub["attributedTo"] == _ACTOR_URI
    assert stub["name"] == "CVE-2025-0001 in widget"
    assert [status["type"] for status in stub["caseStatuses"]] == [
        "CaseStatus"
    ]
    assert "embargoRegister" not in stub


@pytest.mark.spec("CM-17-020")
@pytest.mark.spec("CM-17-010")
def test_rm_invite_to_case_refuses_when_no_stub_summary():
    """The factory refuses when the case carries no ``stub_summary`` (CM-17-010, AC-2).

    The case owner MUST set ``stub_summary`` before emitting a stub Invite;
    the factory raises rather than silently falling back to the case name or
    any other default.
    """
    case = make(
        as_VulnerabilityCase,
        id_=_CASE_URI,
        name="CVE-2025-0001 in widget",
        summary="A summary of the case",
        attributed_to=_ACTOR_URI,
        # stub_summary intentionally absent
    )
    with pytest.raises(VultronActivityConstructionError, match="stub_summary"):
        rm_invite_to_case_activity(
            invitee=_ACTOR_URI,
            case=case,
            actor=_ACTOR_URI,
            at=authored_at(),
        )


@pytest.mark.spec("AF-04-001")
def test_rm_invite_to_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_invite_to_case_activity(
            invitee=["not-an-actor"],  # type: ignore[arg-type]
            case=_invitable_case(),
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# rm_accept_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("RF-02-001")
def test_rm_accept_invite_to_case_returns_accept(sample_actor):
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_accept_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Accept)
    assert result.type_ == "Accept"


def test_rm_accept_invite_to_case_object_is_invite(sample_actor):
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_accept_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == invite


@pytest.mark.spec("RF-08-001")
@pytest.mark.spec("RF-08-002")
@pytest.mark.spec("RF-08-003")
def test_rm_accept_invite_to_case_in_reply_to_auto_set(sample_actor):
    """Model validator auto-populates in_reply_to from invite.id_."""
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_accept_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.in_reply_to == invite.id_


def test_rm_accept_invite_to_case_explicit_in_reply_to_preserved(sample_actor):
    """Explicitly provided in_reply_to is not overwritten."""
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    explicit_id = "https://example.org/activities/explicit-invite-id"
    result = rm_accept_invite_to_case_activity(
        invite=invite,
        in_reply_to=explicit_id,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.in_reply_to == explicit_id


@pytest.mark.spec("AF-04-001")
def test_rm_accept_invite_to_case_plain_invite_raises(sample_actor):
    """A plain as_Invite (not from rm_invite_to_case_activity) must fail."""
    plain_invite = make(as_Invite, actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_accept_invite_to_case_activity(
            invite=plain_invite, at=authored_at()
        )
    assert exc_info.value.__cause__ is not None


def _received(activity: Any, **extra: object) -> Any:
    """*activity* as a receiver parses it from the body its sender sent.

    *extra* adds keys to that body, as a sender that names more than this
    receiver's vocabulary would.  The body is signed by its author, as its
    sender's outbox signs it (SIG-01-001), after *extra* is added, so the
    proof covers what was sent.
    """
    body = activity.model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )
    body.update(extra)
    return parse_activity(signed_body(body))


def _embedded(reply: BaseModel) -> dict[str, Any]:
    """The answered activity in *reply*'s outbound body."""
    body: dict[str, Any] = json.loads(
        reply.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
    )
    embedded: dict[str, Any] = body["object"]
    return embedded


@pytest.mark.spec("DL-06-004")
@pytest.mark.parametrize(
    "factory",
    [rm_accept_invite_to_case_activity, rm_reject_invite_to_case_activity],
)
def test_reply_embeds_an_invite_as_its_sender_sent_it(sample_actor, factory):
    """A received Invite is parsed from the body intake archived; the reply
    validates it into the case-Invite class and embeds the body verbatim,
    keys no vocabulary names included (ADR-0149)."""
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        actor=_ACTOR_URI,
        case=_invitable_case(),
        roles=["vendor"],
        at=authored_at(),
    )
    held = _received(invite, fooBar=[1])
    assert type(held) is as_Invite

    result = factory(invite=held, actor=_ACTOR_URI, at=authored_at())

    assert result.object_.id_ == invite.id_
    assert result.object_.roles == ["vendor"]
    assert result.in_reply_to == invite.id_
    assert _embedded(result) == held.received_evidence


@pytest.mark.parametrize(
    "factory",
    [rm_accept_invite_to_case_activity, rm_reject_invite_to_case_activity],
)
def test_reply_refuses_a_received_activity_that_is_not_an_invite(
    sample_actor, factory
):
    from vultron.wire.as2.factories import recommend_actor_activity

    offer = recommend_actor_activity(
        sample_actor,
        target=make(
            as_VulnerabilityCase,
            attributed_to=CASE_OWNER_ID,
            id_="https://example.org/cases/c1",
            name="Case",
        ),
        actor=_ACTOR_URI,
        at=authored_at(),
    )

    with pytest.raises(
        VultronActivityConstructionError, match="not a case Invite"
    ):
        factory(invite=_received(offer), actor=_ACTOR_URI, at=authored_at())


# ---------------------------------------------------------------------------
# rm_reject_invite_to_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
@pytest.mark.spec("RF-03-001")
def test_rm_reject_invite_to_case_returns_reject(sample_actor):
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_reject_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Reject)
    assert result.type_ == "Reject"


def test_rm_reject_invite_to_case_object_is_invite(sample_actor):
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_reject_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == invite


@pytest.mark.spec("RF-08-001")
@pytest.mark.spec("RF-08-002")
@pytest.mark.spec("RF-08-003")
def test_rm_reject_invite_to_case_in_reply_to_auto_set(sample_actor):
    """Model validator auto-populates in_reply_to from invite.id_."""
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    result = rm_reject_invite_to_case_activity(
        invite=invite, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.in_reply_to == invite.id_


def test_rm_reject_invite_to_case_explicit_in_reply_to_preserved(sample_actor):
    """Explicitly provided in_reply_to is not overwritten."""
    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=_invitable_case(),
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    explicit_id = "https://example.org/activities/explicit-invite-id"
    result = rm_reject_invite_to_case_activity(
        invite=invite,
        in_reply_to=explicit_id,
        actor=_ACTOR_URI,
        at=authored_at(),
    )
    assert result.in_reply_to == explicit_id


@pytest.mark.spec("AF-04-001")
def test_rm_reject_invite_to_case_plain_invite_raises(sample_actor):
    plain_invite = make(as_Invite, actor=_ACTOR_URI, object_=sample_actor)
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        rm_reject_invite_to_case_activity(
            invite=plain_invite, at=authored_at()
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# announce_vulnerability_case_activity
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-01-002")
def test_announce_vulnerability_case_returns_announce(sample_case):
    result = announce_vulnerability_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert isinstance(result, as_Announce)


def test_announce_vulnerability_case_object_is_case(sample_case):
    result = announce_vulnerability_case_activity(
        case=sample_case, actor=_ACTOR_URI, at=authored_at()
    )
    assert result.object_ == sample_case


@pytest.mark.spec("AF-04-001")
def test_announce_vulnerability_case_invalid_raises():
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        announce_vulnerability_case_activity(
            case="not-a-case",  # type: ignore[arg-type]
            at=authored_at(),
        )
    assert exc_info.value.__cause__ is not None


# ---------------------------------------------------------------------------
# __init__.py re-exports (AF-04-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("AF-04-002")
def test_all_case_factories_importable_from_package():
    """All case factory functions must be importable from the factories package."""
    from vultron.wire.as2.factories import (  # noqa: F401
        accept_case_ownership_transfer_activity,
        add_note_to_case_activity,
        add_report_to_case_activity,
        add_status_to_case_activity,
        announce_vulnerability_case_activity,
        create_case_activity,
        offer_case_ownership_transfer_activity,
        reject_case_ownership_transfer_activity,
        rm_accept_invite_to_case_activity,
        rm_close_case_activity,
        rm_defer_case_activity,
        rm_engage_case_activity,
        rm_invite_to_case_activity,
        rm_reject_invite_to_case_activity,
        undo_case_ownership_transfer_activity,
        update_case_activity,
    )


# ---------------------------------------------------------------------------
# CM-17-002: the Invite stub is enriched from a case whose embargo is inline
# ---------------------------------------------------------------------------


@pytest.mark.spec("CM-17-002")
def test_rm_invite_stub_is_enriched_from_an_inline_active_embargo(
    sample_actor,
):
    """A case seeded from a sealed Announce carries ``active_embargo`` as the
    ``EmbargoEvent`` object, not its id.  The stub must still carry the embargo,
    its id and end time included — and needs no separate ``embargo_obj`` when
    the case already holds the object."""
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_status import CaseStatus
    from vultron.core.models.dimensions import EmDimension
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.states.em import EM
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    case_id = "https://example.org/cases/inline-embargo"
    embargo = make(EmbargoEvent, context=case_id, end_time=days_from_now(30))
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="CVE-2025-010",
        stub_summary="Memory corruption under embargo",
        attributed_to="https://example.org/actors/coordinator",
        case_statuses=[
            make(
                CaseStatus,
                context=case_id,
                attributed_to="https://example.org/actors/coordinator",
                em=EmDimension(state=EM.ACTIVE),
            )
        ],
        embargo_register=register(active=embargo),
    )

    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=case,
        actor="https://example.org/actors/coordinator",
        at=authored_at(),
    )

    reference = invite.object_
    assert isinstance(reference, as_TypedReference)
    assert reference.id_ == case_id
    stub = reference.preview
    assert isinstance(stub, as_CasePreview)
    # A preview holds its contents in loose forms (ADR-0217); the embargo is
    # shown whole, every term as the inviter holds it (CM-17-011).
    shown = preview_in_force_embargo(stub)
    assert is_loose_form_of(shown, as_EmbargoEvent)
    expected = case.active_embargo
    assert expected is not None and _as2(shown) == _as2(expected)
    assert getattr(shown, "status", None) == "ACTIVE"
    assert is_loose_form_of(preview_current_status(stub), as_CaseStatus)
    assert preview_em_state(stub) is EM.ACTIVE


@pytest.mark.spec("CM-17-013")
@pytest.mark.spec("CM-17-002")
def test_enriched_stub_carries_the_current_status_and_in_force_entry(
    sample_actor,
):
    """An embargo-active stub shows the case's current status whole and its
    register reduced to the in-force entry.

    The case here is public with an exploit (``PXa``).  The stub shows the
    case's own current status, so its ``pxaState`` is the case's, not a
    class default that would tell the invitee the case is not public.  The
    dump goes through the outbound form, the subtype-aware JSON dump
    (VM-07-001).
    """
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_status import CaseStatus
    from vultron.core.models.dimensions import EmDimension, PxaDimension
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.states.cs import CS_pxa
    from vultron.core.states.em import EM

    case_id = "https://example.org/cases/enriched-stub"
    embargo = make(EmbargoEvent, context=case_id, end_time=days_from_now(30))
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="CVE-2025-011",
        summary="Case content the invitee must not see",
        stub_summary="Vulnerability under active embargo",
        attributed_to=_ACTOR_URI,
        case_statuses=[
            make(
                CaseStatus,
                context=case_id,
                attributed_to=_ACTOR_URI,
                em=EmDimension(state=EM.ACTIVE),
                pxa=PxaDimension(state=CS_pxa.PXa),
            )
        ],
        embargo_register=register(active=embargo),
    )

    invite = rm_invite_to_case_activity(
        invitee=sample_actor, case=case, actor=_ACTOR_URI, at=authored_at()
    )
    wire = json.loads(
        invite.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
    )

    stub = wire["object"]["preview"]
    # The stub summary stands for the case's own (CM-17-020).
    assert stub["summary"] == "Vulnerability under active embargo"
    (status,) = stub["caseStatuses"]
    held = json.loads(
        case.current_status.model_dump_json(by_alias=True, exclude_none=True)
    )
    del held["@context"]  # nested: VM-10-004
    assert status == held
    assert status["emState"] == EM.ACTIVE.value
    assert status["pxaState"] == CS_pxa.PXa.name
    (entry,) = stub["embargoRegister"]
    assert entry["status"] == "ACTIVE"
    assert entry["id"] == embargo.id_
    assert "activeEmbargo" not in stub
    assert "caseStatus" not in stub


@pytest.mark.spec("CM-17-014")
@pytest.mark.spec("CM-17-002")
def test_revise_stub_carries_the_embargo_in_force_not_the_revision(
    sample_actor,
):
    """In EM ``REVISE`` the prior embargo stays in force (EP-05-002) and
    accepting the stub binds the invitee to it (CM-11-001), so the stub
    carries that embargo and ``emState=REVISE``.  The open revision is not
    yet binding and stays out of the stub; EP-09-011 relays it after
    joining."""
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    case_id = "https://example.org/cases/revise-stub"
    in_force = make(EmbargoEvent, context=case_id, end_time=days_from_now(30))
    revision = make(EmbargoEvent, context=case_id, end_time=days_from_now(60))
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="CVE-2025-013",
        stub_summary="Vulnerability under a revised embargo",
        attributed_to=_ACTOR_URI,
        case_statuses=[
            make(
                CaseStatus,
                context=case_id,
                attributed_to=_ACTOR_URI,
                em=EmDimension(state=EM.REVISE),
            )
        ],
        embargo_register=register(active=in_force, proposed=[revision]),
    )
    assert case.em_state == EM.REVISE

    invite = rm_invite_to_case_activity(
        invitee=sample_actor, case=case, actor=_ACTOR_URI, at=authored_at()
    )

    reference = invite.object_
    assert isinstance(reference, as_TypedReference)
    stub = reference.preview
    assert isinstance(stub, as_CasePreview)
    assert is_loose_form_of(preview_in_force_embargo(stub), as_EmbargoEvent)
    assert preview_embargo_id(stub) == in_force.id_
    # The register is reduced to the in-force entry: the revision is not in
    # it (CM-17-014).
    shown_register = stub.embargo_register
    assert isinstance(shown_register, list)
    assert [preview_embargo_id(stub)] == [
        getattr(shown, "id_", None) for shown in shown_register
    ]
    assert is_loose_form_of(preview_current_status(stub), as_CaseStatus)
    assert preview_em_state(stub) is EM.REVISE


@pytest.mark.spec("CM-17-002")
@pytest.mark.parametrize(
    ("entry", "em_state"),
    [("proposed", EM.PROPOSED), ("terminated", EM.EXITED)],
    ids=["proposal-only", "embargo-ended"],
)
def test_no_embargo_in_force_leaves_the_stub_bare(
    sample_actor, entry, em_state
):
    """With no embargo in force the stub carries no terms.

    The stub is enriched from the register's ``ACTIVE`` entry, not from any
    entry: a proposal (EM ``PROPOSED``) binds nobody yet, and an ended embargo
    (EM ``EXITED``) binds nobody any more (CM-17-002, CM-17-010).
    """

    case_id = f"https://example.org/cases/{entry}-stub"
    embargo = _full_embargo(case_id)
    entries = (
        register(proposed=[embargo])
        if entry == "proposed"
        else register(terminated=embargo)
    )
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="CVE-2025-014",
        stub_summary="Vulnerability with no embargo in force",
        attributed_to=_ACTOR_URI,
        embargo_register=entries,
    )
    assert case.em_state == em_state

    invite = rm_invite_to_case_activity(
        invitee=sample_actor,
        case=case,
        actor=_ACTOR_URI,
        at=authored_at(),
    )

    reference = invite.object_
    assert isinstance(reference, as_TypedReference)
    stub = reference.preview
    assert isinstance(stub, as_CasePreview)
    assert stub.embargo_register is None
    assert preview_em_state(stub) is em_state


#: An embargo in force: EM ``ACTIVE``, or ``REVISE`` with a revision open.
_IN_FORCE_EM = pytest.mark.parametrize(
    "revising", [False, True], ids=["em-active", "em-revise"]
)


def _embargo_active_case(
    case_id: str,
    active_embargo: EmbargoEvent,
    *,
    revising: bool = False,
) -> VulnerabilityCase:
    """A case with *active_embargo* in force.

    EM is ``ACTIVE``, or ``REVISE`` when *revising* adds an open revision.
    """
    em_state = EM.REVISE if revising else EM.ACTIVE
    revisions = (
        [make(EmbargoEvent, context=case_id, end_time=days_from_now(90))]
        if revising
        else []
    )
    case = make(
        VulnerabilityCase,
        id_=case_id,
        name="CVE-2025-012",
        stub_summary="Vulnerability under active embargo",
        attributed_to=_ACTOR_URI,
        case_statuses=[
            make(
                CaseStatus,
                context=case_id,
                attributed_to=_ACTOR_URI,
                em=EmDimension(state=em_state),
            )
        ],
        embargo_register=register(active=active_embargo, proposed=revisions),
    )
    assert case.em_state == em_state
    return case


def _full_embargo(case_id: str) -> EmbargoEvent:
    """An embargo carrying every term a sender may set, not just its window."""
    return make(
        EmbargoEvent,
        context=case_id,
        name="Coordinated embargo for widget RCE",
        summary="Disclose together once the vendor ships the fix",
        attributed_to=_ACTOR_URI,
        start_time=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        end_time=datetime(2099, 6, 7, 8, 9, 10, tzinfo=UTC),
    )


@pytest.mark.spec("CM-17-011")
@_IN_FORCE_EM
def test_rm_invite_stub_embeds_the_full_active_embargo(sample_actor, revising):
    """The stub carries the whole embargo, not just its id and end time.

    The prototype builds no way for the invitee to ask the inviter for the
    embargo by id, so the stub embeds it (CM-17-011).  Every term the
    registered embargo holds reaches the wire unchanged — its sender-set
    start, name, summary and author included — with its own status
    (ADR-0202), rather than a rebuilt copy that keeps only the end time and
    mints a fresh start.
    """
    case_id = "https://example.org/cases/full-embargo"
    embargo = _full_embargo(case_id)
    case = _embargo_active_case(case_id, embargo, revising=revising)

    invite = rm_invite_to_case_activity(
        invitee=sample_actor, case=case, actor=_ACTOR_URI, at=authored_at()
    )
    wire = json.loads(
        invite.model_dump_json(
            by_alias=True, exclude_none=True, serialize_as_any=True
        )
    )

    active = case.active_embargo
    assert active is not None
    expected = json.loads(
        active.model_dump_json(by_alias=True, exclude_none=True)
    )
    del expected["@context"]  # nested: VM-10-004
    (shown,) = wire["object"]["preview"]["embargoRegister"]
    assert shown == expected
    assert shown["status"] == "ACTIVE"


@pytest.mark.spec("CM-11-001")
def test_stub_invite_factory_docstrings_do_not_label_the_stub_replies_as_rm_replies():
    """The stub Invite and its replies are not RV/RI messages (CM-11-001, CM-11-007).

    Accepting the stub is joining; the RV/RI/RC replies belong to the full-case
    Invite.
    """
    from vultron.wire.as2.factories import case as case_factories

    accept = case_factories.rm_accept_invite_to_case_activity.__doc__ or ""
    reject = case_factories.rm_reject_invite_to_case_activity.__doc__ or ""
    stub = case_factories.rm_invite_to_case_activity.__doc__ or ""

    assert "stub Invite" in stub.splitlines()[0]
    assert "RV message" not in accept.splitlines()[0]
    assert "join" in accept.splitlines()[0]
    assert "RI message" not in reject.splitlines()[0]
    assert "(RC)" in reject.splitlines()[0]
    full = case_factories.rm_accept_full_case_invite_activity.__doc__ or ""
    assert "RV" in full.splitlines()[0]


@pytest.mark.spec("DL-06-004")
@pytest.mark.parametrize(
    "factory",
    [
        accept_case_ownership_transfer_activity,
        reject_case_ownership_transfer_activity,
    ],
)
def test_ownership_reply_embeds_the_offer_as_its_sender_sent_it(factory):
    """A received ownership Offer, parsed from its archived body, is
    validated into the Offer class the reply embeds, and embedded as the
    body that arrived: its answer deadline and ``cc`` included (ADR-0149)."""
    case = make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_="https://example.org/cases/c1",
        name="C",
    )
    offer = offer_case_ownership_transfer_activity(
        case,
        target=_ACTOR_URI,
        actor=_ACTOR_URI,
        to=[_ACTOR_URI],
        at=authored_at(),
    )
    received = _received(
        offer,
        endTime="2031-01-01T00:00:00+00:00",
        cc=["https://example.org/actors/watcher"],
    )

    result = factory(offer=received, actor=_ACTOR_URI, at=authored_at())

    assert result.object_.id_ == offer.id_
    assert result.object_.object_.id_ == case.id_
    embedded = _embedded(result)
    assert embedded == received.received_evidence
    assert embedded["endTime"] == "2031-01-01T00:00:00+00:00"
    assert embedded["cc"] == ["https://example.org/actors/watcher"]


@pytest.mark.spec("AF-04-001")
@pytest.mark.parametrize(
    "factory",
    [
        accept_case_ownership_transfer_activity,
        reject_case_ownership_transfer_activity,
    ],
)
def test_ownership_reply_refuses_a_received_offer_of_another_kind(
    sample_report, factory
):
    """A received ``Offer(VulnerabilityReport)`` is not an ownership-transfer Offer."""
    from vultron.wire.as2.factories import rm_submit_report_activity

    offer = rm_submit_report_activity(
        sample_report, to=_ACTOR_URI, actor=_ACTOR_URI, at=authored_at()
    )

    with pytest.raises(VultronActivityConstructionError) as exc_info:
        factory(offer=_received(offer), actor=_ACTOR_URI, at=authored_at())
    cause = exc_info.value.__cause__
    # as_answered's validation of the parsed Offer refused it.
    assert isinstance(cause, ValidationError)
    assert cause.title == "_OfferCaseOwnershipTransferActivity"


def _as2(obj: object) -> object:
    """*obj*'s AS2 form, without the top-level ``@context``."""
    assert isinstance(obj, BaseModel)
    dumped = obj.model_dump(by_alias=True, exclude_none=True, mode="json")
    dumped.pop("@context", None)
    return dumped
