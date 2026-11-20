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

"""A case stub is recognised by its ``type`` alone (CM-11-038, #4045).

The parser used to recognise a stub as a ``VulnerabilityCase`` whose keys all
fell in a list derived from the stub class (#2624), so a sparse full case and
a stub had the same shape.  The stub names itself ``CasePreview``
and is the case's preview: the case reference that carries it names the case
by its own ``id``, so the stub carries no case id and no ID derived from the
case's (ADR-0205).  A ``VulnerabilityCase`` is a case however few keys it
has.
"""

import json
from pathlib import Path
from typing import Any, cast

import pytest

from test.support.case_owner import CASE_OWNER_ID, INBOUND_CASE_OWNERSHIP
from test.support.future_dates import days_from_now
from test.support.objects import with_times
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_preview import (
    preview_current_status,
    preview_em_state,
    preview_embargo_id,
)
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.preview_object import is_loose_form_of
from vultron.core.states.em import EM
from vultron.wire.as2.errors import (
    VultronParseValidationError,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import (
    as_TypedReference,
    is_case_reference,
)
from vultron.wire.as2.unknown_keys import (
    resolve_inline_class as _inline_vocab_class,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Invite
from vultron.wire.as2.vocab.objects.case_preview import as_CasePreview

_EXAMPLES = Path(__file__).resolve().parents[3] / "docs/reference/examples"
_CASE_ID = "https://example.org/cases/case-stub"
_PREVIEW_ID = "urn:uuid:case-stub-preview"
_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"


def _enriched_stub() -> dict:
    return {
        "@context": "https://certcc.github.io/Vultron/ns/context.jsonld",
        "type": "CasePreview",
        "attributedTo": "https://example.org/actors/vendor",
        "id": _PREVIEW_ID,
        "summary": "Security issue — embargo active, details shared after acceptance",
        "embargoRegister": [
            {
                "type": "EmbargoEvent",
                "published": "2026-01-01T00:00:00+00:00",
                "id": f"{_CASE_ID}/embargoes/e0",
                "context": _CASE_ID,
                "endTime": days_from_now(30).isoformat(),
                "status": "ACTIVE",
            }
        ],
        "caseStatuses": [
            {
                "type": "CaseStatus",
                "id": f"{_CASE_ID}/statuses/1",
                "context": _CASE_ID,
                "published": "2026-01-01T00:00:00+00:00",
                "em": "ACTIVE",
            }
        ],
    }


@pytest.mark.spec("CM-11-038")
def test_a_stub_is_recognised_by_its_type():
    assert (
        _inline_vocab_class({"type": "CasePreview", "summary": "A case"})
        is as_CasePreview
    )


@pytest.mark.spec("CM-11-038")
def test_an_enriched_stub_is_a_stub():
    assert _inline_vocab_class(_enriched_stub()) is as_CasePreview


@pytest.mark.spec("CM-11-038")
@pytest.mark.spec("AKM-03-003")
def test_an_id_and_type_case_is_a_case_reference_not_a_stub():
    """Only ``id`` and ``type``: the typed reference an act names its case by
    (ADR-0165), never a stub, because the type says ``VulnerabilityCase``."""
    resolved = _inline_vocab_class(
        {"type": "VulnerabilityCase", "id": _CASE_ID}
    )
    assert resolved is as_TypedReference


def _body(type_: str, obj: dict) -> dict:
    return {
        "type": type_,
        "id": "urn:uuid:act-case-reference",
        "actor": "https://example.org/actors/a",
        "published": "2026-01-01T00:00:00Z",
        "object": obj,
    }


_REFERENCE = {"type": "VulnerabilityCase", "id": _CASE_ID}


@pytest.mark.spec("AKM-03-004")
@pytest.mark.parametrize("type_", ["Join", "Ignore", "Leave", "Offer"])
def test_an_act_naming_its_case_parses_the_reference(type_):
    named = cast(Any, parse_activity(_body(type_, dict(_REFERENCE)))).object_
    assert is_case_reference(named)
    assert named.id_ == _CASE_ID


@pytest.mark.spec("AKM-03-004")
def test_an_answer_embedding_an_act_keeps_its_reference():
    """An Accept embeds the Offer it answers, reference and all."""
    offer = {
        "type": "Offer",
        "published": "2026-01-01T00:00:00+00:00",
        "id": "urn:uuid:offer",
        "actor": "https://example.org/actors/m",
        "object": dict(_REFERENCE),
        "target": {"type": "Actor", "id": "https://example.org/actors/t"},
    }
    inner = cast(Any, parse_activity(_body("Accept", offer))).object_
    assert is_case_reference(getattr(inner, "object_", None))


@pytest.mark.spec("AKM-03-004")
@pytest.mark.spec("MV-04-003")
@pytest.mark.parametrize("type_", ["Create", "Announce", "Update"])
def test_a_case_reference_elsewhere_is_refused_at_parse(type_):
    """Anywhere but an act that names its case, a case is carried whole, so
    a reference there is a malformed case, refused naming the activity."""
    with pytest.raises(
        VultronParseValidationError, match="act-case-reference"
    ):
        parse_activity(_body(type_, dict(_REFERENCE)))


@pytest.mark.spec("AKM-03-004")
@pytest.mark.spec("MV-04-003")
def test_a_case_reference_as_a_target_is_refused_at_parse():
    body = _body("Join", dict(_REFERENCE))
    body["target"] = dict(_REFERENCE)
    with pytest.raises(VultronParseValidationError, match="target"):
        parse_activity(body)


@pytest.mark.spec("AKM-03-004")
def test_a_misplaced_case_reference_is_named_by_its_wire_key():
    """The refusal names the key the sender wrote, not the Python field."""
    body = _body("Join", dict(_REFERENCE))
    body["inReplyTo"] = dict(_REFERENCE)
    with pytest.raises(VultronParseValidationError) as exc:
        parse_activity(body)
    assert " inReplyTo" in str(exc.value)
    assert "in_reply_to" not in str(exc.value)


@pytest.mark.spec("AKM-03-004")
def test_a_case_reference_inside_an_inline_report_is_refused():
    """The walk reaches into an inline core object, here a report."""
    body = json.loads((_EXAMPLES / "create_report.json").read_text())
    body.setdefault("published", "2026-01-01T00:00:00Z")
    body["object"]["context"] = dict(_REFERENCE)
    with pytest.raises(VultronParseValidationError, match="AKM-03-004") as exc:
        parse_activity(body)
    assert "object.context" in str(exc.value)


@pytest.mark.spec("CM-11-038")
def test_a_sparse_case_is_a_case_not_a_stub():
    """One key past ``id`` and ``type``: a case, because the type says so."""
    resolved = _inline_vocab_class(
        {
            "type": "VulnerabilityCase",
            "published": "2026-01-01T00:00:00+00:00",
            "id": _CASE_ID,
            "name": "sparse",
        }
    )
    assert resolved is VulnerabilityCase


@pytest.mark.spec("CM-11-038")
def test_a_sparse_case_validates_as_a_case():
    case = VulnerabilityCase.model_validate(
        with_times(
            VulnerabilityCase,
            {
                "attributed_to": CASE_OWNER_ID,
                "type": "VulnerabilityCase",
                "published": "2026-01-01T00:00:00+00:00",
                "id": _CASE_ID,
            },
        )
    )
    assert case.id_ == _CASE_ID


@pytest.mark.spec("CM-17-010")
@pytest.mark.spec("CM-11-013")
def test_the_preview_carries_exactly_its_id_type_and_summary():
    """The stub names no case of its own (ADR-0205).

    It carries no ``caseId``, and its ``id`` is minted like any object's,
    never derived from the case's: the reference that carries it names the
    case.
    """
    first = as_CasePreview(summary="A case to join")
    second = as_CasePreview(summary="A case to join")
    wire = json.loads(first.model_dump_json(by_alias=True, exclude_none=True))
    assert set(wire) - {"@context"} == {"id", "type", "summary"}
    assert wire["type"] == "CasePreview"
    assert not wire["id"].endswith("/stub")
    assert first.id_ != second.id_
    assert "case_id" not in as_CasePreview.model_fields


def _invite(case_object: object) -> dict:
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Invite",
        "id": "urn:uuid:invite-enriched",
        "actor": _ACTOR,
        "to": [_INVITEE],
        "published": days_from_now(0).isoformat(),
        "object": case_object,
        "target": {"type": "Organization", "id": _INVITEE},
        "context": _CASE_ID,
    }


def _previewed(preview: dict) -> dict:
    """The case reference carrying *preview* (ADR-0205)."""
    return {"type": "VulnerabilityCase", "id": _CASE_ID, "preview": preview}


def test_an_invite_with_an_enriched_preview_parses():
    """The invitee receives the embargo terms it is asked to consent to."""
    activity = parse_activity(
        json.loads(json.dumps(_invite(_previewed(_enriched_stub()))))
    )
    assert isinstance(activity, as_Invite)
    reference = activity.object_
    assert isinstance(reference, as_TypedReference)
    assert reference.id_ == _CASE_ID
    preview = reference.preview
    assert isinstance(preview, as_CasePreview)
    assert preview_embargo_id(preview) == f"{_CASE_ID}/embargoes/e0"
    assert preview_em_state(preview) is EM.ACTIVE


@pytest.mark.spec("CM-11-038")
def test_an_invite_whose_object_is_a_sparse_case_parses_it_as_a_case():
    activity = parse_activity(
        _invite(
            {
                **INBOUND_CASE_OWNERSHIP,
                "type": "VulnerabilityCase",
                "published": "2026-01-01T00:00:00+00:00",
                "id": _CASE_ID,
            }
        )
    )
    assert isinstance(activity, as_Invite)
    assert isinstance(activity.object_, VulnerabilityCase)


def _stub_with_untyped_status_without_published() -> dict:
    stub = _enriched_stub()
    (status,) = stub["caseStatuses"]
    del status["type"]
    del status["published"]
    return stub


@pytest.mark.spec("MV-12-001")
@pytest.mark.spec("CM-17-013")
def test_an_untyped_stub_status_is_read_as_a_status_keeping_its_em_state():
    """An untyped status in a preview is read in the field's loose
    status form, never as a bare Link, so its EM state is kept (#5715).

    What a preview shows is read as its sender sent it (ADR-0217): the status
    is not refused for its missing ``type`` or ``published``.
    """
    activity = parse_activity(
        _invite(_previewed(_stub_with_untyped_status_without_published()))
    )

    preview = cast(Any, activity).object_.preview
    assert is_loose_form_of(preview_current_status(preview), CaseStatus)
    assert preview_em_state(preview) is EM.ACTIVE


@pytest.mark.spec("MV-12-001")
def test_a_stub_built_here_reads_an_untyped_status_as_a_status():
    """The same holds for a stub this process builds from a dict (#5715)."""
    stub = _stub_with_untyped_status_without_published()
    del stub["embargoRegister"]  # inbound-shaped: it carries no times

    preview = as_CasePreview.model_validate(stub)

    assert is_loose_form_of(preview_current_status(preview), CaseStatus)
    assert preview_em_state(preview) is EM.ACTIVE
