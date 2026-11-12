"""The ``Redacted`` marker is read only in a preview's fields (MV-12, ADR-0193).

A preview is a limited view of an object for a recipient not yet entitled to
the whole of it; the case stub is the only one today.  A sender may put
``{"type": "Redacted", "summary": "<reason>"}`` in a preview field to say the
field has a value it withholds.  Anywhere else the marker is refused.

The refusal already holds: every declared field of a full object refuses a
marker as a malformed value.  Accepting the marker in a preview needs the
marker type, so those rows are strict ``xfail`` until #6372 builds it.
"""

from typing import Any

import pytest

from test.support.case_owner import INBOUND_CASE_OWNERSHIP
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity

ACTIVITY_ID = "https://example.org/activities/1"
SENDER = "https://example.org/actors/alice"
PUBLISHED = "2026-03-04T05:06:07+00:00"
CASE_ID = "https://example.org/cases/1"
# A case invitation carries its invitee inline (AKM-05-017); only then may its
# target be a case stub (MV-10-002).
INVITEE = {"type": "Person", "id": "https://example.org/actors/bob"}
MARKER: dict[str, Any] = {"type": "Redacted", "summary": "Embargo pending"}
TRACKED = "Tracked by #6372."


def _envelope(**slots: Any) -> dict[str, Any]:
    return {
        "type": "Offer",
        "id": ACTIVITY_ID,
        "actor": SENDER,
        "published": PUBLISHED,
        "object": "https://example.org/objects/1",
        **slots,
    }


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
        "type": "VulnerabilityCaseStub",
        "id": f"{CASE_ID}/stub",
        "caseId": CASE_ID,
        "summary": "Security issue — details after acceptance",
        **stub_fields,
    }
    return _envelope(type="Invite", object=INVITEE, target=stub)


@pytest.mark.spec("MV-12-002")
@pytest.mark.parametrize("field", ["name", "content", "summary", "notes"])
def test_a_marker_in_a_full_case_field_is_refused(field: str) -> None:
    """A full case never holds a marker, so a marker in its field is refused."""
    value: Any = [MARKER] if field == "notes" else MARKER
    body = _envelope(object=_full_case(**{field: value}))

    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(body)

    assert field in str(exc_info.value)


@pytest.mark.spec("MV-12-002")
@pytest.mark.parametrize("slot", ["object", "target"])
def test_a_marker_in_an_activity_slot_is_refused(slot: str) -> None:
    """A marker is never an activity's own object or target."""
    with pytest.raises(VultronParseValidationError) as exc_info:
        parse_activity(_envelope(**{slot: MARKER}))

    assert slot in str(exc_info.value)


@pytest.mark.xfail(
    strict=True,
    reason=f"MV-12-001: no Redacted marker type exists yet. {TRACKED}",
)
@pytest.mark.spec("MV-12-001")
def test_a_marker_in_a_case_preview_field_parses_as_the_marker() -> None:
    """A preview field holding a marker reads as withheld, never as absent."""
    activity = parse_activity(_stub_invite(name=MARKER))

    name = getattr(activity.target, "name", None)
    assert getattr(name, "type_", None) == "Redacted"
    assert getattr(name, "summary", None) == MARKER["summary"]


@pytest.mark.xfail(
    strict=True,
    reason=f"MV-12-003: no Redacted marker type exists yet. {TRACKED}",
)
@pytest.mark.spec("MV-12-005")
@pytest.mark.spec("MV-12-003")
def test_a_marker_carrying_the_withheld_value_is_refused() -> None:
    """A marker carries no field but ``type`` and ``summary``.

    The clean marker must parse first: today every marker is refused, which
    would satisfy the refusal below without testing this rule.
    """
    parse_activity(_stub_invite(name=MARKER))
    leaky = {**MARKER, "content": "CVE-2026-0001 in widget"}

    with pytest.raises(VultronParseValidationError):
        parse_activity(_stub_invite(name=leaky))
