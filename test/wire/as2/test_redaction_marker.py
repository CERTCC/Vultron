"""The ``Redacted`` marker is read only inside a preview (MV-12, ADR-0217).

A preview is a limited view of an object for a recipient not yet entitled to
the whole of it; the case stub is the only one today.  A sender may put
``{"type": "Redacted", "summary": "<reason>"}`` anywhere inside a preview to
say there is a value it withholds, and the receiver reads the preview as sent:
a marker at any depth, and nested objects cut down to what the sender chose to
show.  Outside a preview the marker is refused.

The refusal holds for every declared field of a full object, which refuses a
marker as a malformed value, and for every activity slot, which reads the
marker as a ``Redacted`` value it does not admit, whether or not the marker
carries a ``summary`` (a marker is never read as a typed reference).  A field
that admits any embedded object, such as a full case's ``tag``, holds no
marker either: the parse edge refuses one there, naming its path.  A marker
that carries the value it withholds is its sender's fault: the receiver sets
the extra keys aside like any unknown key (MV-11-003).
"""

import logging
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from test.support.case_owner import INBOUND_CASE_OWNERSHIP
from vultron.core.models.case_preview import CasePreview
from vultron.core.models.preview_object import PreviewObject
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
        "published": PUBLISHED,
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


def _preview_of(activity: object) -> CasePreview:
    """The case preview a parsed stub Invite carries."""
    preview = getattr(getattr(activity, "object_", None), "preview", None)
    assert isinstance(preview, CasePreview)
    return preview


def _is_the_marker(value: object) -> bool:
    return isinstance(value, Redacted) and value.summary == MARKER["summary"]


#: A marker at each depth a preview may hold one, and how to read it back.
MARKED_PREVIEW_FIELDS: dict[str, tuple[dict[str, Any], Any]] = {
    "top-level field": (
        {"name": MARKER},
        lambda preview: preview.name,
    ),
    "case field": (
        {"caseParticipants": MARKER},
        lambda preview: preview.case_participants,
    ),
    "list item": (
        {"tag": [MARKER]},
        lambda preview: preview.tag[0],
    ),
    "nested object field": (
        {
            "vulnerabilityItems": [
                {"type": "VulnerabilityItem", "title": MARKER}
            ]
        },
        lambda preview: preview.vulnerability_items[0].title,
    ),
    "nested value field": (
        {
            "embargoRegister": [
                {
                    "status": "ACTIVE",
                    "embargo": {"type": "EmbargoEvent", "endTime": MARKER},
                }
            ]
        },
        lambda preview: preview.embargo_register[0].embargo.end_time,
    ),
}


@pytest.mark.spec("MV-12-001")
@pytest.mark.parametrize("where", list(MARKED_PREVIEW_FIELDS))
def test_a_marker_in_a_case_preview_parses_as_the_marker(where: str) -> None:
    """A marker anywhere inside a preview reads as withheld, never as
    absent, at any depth."""
    fields, read = MARKED_PREVIEW_FIELDS[where]

    preview = _preview_of(parse_activity(_stub_invite(**fields)))

    assert _is_the_marker(read(preview))


@pytest.mark.spec("MV-12-001")
@pytest.mark.parametrize("field", ["id", "summary"])
def test_a_marker_in_the_preview_identity_or_summary_is_refused(
    field: str,
) -> None:
    """The preview's own ``id`` and its required ``summary`` are not values
    it withholds (MV-10-001), so a marker in either is refused."""
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(_stub_invite(**{field: MARKER}))

    cause = exc_info.value.__cause__
    assert isinstance(cause, ValidationError)
    assert {detail["loc"][0] for detail in cause.errors()} == {field}


#: Nested objects cut to what a sender chose to show: no ``id``, no
#: ``published`` and none of the full class's other fields.
CUT_DOWN_OBJECTS: dict[str, dict[str, Any]] = {
    "vul item cut to its ids": {
        "vulnerabilityItems": [
            {
                "type": "VulnerabilityItem",
                "ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}],
            }
        ]
    },
    "participant cut to its actor and roles": {
        "caseParticipants": [
            {
                "type": "CaseParticipant",
                "attributedTo": "https://example.org/actors/vendor",
                "caseRoles": ["vendor"],
            }
        ]
    },
    "status cut to its EM state": {
        "caseStatuses": [{"type": "CaseStatus", "emState": "ACTIVE"}]
    },
    "case reference shown whole": {
        "caseReferences": [
            {
                "type": "CaseReference",
                "id": "https://example.org/references/1",
                "url": {
                    "type": "Link",
                    "href": "https://example.org/advisory",
                },
            }
        ]
    },
    "participant named by id and type": {
        "caseParticipants": [
            {
                "type": "CaseParticipant",
                "id": "https://example.org/participants/1",
            }
        ]
    },
    "case cut to its name in inReplyTo": {
        "inReplyTo": {"type": "VulnerabilityCase", "name": "an earlier case"}
    },
    "vul item without an id in attachment": {
        "attachment": [
            {
                "type": "VulnerabilityItem",
                "ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}],
            }
        ]
    },
    "AS2 note with a marker in tag": {
        "tag": [{"type": "Note", "content": {"type": "Redacted"}}]
    },
    "participant roles as the full class writes them": {
        "caseParticipants": [
            {
                "type": "CaseParticipant",
                "caseRoles": ["vendor", MARKER],
                "participantStatuses": [
                    {"type": "ParticipantStatus", "cvdRole": ["VENDOR"]}
                ],
            }
        ]
    },
    "termination cause cut to its kind": {
        "embargoRegister": [
            {
                "termination": {
                    "reason": "EARLY",
                    "cause": {"kind": "FIX_READY", "vendors": [MARKER]},
                }
            }
        ]
    },
    "note in a note's tag": {
        "tag": [
            {
                "type": "Note",
                "content": "outer",
                "tag": [{"type": "Note", "content": MARKER}],
            }
        ]
    },
    "offer whose object is a note": {
        "tag": [{"type": "Offer", "object": {"type": "Note", "content": "x"}}]
    },
    "object with no type and a marker": {"tag": [{"content": MARKER}]},
    "object of an unknown type and a marker": {
        "tag": [{"type": "NoSuchType", "content": MARKER}]
    },
}


@pytest.mark.spec("MV-12-006")
@pytest.mark.spec("MV-12-001")
@pytest.mark.spec("OID-01-013")
@pytest.mark.spec("CLP-15-011")
@pytest.mark.spec("MV-04-003")
@pytest.mark.parametrize("shown", list(CUT_DOWN_OBJECTS))
def test_a_preview_shows_a_nested_object_cut_down_as_sent(shown: str) -> None:
    """What a preview shows is read as sent: a nested object without its
    ``id``, ``published`` or other fields is not refused (ADR-0217)."""
    fields = CUT_DOWN_OBJECTS[shown]

    preview = _preview_of(parse_activity(_stub_invite(**fields)))

    dumped = preview.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert {key: dumped.get(key) for key in fields} == fields


#: A value shown in a spelling the full class reads, and the spelling the
#: full class writes it back in.
FULL_CLASS_SPELLINGS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "one rel as a string": (
        {
            "caseReferences": [
                {
                    "type": "CaseReference",
                    "url": {
                        "type": "Link",
                        "href": "https://example.org/advisory",
                        "rel": "advisory",
                    },
                }
            ]
        },
        {
            "caseReferences": [
                {
                    "type": "CaseReference",
                    "url": {
                        "type": "Link",
                        "href": "https://example.org/advisory",
                        "rel": ["advisory"],
                    },
                }
            ]
        },
    ),
    "one attachment as an object": (
        {
            "vulnerabilityReports": [
                {
                    "type": "VulnerabilityReport",
                    "attachment": {"type": "Document", "name": "csaf.json"},
                }
            ]
        },
        {
            "vulnerabilityReports": [
                {
                    "type": "VulnerabilityReport",
                    "attachment": [{"type": "Document", "name": "csaf.json"}],
                }
            ]
        },
    ),
}


@pytest.mark.spec("MV-12-006")
@pytest.mark.parametrize("shown", list(FULL_CLASS_SPELLINGS))
def test_a_preview_reads_a_value_as_its_full_class_reads_it(
    shown: str,
) -> None:
    """A loose form carries its full class's reading rules, so a value a full
    object may spell more than one way is read the same way inside a
    preview, not refused or misread."""
    fields, written = FULL_CLASS_SPELLINGS[shown]

    preview = _preview_of(parse_activity(_stub_invite(**fields)))

    dumped = preview.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert {key: dumped.get(key) for key in written} == written


@pytest.mark.spec("MV-12-001")
def test_a_nested_object_inside_a_preview_is_its_loose_form() -> None:
    """A preview's nested object is held in a loose form of its class, not
    the full class, which would refuse a cut-down one."""
    preview = _preview_of(
        parse_activity(
            _stub_invite(**CUT_DOWN_OBJECTS["vul item cut to its ids"])
        )
    )

    (item,) = preview.vulnerability_items or []
    assert isinstance(item, PreviewObject)
    assert item.id_ is None and item.published is None


@pytest.mark.spec("MV-12-005")
@pytest.mark.spec("MV-11-003")
@pytest.mark.parametrize(
    "extra",
    [
        {"content": "CVE-2026-0001 in widget"},
        {"id": "https://example.org/vuls/1"},
        {"name": "CVE-2026-0001"},
    ],
    ids=["content", "id", "name"],
)
def test_a_marker_carrying_the_withheld_value_has_it_set_aside(
    extra: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """A leaky marker is its sender's fault (MV-12-005): the receiver sets
    the extra key aside and reports it as it does any unknown key, and reads
    a clean marker (MV-11-003)."""
    leaky = {**MARKER, **extra}
    (key,) = extra

    with caplog.at_level(logging.INFO, logger="vultron.wire.as2.unknown_keys"):
        preview = _preview_of(parse_activity(_stub_invite(name=leaky)))

    assert preview.name == Redacted(summary=MARKER["summary"])
    assert any(
        record.levelno == logging.INFO
        and repr(key) in record.getMessage()
        and "'object.preview.name'" in record.getMessage()
        for record in caplog.records
    ), "the set-aside key is reported with its position"


@pytest.mark.spec("MV-11-003")
def test_case_bookkeeping_in_a_preview_is_set_aside() -> None:
    """A preview declares none of the case's bookkeeping, so a received one
    is an unknown key, set aside, not read (ADR-0217)."""
    preview = _preview_of(
        parse_activity(_stub_invite(genesisHash="abc", stubSummary="x"))
    )

    dumped = preview.model_dump(by_alias=True, exclude_none=True)
    assert "genesisHash" not in dumped and "stubSummary" not in dumped


#: A preview a sender cuts as ADR-0217's profile does, with an embargo in
#: force; times in the fixed wire form, so the re-dump is byte-equal.
CUT_PREVIEW: dict[str, Any] = {
    "type": "CasePreview",
    "id": "urn:uuid:case-1-preview",
    "summary": "A remote code execution vulnerability in widget.",
    "name": "Widget RCE",
    "published": "2026-08-03T00:00:00.000000+00:00",
    "attributedTo": "https://example.org/actors/vendor",
    "caseStatuses": [
        {
            "type": "CaseStatus",
            "id": "urn:uuid:status-1",
            "published": "2026-11-01T00:00:00.000000+00:00",
            "emState": "ACTIVE",
        }
    ],
    "vulnerabilityItems": [
        {
            "type": "VulnerabilityItem",
            "ids": [{"systemName": "CVE", "text": "CVE-2026-1234"}],
        }
    ],
    "content": {"type": "Redacted"},
    "caseParticipants": {"type": "Redacted", "summary": "after joining"},
    "vulnerabilityReports": {"type": "Redacted"},
    "notes": {"type": "Redacted"},
}


@pytest.mark.spec("VM-05-002")
@pytest.mark.spec("MV-12-001")
def test_a_preview_carrying_markers_round_trips_unchanged() -> None:
    """Parsing a preview with markers and cut-down objects and dumping it
    again gives the same JSON (VM-05-002)."""
    reference = {
        "type": "VulnerabilityCase",
        "id": CASE_ID,
        "preview": CUT_PREVIEW,
    }
    body = _envelope(type="Invite", object=reference, target=INVITEE)

    preview = _preview_of(parse_activity(body))
    dumped = preview.model_dump(by_alias=True, exclude_none=True, mode="json")
    dumped.pop("@context", None)

    assert dumped == CUT_PREVIEW


class _HoldsAPreviewAndAMarker(BaseModel):
    """A stand-in object that holds a preview and, beside it, a marker."""

    preview: CasePreview
    note: Redacted | None = None


@pytest.mark.spec("MV-12-001")
@pytest.mark.spec("MV-12-002")
def test_the_walk_admits_a_preview_whole_and_refuses_a_marker_beside_it() -> (
    None
):
    """A preview is admitted whole, so no marker inside it is misplaced; a
    marker beside it is outside every preview."""
    preview = CasePreview(summary="a case", name=Redacted(), tag=[Redacted()])
    holder = _HoldsAPreviewAndAMarker(preview=preview, note=Redacted())

    assert list(
        _misplaced(holder, "", _is_redaction_marker, _admits_redaction_marker)
    ) == ["note"]


#: A key a dict in a preview's field carries that its loose form lacks, and
#: where the set-aside report names it.
TYPELESS_EXTRAS: dict[str, tuple[dict[str, Any], str, str]] = {
    "register entry with a summary": (
        {
            "embargoRegister": [
                {
                    "summary": "an extra key",
                    "status": "ACTIVE",
                    "embargo": {"type": "EmbargoEvent", "id": "urn:uuid:e1"},
                }
            ]
        },
        "summary",
        "object.preview.embargoRegister[0]",
    ),
    "identifier with a type": (
        {
            "vulnerabilityItems": [
                {
                    "type": "VulnerabilityItem",
                    "ids": [
                        {
                            "type": "NoSuchType",
                            "systemName": "CVE",
                            "text": "CVE-2026-1234",
                        }
                    ],
                }
            ]
        },
        "type",
        "object.preview.vulnerabilityItems[0].ids[0]",
    ),
}


@pytest.mark.spec("MV-11-003")
@pytest.mark.spec("MV-12-006")
@pytest.mark.parametrize("case", list(TYPELESS_EXTRAS))
def test_an_unknown_key_in_a_preview_dict_without_a_type_is_set_aside(
    case: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The partition and the parser read a dict with no known ``type`` in a
    preview field with the same loose form, so a key it lacks is set aside
    and reported, not refused."""
    fields, key, where = TYPELESS_EXTRAS[case]

    with caplog.at_level(logging.INFO, logger="vultron.wire.as2.unknown_keys"):
        parse_activity(_stub_invite(**fields))

    assert any(
        repr(key) in record.getMessage() and repr(where) in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.spec("MV-10-002")
def test_a_case_preview_inside_a_preview_is_refused() -> None:
    """A preview's one place is the case reference an Invite names, so a
    preview nested inside it is misplaced, naming its path."""
    nested = {
        "type": "CasePreview",
        "id": "urn:uuid:another-preview",
        "summary": "another case",
    }

    with pytest.raises(
        VultronParseValidationError, match="CasePreview"
    ) as exc:
        parse_activity(_stub_invite(tag=[nested]))

    assert "object.preview.tag[0]" in str(exc.value)


@pytest.mark.spec("MV-12-006")
def test_a_typeless_status_is_written_back_with_its_type() -> None:
    """A dict a field reads as its loose form takes that form's ``type``, so
    the preview dumps it with one: the content survives, and the type is the
    one the field already implied."""
    status = {"emState": "ACTIVE"}

    preview = _preview_of(parse_activity(_stub_invite(caseStatus=status)))

    dumped = preview.model_dump(by_alias=True, exclude_none=True, mode="json")
    assert dumped["caseStatus"] == {"type": "CaseStatus", "emState": "ACTIVE"}
