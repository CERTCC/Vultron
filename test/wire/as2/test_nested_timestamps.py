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

"""A nested object's time is taken as received — never the receiver's clock.

AS2 makes ``published`` and ``updated`` optional on every object, and nested
objects routinely omit them.  The top-level activity's ``published`` is refused
when missing (CLP-15-006); a nested object's is not, so absence must survive the
wire→core boundary as absence.  Before ISSUE-3257 it did not: the wire
``default_factory=now_utc`` filled an omitted value with the receiver's clock,
``_get_timestamp`` did the same for ``None``, and four builders dropped even a
real sender value.  Downstream every one of those read as the sender's claim.

Each body is raw JSON through ``parse_activity`` → ``extract_event``, the real
inbound path, so the test sees what a receiver sees.
"""

from datetime import datetime
from typing import Any, Callable

import pytest

from vultron.core.models._helpers import absent_times_as_none
from vultron.semantic_registry import extract_event
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.base import as_Base

ACTOR = "https://example.org/actors/alice"
CASE_ID = "https://example.org/cases/c1"
ACTIVITY_PUBLISHED = "2026-01-02T03:04:05+00:00"
SENDER_PUBLISHED = "2025-05-05T05:05:05+00:00"
SENDER_UPDATED = "2025-06-06T06:06:06+00:00"
SENDER_GENESIS = "f" * 64

#: Every spelling of "the sender supplied no time" (ADR-0090: blank is absence).
ABSENT: dict[str, Callable[[dict[str, Any]], None]] = {
    "omitted": lambda d: d.pop("published", None),
    "blank": lambda d: d.__setitem__("published", ""),
    "null": lambda d: d.__setitem__("published", None),
}


def _body(
    obj: dict[str, Any] | str, activity_type: str = "Create", **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": activity_type,
        "id": "https://example.org/activities/1",
        "actor": ACTOR,
        "published": ACTIVITY_PUBLISHED,
        "object": obj,
    }
    body.update(extra)
    return body


#: One inbound shape per nested object type the extractor builds.  ``Case``
#: carries a ``genesisHash`` so that its time is not needed for a decision —
#: the no-hash case is pinned separately below.
KINDS: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "VulnerabilityReport": (
        {
            "type": "VulnerabilityReport",
            "id": "https://example.org/reports/1",
            "name": "r",
            "content": "x",
            "attributedTo": ACTOR,
        },
        {},
    ),
    "VulnerabilityCase": (
        {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "name": "c",
            "attributedTo": ACTOR,
            "genesisHash": SENDER_GENESIS,
        },
        {},
    ),
    "CaseParticipant": (
        {
            "type": "CaseParticipant",
            "id": "https://example.org/participants/1",
            "attributedTo": ACTOR,
            "context": CASE_ID,
        },
        {"context": CASE_ID},
    ),
    "Note": (
        {
            "type": "Note",
            "id": "https://example.org/notes/1",
            "content": "hi",
            "attributedTo": ACTOR,
            "context": CASE_ID,
        },
        {"context": CASE_ID},
    ),
    "CaseStatus": (
        {
            "type": "CaseStatus",
            "id": "https://example.org/case-statuses/1",
            "context": CASE_ID,
            "emState": "NONE",
            "pxaState": "pxa",
        },
        {"activity_type": "Add", "target": CASE_ID},
    ),
    "ParticipantStatus": (
        {
            "type": "ParticipantStatus",
            "id": "https://example.org/participant-statuses/1",
            "context": CASE_ID,
            "attributedTo": ACTOR,
            "rmState": "RECEIVED",
        },
        {
            "activity_type": "Add",
            "target": "https://example.org/participants/1",
            "context": CASE_ID,
        },
    ),
    "EmbargoEvent": (
        {
            "type": "EmbargoEvent",
            "id": "https://example.org/embargoes/1",
            "context": CASE_ID,
            "startTime": "2026-01-01T00:00:00+00:00",
            "endTime": "2027-01-01T00:00:00+00:00",
        },
        {"context": CASE_ID},
    ),
}


def _extracted(obj: dict[str, Any], extra: dict[str, Any]) -> Any:
    extra = dict(extra)
    activity_type = extra.pop("activity_type", "Create")
    event = extract_event(parse_activity(_body(obj, activity_type, **extra)))
    domain = getattr(event, "object_", None)
    assert domain is not None, f"{obj['type']} did not extract a domain object"
    return domain


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("kind", list(KINDS))
def test_extracted_object_carries_sender_published_and_updated(kind: str):
    """A timestamp the sender supplied reaches core unchanged, for every type.

    ``_build_participant_object``, ``_build_note_object``,
    ``_build_case_status_object`` and ``_build_participant_status_object`` never
    passed ``published``/``updated``, so the core ``default_factory`` replaced a
    real sender value with the receiver's clock.
    """
    obj, extra = KINDS[kind]
    obj = {**obj, "published": SENDER_PUBLISHED, "updated": SENDER_UPDATED}

    domain = _extracted(obj, extra)

    assert domain.published == datetime.fromisoformat(SENDER_PUBLISHED)
    assert domain.updated == datetime.fromisoformat(SENDER_UPDATED)


@pytest.mark.spec("CLP-15-007")
@pytest.mark.spec("MV-03-002")
@pytest.mark.parametrize("spelling", list(ABSENT))
@pytest.mark.parametrize("kind", list(KINDS))
def test_nested_object_without_published_extracts_with_no_published(
    kind: str, spelling: str
):
    """No claimed time on the wire means no time in core — not the receiver's.

    Every spelling of absence reads the same (ADR-0090), and none of them may
    come out as a clock reading the sender never made.
    """
    obj, extra = KINDS[kind]
    obj = dict(obj)
    ABSENT[spelling](obj)

    domain = _extracted(obj, extra)

    assert domain.published is None
    assert domain.updated is None


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("spelling", list(ABSENT))
def test_nested_updated_is_not_filled_when_only_published_is_sent(
    spelling: str,
):
    """An omitted ``updated`` stays absent even when ``published`` is present.

    Filled with the receiver's clock, it outranked ``published`` in
    ``status_recency_key`` and ordered received statuses by *arrival*.
    """
    obj, extra = KINDS["CaseStatus"]
    # Vary ``updated`` by reusing the ``published`` spellings on a scratch dict.
    scratch = {"published": SENDER_UPDATED}
    ABSENT[spelling](scratch)
    obj = {**obj, "published": SENDER_PUBLISHED}
    if "published" in scratch:
        obj["updated"] = scratch["published"]

    domain = _extracted(obj, extra)

    assert domain.published == datetime.fromisoformat(SENDER_PUBLISHED)
    assert domain.updated is None


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("spelling", list(ABSENT))
def test_status_nested_in_a_case_without_published_does_not_crash(
    spelling: str,
):
    """A case status with no time, inside a case, extracts rather than raising.

    ``as_CaseStatus.to_core`` handed ``None`` to a core ``published: datetime``
    and raised an uncaught pydantic ``ValidationError`` out of the extractor.
    """
    status: dict[str, Any] = {
        "type": "CaseStatus",
        "id": "https://example.org/case-statuses/1",
        "context": CASE_ID,
        "emState": "NONE",
        "pxaState": "pxa",
    }
    ABSENT[spelling](status)
    case = {
        **KINDS["VulnerabilityCase"][0],
        "published": SENDER_PUBLISHED,
        "caseStatuses": [status],
    }

    domain = _extracted(case, {})

    materialised = [s for s in domain.case_statuses if not isinstance(s, str)]
    assert len(materialised) == 1
    assert materialised[0].published is None


@pytest.mark.spec("CLP-08-002")
def test_extracted_case_keeps_the_sender_genesis_hash():
    """The sender's ``genesisHash`` crosses the boundary instead of being redone.

    ``_build_case_object`` dropped it, so core recomputed the hash from
    ``published`` — which, when that was absent, meant from the receiver's clock,
    giving every receiver a different genesis for the same case.
    """
    obj, extra = KINDS["VulnerabilityCase"]

    domain = _extracted({**obj, "published": SENDER_PUBLISHED}, extra)

    assert domain.genesis_hash == SENDER_GENESIS


@pytest.mark.spec("CLP-08-002")
@pytest.mark.spec("MV-03-002")
@pytest.mark.parametrize("spelling", list(ABSENT))
def test_case_needing_its_time_for_genesis_is_refused_at_parse(spelling: str):
    """The one decision that needs a nested time refuses loudly when it is absent.

    A case with no ``genesisHash`` has its genesis computed from ``published``
    (CLP-08-002).  Blank and ``null`` were already refused; *omitted* was filled
    with the receiver's clock and accepted, so each receiver derived its own
    genesis.  All three spellings are one omission and draw one refusal.
    """
    obj = {
        key: value
        for key, value in KINDS["VulnerabilityCase"][0].items()
        if key != "genesisHash"
    }
    obj["published"] = SENDER_PUBLISHED
    ABSENT[spelling](obj)

    with pytest.raises(VultronParseValidationError, match="genesis_hash"):
        parse_activity(_body(obj))


@pytest.mark.spec("CLP-15-007")
def test_nested_activity_without_published_parses_with_no_published():
    """An inner activity (the ``Invite`` inside an ``Accept``) is nested too."""
    body = _body(
        {
            "type": "Invite",
            "id": "urn:uuid:invite-1",
            "actor": "https://example.org/actors/vendor",
            "object": {"type": "Organization", "id": ACTOR, "name": "Alice"},
            "target": {"type": "VulnerabilityCase", "id": CASE_ID},
        },
        activity_type="Accept",
    )

    activity = parse_activity(body)

    inner = getattr(activity, "object_", None)
    assert getattr(inner, "published", "missing") is None
    assert getattr(inner, "updated", "missing") is None


@pytest.mark.spec("CLP-15-007")
def test_top_level_updated_is_not_filled_with_the_receiver_clock():
    """The activity's own ``updated`` is optional, and absent means absent."""
    body = _body("https://example.org/notes/1")

    activity = parse_activity(body)
    event = extract_event(activity)

    assert activity.updated is None
    assert event.activity is None or event.activity.updated is None


@pytest.mark.spec("CLP-15-007")
def test_embargo_without_start_time_extracts_with_no_start_time():
    """An embargo's ``startTime`` is optional on the wire and is not invented.

    ``endTime`` is what embargo decisions read; nothing decides on the start, so
    an absent one stays absent rather than becoming the receiver's clock.
    """
    obj, extra = KINDS["EmbargoEvent"]
    obj = {key: value for key, value in obj.items() if key != "startTime"}

    domain = _extracted(obj, extra)

    assert domain.start_time is None


#: A replicated ledger entry, shaped as ``Announce(CaseLedgerEntry)`` carries it.
LEDGER_ENTRY: dict[str, Any] = {
    "type": "CaseLedgerEntry",
    "id": f"{CASE_ID}/ledger/0",
    "caseId": CASE_ID,
    "logIndex": 0,
    "logObjectId": "https://example.org/activities/0",
    "eventType": "create_case",
    "prevLogHash": "0" * 64,
    "entryHash": "a" * 64,
    "published": SENDER_PUBLISHED,
    "receivedAt": SENDER_UPDATED,
}


@pytest.mark.spec("CLP-14-002")
def test_replicated_ledger_entry_keeps_the_case_actor_stamps():
    """A replica keeps the CaseActor's commit and receipt times.

    ``received_at`` is hashed content, so a replica that stamped its own could
    never re-verify the entry; the builder dropped both fields.
    """
    domain = _extracted(LEDGER_ENTRY, {"activity_type": "Announce"})

    assert domain.published == datetime.fromisoformat(SENDER_PUBLISHED)
    assert domain.received_at == datetime.fromisoformat(SENDER_UPDATED)


@pytest.mark.spec("CLP-14-002")
@pytest.mark.parametrize("key", ["published", "receivedAt"])
def test_replicated_ledger_entry_without_its_stamp_is_refused_at_parse(
    key: str,
):
    """An entry missing a time it must carry is refused, not stamped locally."""
    entry = {k: v for k, v in LEDGER_ENTRY.items() if k != key}

    with pytest.raises(VultronParseValidationError):
        parse_activity(_body(entry, "Announce"))


@pytest.mark.spec("MV-03-002")
def test_embargo_without_end_time_is_refused_at_parse():
    """``endTime`` is what embargo decisions read, so its absence is refused.

    The wire default was the receiver's clock plus 45 days — an expiry the
    sender never proposed.
    """
    obj, _ = KINDS["EmbargoEvent"]
    obj = {key: value for key, value in obj.items() if key != "endTime"}

    with pytest.raises(VultronParseValidationError, match="end_time"):
        parse_activity(_body(obj))


@pytest.mark.spec("CLP-15-007")
@pytest.mark.parametrize("spelling", list(ABSENT))
def test_inline_object_without_a_type_is_not_stamped_either(spelling: str):
    """An inline object that omits ``type`` is carried as received too.

    ``_inline_vocab_class`` can only pre-resolve a dict that names its ``type``;
    without one the dict stays raw for the parent field to validate.  Reading
    absences in the parser therefore missed it, and the class the parent chose
    stamped the receiver's clock — which, being the newest value in the list,
    made this status the case's current one ahead of every status the sender
    actually timed.  The read belongs on the class being validated
    (``as_Base.carry_absent_times_on_inbound``), which is the only place that
    knows both that the object has timestamps and which they are.
    """
    status: dict[str, Any] = {
        "id": "https://example.org/cases/c1/statuses/1",
        "published": SENDER_PUBLISHED,
    }
    ABSENT[spelling](status)
    case = dict(KINDS["VulnerabilityCase"][0])
    case["caseStatuses"] = [status]

    parsed = parse_activity(_body(case))

    parsed_case = getattr(parsed, "object_", None)
    assert parsed_case is not None
    nested = parsed_case.case_statuses[0]
    assert nested.published is None
    assert nested.updated is None


@pytest.mark.spec("CLP-15-007")
def test_a_class_without_timestamps_is_untouched_by_the_inbound_read():
    """The read only names fields the validated class declares.

    Injecting ``published``/``updated`` blindly would hand a timestamp-less
    class keys it refuses under ``extra="forbid"``, turning an absent time into
    a parse failure for an object that never had one.  ``as_Base`` declares no
    timestamp at all, so it is the case that would break.
    """
    data = {"id": "https://example.org/things/1", "name": "no times here"}

    result = absent_times_as_none(as_Base, dict(data))

    assert result == data
