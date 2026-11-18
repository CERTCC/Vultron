"""The ``Redacted`` marker is read only in a preview's fields (MV-12, ADR-0193).

A preview is a limited view of an object for a recipient not yet entitled to
the whole of it; the case stub is the only one today.  A sender may put
``{"type": "Redacted", "summary": "<reason>"}`` in a preview field to say the
field has a value it withholds.  Anywhere else the marker is refused.

The refusal holds for every declared field of a full object, which refuses a
marker as a malformed value, and for every activity slot, which reads the
marker as a ``Redacted`` value it does not admit, whether or not the marker
carries a ``summary`` (a marker is never read as a typed reference).  A field
that admits any embedded object, such as a full case's ``tag``, holds no
marker either: the parse edge refuses one there, naming its path.  Accepting
the marker in a preview needs a preview field that admits the marker, so that
row is a strict ``xfail`` until #6372 opens one.  The row refusing a marker
that carries the withheld value is held for Concern #6641, which makes that
the sender's rule.
"""

from typing import Any, ClassVar

import pytest
from pydantic import BaseModel, ValidationError

from test.support.case_owner import INBOUND_CASE_OWNERSHIP
from vultron.core.models.redacted import Redacted
from vultron.wire.as2.case_reference_placement import (
    _admits_redaction_marker,
    _is_redaction_marker,
    _misplaced,
)
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

ACTIVITY_ID = "https://example.org/activities/1"
SENDER = "https://example.org/actors/alice"
PUBLISHED = "2026-03-04T05:06:07+00:00"
CASE_ID = "https://example.org/cases/1"
# A stub Invite carries its invitee in ``target`` and the case stub as the
# preview of the case reference in its ``object`` (MV-10-002, ADR-0205).
INVITEE = {"type": "Person", "id": "https://example.org/actors/bob"}
MARKER: dict[str, Any] = {"type": "Redacted", "summary": "Embargo pending"}
TRACKED = "Tracked by #6372."
MARKER_ID = "https://example.org/redactions/1"
# Every free-form slot of an activity; each refuses a marker in any form.
ACTIVITY_SLOTS = [
    "object",
    "target",
    "origin",
    "instrument",
    "result",
    "tag",
    "attachment",
    "inReplyTo",
    "context",
    "location",
    "generator",
    "audience",
]
# A full case's fields that hold any embedded object, and so take a marker
# as a value; the parse edge refuses one there by its position.
FREE_FORM_CASE_FIELDS = ["tag", "attachment", "inReplyTo", "location"]
# A marker with a reason, and one that has the typed reference shape.
MARKER_FORMS = {
    "with-summary": MARKER,
    "with-summary-and-id": {**MARKER, "id": MARKER_ID},
    "only-id-and-type": {"type": "Redacted", "id": MARKER_ID},
}


def _envelope(**slots: Any) -> dict[str, Any]:
    return {
        "type": "Offer",
        "id": ACTIVITY_ID,
        "actor": SENDER,
        "published": PUBLISHED,
        "object": "https://example.org/objects/1",
        **slots,
    }


def _error_locations(error: VultronParseValidationError) -> set[str]:
    """Return the top-level field each validation error is located at."""
    cause = error.__cause__
    assert isinstance(cause, ValidationError), (
        "refusal carries no field errors"
    )
    return {str(detail["loc"][0]) for detail in cause.errors()}


def _assert_refused_as_a_marker(
    error: VultronParseValidationError, slot: str
) -> None:
    """Assert the slot refused the body as a ``Redacted`` value it does not
    admit, so the refusal does not rest on some other fault of the body."""
    assert _error_locations(error) == {slot}
    cause = error.__cause__
    assert isinstance(cause, ValidationError)
    assert "model_type" in {detail["type"] for detail in cause.errors()}, (
        "the slot must refuse the marker as a value of the wrong type"
    )


def _full_case(**fields: Any) -> dict[str, Any]:
    return {
        **INBOUND_CASE_OWNERSHIP,
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "name": "a case",
        **fields,
    }


def _stub_invite(**stub_fields: Any) -> dict[str, Any]:
    stub = {
        "type": "CasePreview",
        "id": "urn:uuid:case-1-preview",
        "summary": "Security issue — details after acceptance",
        **stub_fields,
    }
    reference = {"type": "VulnerabilityCase", "id": CASE_ID, "preview": stub}
    return _envelope(type="Invite", object=reference, target=INVITEE)


@pytest.mark.spec("MV-12-002")
@pytest.mark.parametrize("field", ["name", "content", "summary", "notes"])
def test_a_marker_in_a_full_case_field_is_refused(field: str) -> None:
    """A full case never holds a marker, so a marker in its field is refused."""
    value: Any = [MARKER] if field == "notes" else MARKER
    body = _envelope(object=_full_case(**{field: value}))

    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)

    assert _error_locations(exc_info.value) == {field}


@pytest.mark.spec("MV-12-002")
def test_a_marker_in_a_case_stub_identifying_field_is_refused() -> None:
    """A preview field its type does not open to the marker refuses one."""
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(_stub_invite(id=MARKER))

    assert _error_locations(exc_info.value) == {"id"}


@pytest.mark.spec("MV-12-002")
@pytest.mark.parametrize("form", list(MARKER_FORMS))
@pytest.mark.parametrize("slot", ACTIVITY_SLOTS)
def test_a_marker_in_an_activity_slot_is_refused(slot: str, form: str) -> None:
    """A marker is never an activity's own object, target or other slot.

    The registered type reads the body as a marker, which no activity slot
    admits; the slot refuses it as a value of the wrong type, not for its
    missing ``id`` (OID-01-013).  An ``id`` on the marker is set aside as a
    key the marker does not hold (MV-11-003), and a marker of only ``id``
    and ``type`` is not read as a typed reference, so every form is refused
    the same way.
    """
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(_envelope(**{slot: MARKER_FORMS[form]}))

    _assert_refused_as_a_marker(exc_info.value, slot)


@pytest.mark.spec("MV-12-002")
@pytest.mark.parametrize("form", list(MARKER_FORMS))
@pytest.mark.parametrize("field", FREE_FORM_CASE_FIELDS)
def test_a_marker_in_a_full_case_free_form_field_is_refused(
    field: str, form: str
) -> None:
    """A full case's field that holds any embedded object holds no marker.

    The field's type admits the marker as an object, so the parse edge
    refuses it by its position, naming the path.
    """
    body = _envelope(object=_full_case(**{field: [MARKER_FORMS[form]]}))

    with pytest.raises(VultronParseValidationError, match="Redacted") as exc:
        parse_activity(body)

    assert f"object.{field}[0]" in str(exc.value)


@pytest.mark.spec("MV-12-002")
def test_a_marker_in_a_case_preview_free_form_field_is_refused() -> None:
    """The preview opens no field to the marker yet, so one in its ``tag``
    is refused, naming the path inside the stub Invite's object."""
    with pytest.raises(VultronParseValidationError, match="Redacted") as exc:
        parse_activity(_stub_invite(tag=[MARKER]))

    assert "object.preview.tag[0]" in str(exc.value)


class _PreviewOpeningNameAndTag(BaseModel):
    """A stand-in preview type that opens ``name`` and ``tag`` to the marker,
    as a real preview type will once Concern #6641 decides its fields."""

    redactable_fields: ClassVar[frozenset[str]] = frozenset({"name", "tag"})
    name: Redacted | str | None = None
    summary: Redacted | str | None = None
    tag: list[Redacted | str] | None = None


def _misplaced_markers(model: BaseModel) -> list[str]:
    return list(
        _misplaced(model, "", _is_redaction_marker, _admits_redaction_marker)
    )


@pytest.mark.spec("MV-12-001")
def test_the_walk_admits_a_marker_in_an_opened_field() -> None:
    preview = _PreviewOpeningNameAndTag(name=Redacted(), tag=[Redacted()])

    assert _misplaced_markers(preview) == []


@pytest.mark.spec("MV-12-002")
def test_the_walk_refuses_a_marker_in_a_field_not_opened() -> None:
    preview = _PreviewOpeningNameAndTag(name=Redacted(), summary=Redacted())

    assert _misplaced_markers(preview) == ["summary"]


@pytest.mark.spec("MV-12-002")
def test_a_marker_mixed_with_other_values_in_an_opened_list_is_refused() -> (
    None
):
    """An opened field takes the marker as its value, not as one item among
    others, so a mixed list is walked and its marker refused."""
    preview = _PreviewOpeningNameAndTag(tag=["a tag", Redacted()])

    assert _misplaced_markers(preview) == ["tag[1]"]


@pytest.mark.spec("MV-12-001")
def test_an_empty_list_in_an_opened_field_holds_no_misplaced_marker() -> None:
    """An empty list is not admitted as a marker list, but walking it finds
    nothing to refuse."""
    preview = _PreviewOpeningNameAndTag(tag=[])

    assert _misplaced_markers(preview) == []


class _HoldsASummary(BaseModel):
    summary: Redacted | str | None = None


class _PreviewOpeningDetail(BaseModel):
    """A stand-in preview type whose opened field may also hold an object."""

    redactable_fields: ClassVar[frozenset[str]] = frozenset({"detail"})
    detail: Redacted | _HoldsASummary | None = None


@pytest.mark.spec("MV-12-002")
def test_an_object_in_an_opened_field_is_walked_for_markers() -> None:
    """An opened field admits the marker as its value; an object there is
    walked like any other, so a marker inside it is refused."""
    preview = _PreviewOpeningDetail(detail=_HoldsASummary(summary=Redacted()))

    assert _misplaced_markers(preview) == ["detail.summary"]


@pytest.mark.spec("MV-12-002")
def test_one_refusal_names_every_misplaced_form() -> None:
    """A misplaced case preview and a misplaced marker are named together
    (EH-07-001), not the first one alone."""
    preview = {
        "type": "CasePreview",
        "id": "urn:uuid:misplaced-preview",
        "summary": "a case",
    }
    body = _envelope(object=_full_case(tag=[MARKER]), target=preview)

    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)

    message = str(exc_info.value)
    assert "a CasePreview at target" in message
    assert "a Redacted marker at object.tag[0]" in message


@pytest.mark.xfail(
    strict=True,
    raises=VultronParseValidationError,
    reason=f"MV-12-001: no preview field admits the marker yet. {TRACKED}",
)
@pytest.mark.spec("MV-12-001")
def test_a_marker_in_a_case_preview_field_parses_as_the_marker() -> None:
    """A preview field holding a marker reads as withheld, never as absent."""
    activity = parse_activity(_stub_invite(name=MARKER))

    name = getattr(
        getattr(getattr(activity, "object_", None), "preview", None),
        "name",
        None,
    )
    assert getattr(name, "type_", None) == "Redacted"
    assert getattr(name, "summary", None) == MARKER["summary"]


@pytest.mark.xfail(
    strict=True,
    raises=VultronParseValidationError,
    reason=(
        "MV-12-003, MV-12-005: no preview field admits the marker yet, "
        "so no marker parses. Concern #6641 moves the leaky-marker rule to "
        "the sender; the receiver keeps MV-11-003's unknown-key handling."
    ),
)
@pytest.mark.spec("MV-12-005")
@pytest.mark.spec("MV-12-003")
@pytest.mark.parametrize(
    "extra",
    [
        {"content": "CVE-2026-0001 in widget"},
        {"id": "https://example.org/vuls/1"},
        {"name": "CVE-2026-0001"},
    ],
)
def test_a_marker_carrying_the_withheld_value_is_refused(
    extra: dict[str, str],
) -> None:
    """A marker carries no field but ``type`` and ``summary``.

    The clean marker must parse first: today every marker is refused, which
    would satisfy the refusal below without testing this rule.
    """
    parse_activity(_stub_invite(name=MARKER))
    leaky = {**MARKER, **extra}

    with pytest.raises(VultronParseValidationError):
        parse_activity(_stub_invite(name=leaky))
