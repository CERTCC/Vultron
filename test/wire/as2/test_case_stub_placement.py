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

"""A case stub is accepted only as the target of a case invitation (MV-10-002).

The stub exists so an invitee can decide whether to join a case before it is
entitled to the case (ADR-0114).  Its one place is the ``target`` of the
``Invite`` that invites an actor to the case, including that ``Invite``
carried inline in its ``Accept`` or ``Reject``.  Anywhere else the parser
refuses the activity and names the slot (#5770).
"""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

_EXAMPLES = Path(__file__).resolve().parents[3] / "docs/reference/examples"
_CASE_ID = "https://example.org/cases/abc"
_PUBLISHED = "2026-01-01T00:00:00+00:00"


def _stub() -> dict[str, Any]:
    return {
        "type": "VulnerabilityCaseStub",
        "id": f"{_CASE_ID}/stub",
        "caseId": _CASE_ID,
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
def test_a_stub_as_the_target_of_a_case_invitation_is_accepted(
    name: str,
) -> None:
    """The case invitation and its two replies, as the examples send them."""
    parse_activity(_example(name))


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
    with pytest.raises(VultronParseValidationError, match="target"):
        parse_activity(_activity(type_, target=_stub()))


@pytest.mark.spec("MV-10-002")
def test_a_stub_in_an_embargo_invitation_is_refused() -> None:
    """An embargo invitation names its case by URI, never by stub (#5864)."""
    for slot in ("context", "target"):
        body = _example("relay_embargo_proposal")
        body[slot] = _stub()
        with pytest.raises(VultronParseValidationError, match=slot):
            parse_activity(body)


@pytest.mark.spec("MV-10-002")
def test_a_stub_nested_outside_the_invite_target_is_refused() -> None:
    """A reply whose inline Invite carries the stub in the wrong slot."""
    body = _example("accept_invite_to_case")
    invite = body["object"]
    invite["context"] = invite.pop("target")
    with pytest.raises(VultronParseValidationError, match=r"object\.context"):
        parse_activity(body)


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
    "invitee",
    [
        "https://example.org/actors/bob",
        {"type": "Link", "href": "https://example.org/actors/bob"},
    ],
)
def test_a_case_invitation_naming_its_invitee_by_reference_keeps_its_stub(
    invitee: Any,
) -> None:
    """An invitee named by URI or ``Link`` is still a case invitation."""
    parse_activity(_activity("Invite", object=invitee, target=_stub()))
