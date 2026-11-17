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

"""A case stub is accepted only as the case's preview in a stub Invite (MV-10-002).

The stub exists so an invitee can decide whether to join a case before it is
entitled to the case (ADR-0114).  It is the case's preview (ADR-0205), so its
one place is the ``preview`` of the case reference that is an ``Invite``'s
``object``, wherever that ``Invite`` is carried inline: in its ``Accept`` or
``Reject``, or in a refusal notice quoting such a reply.  Anywhere else,
including the ``target`` it held before ADR-0205, the parser refuses the
activity and names the slot (#5770).
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from test.support.objects import authored_at
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import refusal_notice_activity
from vultron.wire.as2.parser import parse_activity

_EXAMPLES = Path(__file__).resolve().parents[3] / "docs/reference/examples"
_CASE_ID = "https://example.org/cases/abc"
_PUBLISHED = "2026-01-01T00:00:00+00:00"


def _stub() -> dict[str, Any]:
    return {
        "type": "VulnerabilityCaseStub",
        "id": "urn:uuid:abc-preview",
        "summary": "A vul in widget; details shared after acceptance.",
    }


def _example(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((_EXAMPLES / f"{name}.json").read_text())
    body.setdefault("published", _PUBLISHED)
    return body


def _activity(type_: str, **slots: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": type_,
        "id": "https://example.org/activities/1",
        "actor": "https://example.org/actors/vendor",
        "object": "https://example.org/objects/1",
        "published": _PUBLISHED,
    }
    body.update(slots)
    return body


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize(
    "name",
    ["invite_to_case", "accept_invite_to_case", "reject_invite_to_case"],
)
def test_a_stub_as_the_preview_of_a_stub_invite_is_accepted(
    name: str,
) -> None:
    """The case invitation and its two replies, as the examples send them."""
    parse_activity(_example(name))


@pytest.mark.spec("MV-10-002")
@pytest.mark.spec("CLP-05-001")
@pytest.mark.parametrize(
    "name", ["accept_invite_to_case", "reject_invite_to_case"]
)
def test_a_refusal_notice_quoting_a_reply_to_a_case_invitation_is_accepted(
    name: str,
) -> None:
    """The stub stays the preview of its Invite's object however deep it
    is quoted.

    A refusal notice carries the refused reply inline, and the reply carries
    its Invite inline, so the stub is four levels down (MV-10-002).
    """
    notice = refusal_notice_activity(
        _example(name),
        "a precondition did not hold",
        actor="https://example.org/actors/case-manager",
        to=["https://example.org/actors/vendor"],
        at=authored_at(),
    )
    body = json.loads(notice.to_json())
    invite = body["object"]["object"]
    assert invite["object"]["preview"]["type"] == "VulnerabilityCaseStub"

    received = cast(Any, parse_activity(body))

    preview = received.object_.object_.object_.preview
    assert preview.type_ == "VulnerabilityCaseStub"


_REFUSED_SLOTS = [
    "object",
    "origin",
    "instrument",
    "result",
    "context",
    "inReplyTo",
    "attributedTo",
    "attachment",
    "tag",
    "location",
    "generator",
    "audience",
]


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize("type_", ["Invite", "Announce", "Accept", "Offer"])
@pytest.mark.parametrize("slot", _REFUSED_SLOTS)
def test_a_stub_outside_a_case_invitation_target_is_refused(
    type_: str, slot: str
) -> None:
    body = _activity(type_, **{slot: _stub()})
    with pytest.raises(VultronParseValidationError, match="MV-10-002") as exc:
        parse_activity(body)
    assert f" {slot}" in str(exc.value)


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize("type_", ["Offer", "Add", "Announce", "Accept"])
def test_a_stub_as_the_target_of_another_activity_is_refused(
    type_: str,
) -> None:
    with pytest.raises(VultronParseValidationError, match="MV-10-002") as exc:
        parse_activity(_activity(type_, target=_stub()))
    assert "VulnerabilityCaseStub at target;" in str(exc.value)


@pytest.mark.spec("MV-10-002")
def test_a_stub_in_an_embargo_invitation_is_refused() -> None:
    """An embargo invitation names its case by URI, never by stub (#5864)."""
    for slot in ("context", "target"):
        body = _example("relay_embargo_proposal")
        body[slot] = _stub()
        with pytest.raises(
            VultronParseValidationError, match="MV-10-002"
        ) as exc:
            parse_activity(body)
        assert f"VulnerabilityCaseStub at {slot};" in str(exc.value)


@pytest.mark.spec("MV-10-002")
def test_a_stub_nested_outside_the_invite_object_is_refused() -> None:
    """A reply whose inline Invite carries a stub in another slot too."""
    body = _example("accept_invite_to_case")
    invite = body["object"]
    invite["context"] = invite["object"]["preview"]
    with pytest.raises(VultronParseValidationError, match=r"object\.context"):
        parse_activity(body)


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize(
    "name", ["create_case", "create_report", "submit_report"]
)
@pytest.mark.parametrize("slot", ["context", "inReplyTo", "attachment"])
def test_a_stub_inside_an_inline_domain_object_is_refused(
    name: str, slot: str
) -> None:
    """The walk reaches into inline core objects, a case or a report."""
    body = _example(name)
    body["object"][slot] = [_stub()] if slot == "attachment" else _stub()
    with pytest.raises(VultronParseValidationError, match="MV-10-002") as exc:
        parse_activity(body)
    assert f"at object.{slot}" in str(exc.value)


@pytest.mark.spec("MV-10-002")
def test_every_misplaced_stub_is_named() -> None:
    body = _activity("Announce", context=_stub(), result=_stub())
    with pytest.raises(VultronParseValidationError) as exc:
        parse_activity(body)
    assert "context" in str(exc.value)
    assert "result" in str(exc.value)


@pytest.mark.spec("MV-10-009")
@pytest.mark.parametrize("slot", ["target", "context", "origin", "object"])
@pytest.mark.parametrize("form", ["uri", "link"])
def test_a_case_uri_or_link_is_accepted_where_a_stub_is_refused(
    slot: str, form: str
) -> None:
    """The stub rule refuses the stub, never a reference by URI or Link."""
    value: Any = (
        _CASE_ID if form == "uri" else {"type": "Link", "href": _CASE_ID}
    )
    parse_activity(_activity("Announce", **{slot: copy.deepcopy(value)}))


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize(
    "case_object",
    [
        {"type": "Person", "id": "https://example.org/actors/bob"},
        {
            "type": "VulnerabilityCase",
            "id": _CASE_ID,
            "preview": {
                "type": "VulnerabilityCaseStub",
                "id": "urn:uuid:abc-preview-2",
                "summary": "A vul in widget.",
            },
        },
    ],
    ids=["actor-object", "previewed-case-object"],
)
def test_a_stub_in_an_invite_target_is_refused(
    case_object: dict[str, Any],
) -> None:
    """The stub's old place, an Invite's ``target``, is refused, naming it.

    The target is the invitee (ADR-0205), so a stub there is misplaced
    whatever the Invite's ``object`` is.
    """
    with pytest.raises(VultronParseValidationError, match="MV-10-002") as exc:
        parse_activity(_activity("Invite", object=case_object, target=_stub()))
    assert "VulnerabilityCaseStub at target;" in str(exc.value)


def _embargo_invite_naming_its_terms(form: str) -> dict[str, Any]:
    """The relayed embargo Invite, its ``EmbargoEvent`` named by *form*."""
    body = _example("relay_embargo_proposal")
    terms_id = body["object"]["id"]
    body["object"] = (
        terms_id if form == "uri" else {"type": "Link", "href": terms_id}
    )
    return body


@pytest.mark.spec("MV-10-002")
@pytest.mark.spec("SE-01-006")
@pytest.mark.parametrize("form", ["uri", "link"])
def test_an_embargo_invitation_naming_its_terms_by_reference_keeps_no_stub(
    form: str,
) -> None:
    """A stub cannot ride an embargo Invite whose terms are not inline.

    Rehydration resolves such terms from the receiver's own store after the
    parse edge has run (SE-01-006), so a stub the parser let through would
    reach the embargo invitation's use case (#5895).
    """
    body = _embargo_invite_naming_its_terms(form)
    body["target"] = _stub()
    with pytest.raises(VultronParseValidationError, match="MV-10-002") as exc:
        parse_activity(body)
    assert "VulnerabilityCaseStub at target;" in str(exc.value)


@pytest.mark.spec("MV-10-002")
@pytest.mark.parametrize("form", ["uri", "link"])
def test_an_embargo_invitation_naming_its_terms_by_reference_still_parses(
    form: str,
) -> None:
    """Without a stub, terms named by URI or ``Link`` still parse (ADR-0123)."""
    parse_activity(_embargo_invite_naming_its_terms(form))
