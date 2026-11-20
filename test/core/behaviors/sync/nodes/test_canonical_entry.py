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

"""Unit tests for ``_validate_canonical_entry`` (CLP-07).

Mirrors ``vultron/core/behaviors/sync/nodes/canonical_entry.py``, which was
split out of ``chain.py`` (CS-18-004).  Tests that exercise the
guard *through* ``CreateLogEntryNode`` stay in ``test_chain.py``; these call
the validator directly.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

import pytest

from test.core.behaviors.sync.nodes.conftest import (
    CASE_ID,
    OWNER_ACTOR_ID,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _snapshot_object_types,
    _validate_canonical_entry,
)
from vultron.core.models._helpers import now_utc
from vultron.errors import VultronCanonicalEntryError


def _note_snapshot_with_actor(actor_id: str) -> dict[str, object]:
    return {
        "type": "Add",
        "actor": actor_id,
        # CLP-07-011: the commit boundary requires a claimed timestamp on every
        # recorded snapshot, so every fixture here carries one.
        "published": now_utc().isoformat(),
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/note-prov",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }


@pytest.mark.spec("CLP-07-012")
def test_validate_canonical_entry_rejects_empty_snapshot():
    with pytest.raises(VultronCanonicalEntryError):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot={},
            semantic_type="note_added",
            at=datetime.now(UTC),
        )


@pytest.mark.spec("VAM-01-011", "RSH-08-004")
def test_validate_canonical_entry_refuses_a_create_note_snapshot():
    """``Add(Note)`` is a note's one entry; a ``Create(Note)`` is not canonical."""
    snapshot = {**_note_snapshot_with_actor(OWNER_ACTOR_ID), "type": "Create"}

    with pytest.raises(VultronCanonicalEntryError, match="not canonical"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=snapshot,
            semantic_type="create_note",
            at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# CLP-14 timestamp invariant tests
# ---------------------------------------------------------------------------

_CASE_PUBLISHED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_ENTRY_PUBLISHED = datetime(2026, 1, 1, 12, 1, 0, tzinfo=UTC)


def _ts_snapshot(published: str | datetime | None = _ENTRY_PUBLISHED) -> dict:
    snap: dict = {
        "type": "Add",
        "actor": OWNER_ACTOR_ID,
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/n1",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }
    if published is not None:
        snap["published"] = (
            published.isoformat()
            if isinstance(published, datetime)
            else published
        )
    return snap


def _call_with_ts(
    snapshot: dict,
    *,
    case_published: datetime | None = _CASE_PUBLISHED,
    prev_actor_published: datetime | None = None,
    future_tolerance: timedelta | None = None,
    staleness_window: timedelta | None = None,
    skew_tolerance: timedelta = timedelta(minutes=5),
) -> None:
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="note_added",
        case_published=case_published,
        prev_actor_published=prev_actor_published,
        future_tolerance=future_tolerance,
        staleness_window=staleness_window,
        skew_tolerance=skew_tolerance,
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-011")
def test_clp07_011_rejects_missing_published():
    """A snapshot with no ``published`` is not the verbatim AS2 activity.

    Cited as CLP-07-011, not CLP-14-002: CLP-14-002 constrains
    ``CaseLedgerEntry.published`` (the commit stamp, enforced by the model),
    while this is the *asserted activity's* own field.
    """
    with pytest.raises(VultronCanonicalEntryError, match="CLP-07-011"):
        _call_with_ts(_ts_snapshot(published=None))


@pytest.mark.spec("CLP-07-011")
def test_clp07_011_rejects_malformed_published():
    with pytest.raises(VultronCanonicalEntryError, match="CLP-07-011"):
        _call_with_ts(_ts_snapshot(published="not-a-date"))


@pytest.mark.spec("CLP-07-011")
def test_clp07_011_accepts_valid_iso_published():
    _call_with_ts(_ts_snapshot())


@pytest.mark.spec("CLP-07-011")
def test_clp07_011_accepts_datetime_object_published():
    snap = _ts_snapshot()
    snap["published"] = _ENTRY_PUBLISHED
    _call_with_ts(snap)


@pytest.mark.spec("CLP-14-013")
def test_clp14_006_rejects_entry_before_case():
    before_case = _CASE_PUBLISHED - timedelta(minutes=6)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-013"):
        _call_with_ts(_ts_snapshot(published=before_case))


@pytest.mark.spec("CLP-14-013")
def test_clp14_006_accepts_entry_equal_to_case_published():
    _call_with_ts(_ts_snapshot(published=_CASE_PUBLISHED))


@pytest.mark.spec("CLP-14-013")
def test_clp14_006_accepts_entry_within_skew_tolerance():
    """Unsynchronised clocks get slack; ADR-0079 rejected wall-clock ordering."""
    before_case = _CASE_PUBLISHED - timedelta(minutes=2)
    _call_with_ts(
        _ts_snapshot(published=before_case),
        skew_tolerance=timedelta(minutes=5),
    )


@pytest.mark.spec("CLP-14-013")
def test_clp14_006_skipped_when_case_published_is_none():
    """The genesis entry commits before the case is readable; that is not a bug."""
    _call_with_ts(
        _ts_snapshot(published=_CASE_PUBLISHED - timedelta(days=365)),
        case_published=None,
    )


@pytest.mark.spec("CLP-14-013")
def test_clp14_006_message_renders_case_published_in_utc():
    """The violation message renders case_published in UTC (ISSUE-3222).

    An aware non-UTC ``case_published`` (the parent case chose its own offset)
    passed through ``as_utc`` kept that offset, so the message compared a
    ``+00:00`` entry against a ``+05:30`` case and read as though the guard
    compared unlike quantities. ``parse_published`` converts it to UTC first.
    """
    tz_530 = timezone(timedelta(hours=5, minutes=30))
    case_published = datetime(2026, 1, 1, 12, 0, 0, tzinfo=tz_530)  # 06:30 UTC
    entry_before = datetime(2026, 1, 1, 6, 0, 0, tzinfo=UTC)
    with pytest.raises(
        VultronCanonicalEntryError, match="CLP-14-013"
    ) as excinfo:
        _call_with_ts(
            _ts_snapshot(published=entry_before),
            case_published=case_published,
        )
    message = str(excinfo.value)
    assert "+05:30" not in message
    assert "06:30:00+00:00" in message


@pytest.mark.spec("CLP-15-003")
@pytest.mark.spec("CLP-15-005")
def test_clp15_003_reports_timestamp_regression_without_refusing(caplog):
    """A regression is reported, not refused (CLP-15-005).

    Arrival order is not causal order, so refusing on this signal dropped
    well-formed assertions — and dropped them entirely, since the guarded commit
    runs before the effect nodes (CLP-10-006).
    """
    prev = _ENTRY_PUBLISHED + timedelta(seconds=10)
    with caplog.at_level(
        logging.INFO,
        logger="vultron.core.behaviors.sync.nodes.canonical_entry",
    ):
        _call_with_ts(_ts_snapshot(), prev_actor_published=prev)

    assert [r for r in caplog.records if "CLP-15-003" in r.getMessage()]


@pytest.mark.spec("CLP-15-003")
def test_clp15_003_accepts_non_decreasing_timestamp():
    prev = _ENTRY_PUBLISHED - timedelta(seconds=1)
    _call_with_ts(_ts_snapshot(), prev_actor_published=prev)


@pytest.mark.spec("CLP-15-003")
def test_clp15_003_accepts_equal_timestamps():
    _call_with_ts(_ts_snapshot(), prev_actor_published=_ENTRY_PUBLISHED)


@pytest.mark.spec("CLP-14-007")
def test_clp14_007_rejects_future_timestamp():
    far_future = datetime.now(tz=UTC) + timedelta(hours=1)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-007"):
        _call_with_ts(
            _ts_snapshot(published=far_future),
            case_published=_CASE_PUBLISHED,
            future_tolerance=timedelta(minutes=5),
        )


@pytest.mark.spec("CLP-14-007")
def test_clp14_007_skipped_when_tolerance_is_none():
    far_future = datetime.now(tz=UTC) + timedelta(hours=1)
    _call_with_ts(
        _ts_snapshot(published=far_future),
        case_published=_CASE_PUBLISHED,
        future_tolerance=None,
        staleness_window=None,
    )


@pytest.mark.spec("CLP-14-008")
def test_clp14_008_rejects_stale_timestamp():
    stale = datetime.now(tz=UTC) - timedelta(days=30)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-008"):
        _call_with_ts(
            _ts_snapshot(published=stale),
            case_published=stale - timedelta(days=1),
            staleness_window=timedelta(days=7),
        )


@pytest.mark.spec("CLP-14-008")
def test_clp14_008_skipped_when_window_is_none():
    stale = datetime.now(tz=UTC) - timedelta(days=30)
    _call_with_ts(
        _ts_snapshot(published=stale),
        case_published=stale - timedelta(days=1),
        future_tolerance=None,
        staleness_window=None,
    )


@pytest.mark.spec("CLP-07-011")
def test_timestamp_checks_are_not_gated_on_case_published():
    """Omitting ``case_published`` must NOT bypass the other checks.

    This is the regression the whole of ISSUE-2824 came down to: the guard used
    to run only ``if case_published is not None``, and the sole production call
    site never passed it, so nothing was ever checked.  Each check now gates
    itself on the context it needs.
    """
    with pytest.raises(VultronCanonicalEntryError, match="CLP-07-011"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=_ts_snapshot(published=None),
            semantic_type="note_added",
            at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# Bare ``target`` naming the entry's own case (CLP-07-018, VM-08-003, #2654)
# ---------------------------------------------------------------------------


def _offer_participant_snapshot(target: object) -> dict[str, object]:
    """``Offer(CaseParticipant)[target=VulnerabilityCase]`` as the factory emits it."""
    return {
        "type": "Offer",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "CaseParticipant",
            "id": "https://example.org/actors/vendor#participant",
        },
        "target": target,
        "context": CASE_ID,
    }


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("CLP-07-018")
def test_bare_target_equal_to_the_case_uri_is_accepted():
    """A ``target`` that is the case URI names what every replica holds.

    The factories address a case by its URI (AKM-02-003) and the snapshot is
    the factory's exact blob (VM-08-003), so the commit boundary accepts it
    rather than forcing core to strip it (#2654).
    """
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_offer_participant_snapshot(CASE_ID),
        semantic_type="offer_case_participant",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("AKM-02-002")
def test_bare_target_naming_a_held_object_is_recorded_as_received():
    """``Add(ParticipantStatus)`` with a bare status history target is not refused.

    The target is ``<participant>/statuses``, the history of a participant
    the case's replicas hold (ADR-0204), so its sender may name it by URI
    (AKM-02-002).  The commit boundary records the reference as it arrived;
    it neither inlines it nor refuses it (CLP-07-006, ADR-0107).
    """
    snapshot = {
        "type": "Add",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "ParticipantStatus",
            "id": "https://example.org/statuses/status-1",
        },
        "target": "https://example.org/actors/vendor#participant/statuses",
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="add_participant_status_to_participant",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-018")
def test_a_bare_reference_nested_in_the_object_is_recorded_as_received():
    """Only the entry's own ``object`` must be inline; nested slots are as sent.

    An answered Invite names its invitee by URI (AKM-02-002), and the
    snapshot keeps it so.
    """
    snapshot = {
        "type": "Accept",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "Invite",
            "id": "https://example.org/activities/invite-1",
            "object": "https://example.org/actors/vendor",
            "target": CASE_ID,
        },
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="rm_accept_invite_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-018")
def test_bare_target_naming_the_case_is_accepted_when_nested():
    """``Accept(Offer(CaseParticipant))`` carries the same bare case target inside."""
    inner = _offer_participant_snapshot(CASE_ID)
    inner["id"] = "https://example.org/activities/offer-1"
    snapshot = {
        "type": "Accept",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": inner,
        "target": CASE_ID,
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="accept_actor_recommendation",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-018")
def test_bare_object_is_still_refused():
    """The entry's ``object`` travels inline: its type is half the signature."""
    snapshot = _offer_participant_snapshot(CASE_ID)
    snapshot["object"] = "https://example.org/actors/vendor#participant"
    with pytest.raises(VultronCanonicalEntryError, match="object"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=snapshot,
            semantic_type="offer_case_participant",
            at=datetime.now(UTC),
        )


def test_a_full_case_invite_resolves_to_the_invite_of_a_case_signature():
    """``Invite(whole VulnerabilityCase)[target=Actor]`` signs as an Invite
    of a case: ``("Invite", "VulnerabilityCase")`` (ADR-0205)."""
    snapshot = {
        "type": "Invite",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {"type": "VulnerabilityCase", "id": CASE_ID},
        "target": {
            "type": "Organization",
            "id": "https://example.org/actors/vendor",
        },
        "context": CASE_ID,
    }
    assert _snapshot_object_types(snapshot, CASE_ID) == ("VulnerabilityCase",)
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="invite_actor_to_full_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CM-11-038")
def test_a_stub_invite_resolves_to_the_invite_of_a_case_signature():
    """``Invite(VulnerabilityCase preview)[target=Actor]`` is an Invite of a case.

    The stub Invite names the case in its ``object``, a typed reference
    carrying the case's preview (ADR-0205), so the ledger records it under
    the case's type, as the full-case Invite.
    """
    snapshot = {
        "type": "Invite",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "VulnerabilityCase",
            "id": CASE_ID,
            "preview": {
                "type": "CasePreview",
                "id": "https://example.org/previews/1",
                "summary": "A case to join",
            },
        },
        "target": {
            "type": "Organization",
            "id": "https://example.org/actors/vendor",
        },
        "context": CASE_ID,
    }
    assert _snapshot_object_types(snapshot, CASE_ID) == ("VulnerabilityCase",)
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="invite_actor_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("VM-03-006")
def test_a_received_type_list_signs_as_the_type_it_names():
    """A received body is recorded verbatim (VM-08-002), so its ``type`` may
    be a list; the signature reads each name it carries (ADR-0196)."""
    snapshot = {
        "type": ["Foo", "Invite"],
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {"type": ["Bar", "VulnerabilityCase"], "id": CASE_ID},
        "target": "https://example.org/actors/vendor",
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="invite_actor_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("VAM-07-003")
def test_remove_note_snapshot_is_a_canonical_signature():
    """``Remove(Note)[origin=VulnerabilityCase]`` is accepted as a canonical payload."""
    snapshot = {
        "type": "Remove",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "Note",
            "id": "https://example.org/notes/note-prov",
        },
        "origin": CASE_ID,
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        semantic_type="remove_note_from_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("VP-03-009")
@pytest.mark.spec("RMB-08-007")
def test_ack_report_snapshot_is_not_a_canonical_signature():
    """RK, ``Read(Offer(VulnerabilityReport))``, is never ledgered."""
    snapshot = {
        "type": "Read",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "Offer",
            "id": "https://example.org/offers/offer-ack",
            "context": CASE_ID,
        },
        "context": CASE_ID,
    }
    with pytest.raises(VultronCanonicalEntryError, match="not canonical"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=snapshot,
            semantic_type="ack_report",
            at=datetime.now(UTC),
        )


# ---------------------------------------------------------------------------
# A received snapshot is the body as sent (CLP-07-011, ADR-0107)
# ---------------------------------------------------------------------------


def _note_snapshot(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "type": "Add",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {"type": "Note", "id": "https://example.org/notes/n1"},
        "target": CASE_ID,
        "context": CASE_ID,
    }
    snapshot.update(overrides)
    return {k: v for k, v in snapshot.items() if v is not None}


@pytest.mark.spec("CLP-07-011")
def test_a_snapshot_naming_no_context_is_accepted():
    """The entry names its case on the envelope; the body need not.

    The Offer that opens a case predates it, so its body carries no
    ``context``, and nothing writes one in.
    """
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_note_snapshot(context=None),
        semantic_type="add_note_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-011")
def test_a_context_naming_the_case_inline_is_accepted():
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_note_snapshot(
            context={"type": "VulnerabilityCase", "id": CASE_ID}
        ),
        semantic_type="add_note_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-007")
def test_a_context_naming_another_case_inline_is_refused():
    with pytest.raises(
        VultronCanonicalEntryError, match="not the entry's case"
    ):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=_note_snapshot(
                context={
                    "type": "VulnerabilityCase",
                    "id": "https://example.org/cases/other",
                }
            ),
            semantic_type="add_note_to_case",
            at=datetime.now(UTC),
        )


@pytest.mark.spec("CLP-07-003")
@pytest.mark.spec("CP-01-010")
def test_an_inline_actor_profile_is_accepted():
    """A Create(CaseProposal) names its actor by inline profile, as sent."""
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_note_snapshot(
            actor={"type": "Organization", "id": OWNER_ACTOR_ID}
        ),
        semantic_type="add_note_to_case",
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-017")
def test_an_actor_naming_no_id_is_refused():
    with pytest.raises(VultronCanonicalEntryError, match="actor URI"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=_note_snapshot(
                actor={"type": "Organization", "name": "nobody"}
            ),
            semantic_type="add_note_to_case",
            at=datetime.now(UTC),
        )


_NAMED_ACTOR = {
    "type": "Organization",
    "id": "https://example.org/actors/vendor",
}


def _actor_act(verb: str, **slots: object) -> dict[str, object]:
    return {
        "type": verb,
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": dict(_NAMED_ACTOR),
        "context": CASE_ID,
        **slots,
    }


@pytest.mark.spec("CM-31-024")
@pytest.mark.parametrize(
    ("slots", "expected"),
    [
        (
            {"target": {"type": "VulnerabilityCase", "id": CASE_ID}},
            ("VulnerabilityCase", "Actor", "Organization"),
        ),
        ({"target": CASE_ID}, ("VulnerabilityCase", "Actor", "Organization")),
        ({"origin": CASE_ID}, ("Actor", "Organization")),
    ],
    ids=["typed-target", "case-id-target", "no-target"],
)
def test_an_act_on_an_actor_also_signs_as_an_act_on_actor(slots, expected):
    """An act whose object is an actor yields the target's types, then
    ``Actor``, then the actor's own types, so the Case Owner's
    ``Remove(<Actor>)`` and ``Add(<Actor>)`` resolve whatever actor type they
    carry (ADR-0199)."""
    assert _snapshot_object_types(_actor_act("Add", **slots), CASE_ID) == (
        expected
    )


def test_an_object_typed_actor_is_not_named_twice():
    snapshot = _actor_act("Remove", origin=CASE_ID)
    snapshot["object"] = {"type": "Actor", "id": _NAMED_ACTOR["id"]}

    assert _snapshot_object_types(snapshot, CASE_ID) == ("Actor",)


@pytest.mark.spec("CM-31-024")
@pytest.mark.spec("CM-31-044")
@pytest.mark.parametrize(
    ("verb", "slots", "semantic_type"),
    [
        ("Remove", {"origin": CASE_ID}, "remove_participant_from_case"),
        ("Add", {"target": CASE_ID}, "reinstate_participant_in_case"),
    ],
    ids=["removal", "reinstatement"],
)
def test_the_owners_move_of_an_actor_is_canonical(verb, slots, semantic_type):
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_actor_act(verb, **slots),
        semantic_type=semantic_type,
        at=datetime.now(UTC),
    )


@pytest.mark.spec("CLP-07-012")
def test_another_act_on_an_actor_stays_non_canonical():
    """Adding ``Actor`` to the types admits only the listed ``Actor`` pairs."""
    with pytest.raises(VultronCanonicalEntryError, match="is not canonical"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=_actor_act("Like"),
            semantic_type="like_actor",
            at=datetime.now(UTC),
        )
