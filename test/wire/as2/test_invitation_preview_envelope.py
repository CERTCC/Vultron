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

"""A receiver refuses a stub Invite whose preview lacks a shown item (MV-10-007).

The sender cuts the preview from the case by the invitation profile
(ADR-0217); the receiver checks the cut where it recognizes the stub Invite,
at the parse edge, naming the preview's position.  Every cut of a valid case
passes the check.
"""

import copy
import itertools
import json
from typing import Any

import pytest

from test.support.embargo_register import register
from test.support.future_dates import days_from_now
from test.support.objects import authored_at, make
from test.support.signing import signed_body
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_preview import (
    CasePreview,
    invitation_preview_faults,
)
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.vulnerability_item import (
    VulnerabilityItem,
    VulnerabilityItemId,
)
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.factories import (
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.typed_reference import as_TypedReference

CASE_ID = "https://example.org/cases/envelope"
OWNER = "https://example.org/actors/vendor"
MANAGER = "https://example.org/actors/case-manager"
INVITEE = "https://example.org/actors/invitee"


def _embargo() -> EmbargoEvent:
    return make(EmbargoEvent, context=CASE_ID, end_time=days_from_now(30))


def _case(**fields: Any) -> VulnerabilityCase:
    return make(
        VulnerabilityCase,
        id_=CASE_ID,
        attributed_to=OWNER,
        stub_summary="A case to join",
        **fields,
    )


def _invite_json(case: VulnerabilityCase, **kwargs: Any) -> dict[str, Any]:
    invite = rm_invite_to_case_activity(
        invitee=INVITEE, case=case, actor=MANAGER, at=authored_at(), **kwargs
    )
    return invite.model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )


def _in_force_invite() -> dict[str, Any]:
    return _invite_json(_case(embargo_register=register(active=_embargo())))


def _parse(body: dict[str, Any]) -> Any:
    return parse_activity(signed_body(body))


# --- AC-5: the receiver's refusals --------------------------------------


@pytest.mark.spec("MV-10-007")
@pytest.mark.spec("CM-17-010")
@pytest.mark.parametrize(
    "owner", [None, {"type": "Redacted"}], ids=["absent", "marked"]
)
def test_a_preview_without_the_case_owner_is_refused(owner: object) -> None:
    body = _invite_json(_case())
    preview = body["object"]["preview"]
    if owner is None:
        del preview["attributedTo"]
    else:
        preview["attributedTo"] = owner

    with pytest.raises(VultronParseValidationError) as exc:
        _parse(body)

    message = str(exc.value)
    assert "object.preview" in message
    assert "Case Owner at 'attributedTo'" in message
    assert "MV-10-007" in message


@pytest.mark.spec("MV-10-007")
@pytest.mark.parametrize(
    "summary", [None, {"type": "Redacted"}], ids=["absent", "marked"]
)
def test_a_preview_without_its_summary_is_refused(summary: object) -> None:
    body = _invite_json(_case())
    preview = body["object"]["preview"]
    if summary is None:
        del preview["summary"]
    else:
        preview["summary"] = summary

    with pytest.raises(VultronParseValidationError, match="summary"):
        _parse(body)


def _without_register(preview: dict[str, Any]) -> None:
    del preview["embargoRegister"]


def _register_marked(preview: dict[str, Any]) -> None:
    preview["embargoRegister"] = {"type": "Redacted"}


def _embargo_marked(preview: dict[str, Any]) -> None:
    preview["embargoRegister"][0]["embargo"] = {"type": "Redacted"}


def _em_state_marked(preview: dict[str, Any]) -> None:
    preview["caseStatuses"][-1]["emState"] = {"type": "Redacted"}


def _statuses_absent(preview: dict[str, Any]) -> None:
    del preview["caseStatuses"]


def _open_proposal_added(preview: dict[str, Any]) -> None:
    preview["embargoRegister"].append(
        {
            "embargo": "https://example.org/embargoes/revision",
            "status": "PROPOSED",
        }
    )


@pytest.mark.spec("MV-10-007")
@pytest.mark.spec("CM-17-002")
@pytest.mark.spec("CM-17-013")
@pytest.mark.spec("CM-17-014")
@pytest.mark.parametrize(
    ("change", "fault"),
    [
        (_without_register, "lacks the in-force entry in 'embargoRegister'"),
        (_register_marked, "marks 'embargoRegister' Redacted"),
        (_embargo_marked, "lacks or marks the in-force embargo"),
        (_em_state_marked, "lacks or marks the EM state"),
        (_statuses_absent, "lacks or marks the EM state"),
        (
            _open_proposal_added,
            "open embargo proposal at 'embargoRegister[1]'",
        ),
    ],
    ids=[
        "terms absent",
        "terms marked",
        "embargo marked",
        "EM state marked",
        "status absent",
        "open proposal",
    ],
)
def test_a_preview_hiding_the_embargo_in_force_is_refused(
    change: Any, fault: str
) -> None:
    body = _in_force_invite()
    change(body["object"]["preview"])

    with pytest.raises(VultronParseValidationError) as exc:
        _parse(body)

    message = str(exc.value)
    assert "the invitation preview at object.preview " in message
    assert fault in message


@pytest.mark.spec("MV-10-007")
def test_a_reply_quoting_a_preview_without_its_owner_names_its_position() -> (
    None
):
    """The check reaches a stub Invite wherever it is carried inline, as the
    placement rule does (MV-10-002)."""
    invite = _invite_json(_case())
    del invite["object"]["preview"]["attributedTo"]
    accept = rm_accept_invite_to_case_activity(
        rm_invite_to_case_activity(
            invitee=INVITEE, case=_case(), actor=MANAGER, at=authored_at()
        ),
        actor=INVITEE,
        at=authored_at(),
    ).model_dump(
        mode="json", by_alias=True, exclude_none=True, serialize_as_any=True
    )
    accept["object"] = invite

    with pytest.raises(VultronParseValidationError) as exc:
        _parse(accept)

    assert "the invitation preview at object.object.preview lacks" in str(
        exc.value
    )


@pytest.mark.spec("MV-10-007")
def test_every_fault_of_a_preview_is_named_in_one_refusal() -> None:
    body = _in_force_invite()
    preview = body["object"]["preview"]
    del preview["attributedTo"]
    del preview["embargoRegister"]

    with pytest.raises(VultronParseValidationError) as exc:
        _parse(body)

    message = str(exc.value)
    assert "Case Owner" in message and "in-force entry" in message


@pytest.mark.spec("MV-12-006")
def test_withholding_any_other_field_is_the_senders_choice() -> None:
    """The check reads only the shown items, so a preview that marks or
    leaves out everything else is read as sent."""
    body = _in_force_invite()
    preview = body["object"]["preview"]
    for key in ("name", "published", "updated", "caseStatuses"):
        preview.pop(key, None)
    preview["caseStatuses"] = [{"type": "CaseStatus", "emState": "ACTIVE"}]
    preview["vulnerabilityItems"] = {"type": "Redacted"}
    preview["name"] = {"type": "Redacted"}

    activity = _parse(body)

    assert isinstance(activity.object_, as_TypedReference)


# --- AC-3: every cut of a valid case is a valid preview ------------------


def _item(**fields: Any) -> VulnerabilityItem:
    return make(
        VulnerabilityItem,
        context=CASE_ID,
        title="Buffer overflow",
        ids=[VulnerabilityItemId.cve("CVE-2026-1234")],
        **fields,
    )


#: The register shapes a case can be in: no embargo, an embargo in force
#: (held inline or by id), a revision open beside it, only a proposal, and
#: an ended embargo.
_REGISTERS = ("none", "active", "active-by-id", "revise", "proposed", "ended")
#: What else the case holds, each a value the preview withholds or cuts.
_CONTENT = ("bare", "full")
_ITEMS = ("none", "object", "by-id")


def _variant(
    shape: str, content: str, items: str
) -> tuple[VulnerabilityCase, EmbargoEvent | None]:
    """A valid case of the given shape, and the embargo to pass when its
    register names the one in force by id."""
    embargo = _embargo()
    revision = _embargo()
    registers = {
        "none": [],
        "active": register(active=embargo),
        "active-by-id": register(active=embargo.id_),
        "revise": register(active=embargo, proposed=[revision]),
        "proposed": register(proposed=[embargo]),
        "ended": register(terminated=embargo),
    }
    fields: dict[str, Any] = {"embargo_register": registers[shape]}
    if content == "full":
        fields |= {
            "name": "Widget RCE",
            "summary": "What only participants see",
            "content": "The full write-up",
            "case_participants": ["https://example.org/participants/p1"],
            "vulnerability_reports": ["https://example.org/reports/r1"],
            "notes": ["https://example.org/notes/n1"],
            "case_references": ["https://example.org/references/ref1"],
            "parent_cases": ["https://example.org/cases/parent"],
            "tag": ["https://example.org/tags/t1"],
        }
    if items == "object":
        fields["vulnerability_items"] = [_item()]
    elif items == "by-id":
        fields["vulnerability_items"] = ["https://example.org/items/i1"]
    return _case(**fields), embargo if shape == "active-by-id" else None


@pytest.mark.spec("CM-17-010")
@pytest.mark.spec("MV-10-007")
@pytest.mark.parametrize(
    ("shape", "content", "items"),
    list(itertools.product(_REGISTERS, _CONTENT, _ITEMS)),
)
def test_the_cut_of_every_valid_case_is_a_valid_preview(
    shape: str, content: str, items: str
) -> None:
    """Built by the sender, sent and parsed by the receiver: the preview
    passes the envelope check on both sides and reads back as sent."""
    case, embargo = _variant(shape, content, items)

    body = _invite_json(case, embargo_obj=embargo)
    sent = copy.deepcopy(body["object"]["preview"])
    activity = _parse(body)

    preview = activity.object_.preview
    assert isinstance(preview, CasePreview)
    assert invitation_preview_faults(preview) == []
    received = preview.model_dump(
        mode="json", by_alias=True, exclude_none=True
    )
    received.pop("@context", None)
    assert received == sent
    assert "The full write-up" not in json.dumps(sent)
    assert "What only participants see" not in json.dumps(sent)
