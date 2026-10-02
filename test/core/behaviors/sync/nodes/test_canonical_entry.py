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

"""Unit tests for ``_validate_canonical_entry`` (CLP-07, CLP-12).

Mirrors ``vultron/core/behaviors/sync/nodes/canonical_entry.py``, which was
split out of ``chain.py`` (BTND-07-002, CS-18-004).  Tests that exercise the
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
    _snapshot_object_type,
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
            event_type="note_added",
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
        event_type="note_added",
        case_published=case_published,
        prev_actor_published=prev_actor_published,
        future_tolerance=future_tolerance,
        staleness_window=staleness_window,
        skew_tolerance=skew_tolerance,
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


@pytest.mark.spec("CLP-14-006")
def test_clp14_006_rejects_entry_before_case():
    before_case = _CASE_PUBLISHED - timedelta(minutes=6)
    with pytest.raises(VultronCanonicalEntryError, match="CLP-14-006"):
        _call_with_ts(_ts_snapshot(published=before_case))


@pytest.mark.spec("CLP-14-006")
def test_clp14_006_accepts_entry_equal_to_case_published():
    _call_with_ts(_ts_snapshot(published=_CASE_PUBLISHED))


@pytest.mark.spec("CLP-14-006")
def test_clp14_006_accepts_entry_within_skew_tolerance():
    """Unsynchronised clocks get slack; ADR-0079 rejected wall-clock ordering."""
    before_case = _CASE_PUBLISHED - timedelta(minutes=2)
    _call_with_ts(
        _ts_snapshot(published=before_case),
        skew_tolerance=timedelta(minutes=5),
    )


@pytest.mark.spec("CLP-14-006")
def test_clp14_006_skipped_when_case_published_is_none():
    """The genesis entry commits before the case is readable; that is not a bug."""
    _call_with_ts(
        _ts_snapshot(published=_CASE_PUBLISHED - timedelta(days=365)),
        case_published=None,
    )


@pytest.mark.spec("CLP-14-006")
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
        VultronCanonicalEntryError, match="CLP-14-006"
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
            event_type="note_added",
        )


# ---------------------------------------------------------------------------
# Bare ``target`` naming the entry's own case (CLP-07-006, VM-08-003, #2654)
# ---------------------------------------------------------------------------


def _offer_participant_snapshot(target: object) -> dict[str, object]:
    """``Offer(CaseParticipant, target=<case>)`` as the factory emits it."""
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
def test_bare_target_equal_to_the_case_uri_is_accepted():
    """A ``target`` that is the case URI names what every replica holds.

    The factories address a case by its URI (AKM-02-003) and the snapshot is
    the factory's exact blob (VM-08-003), so the commit boundary accepts it
    rather than forcing core to strip it (#2654).
    """
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=_offer_participant_snapshot(CASE_ID),
        event_type="offer_case_participant",
    )


@pytest.mark.spec("CLP-07-006")
def test_bare_target_naming_another_case_is_refused():
    with pytest.raises(VultronCanonicalEntryError, match="target"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=_offer_participant_snapshot(
                "https://example.org/cases/some-other-case"
            ),
            event_type="offer_case_participant",
        )


@pytest.mark.spec("CLP-07-006")
def test_bare_target_naming_the_case_is_accepted_when_nested():
    """``Accept(Offer(..., target=<case>))`` carries the same bare target inside."""
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
        event_type="accept_actor_recommendation",
    )


@pytest.mark.spec("CLP-07-006")
def test_bare_object_is_still_refused():
    """Only ``target`` gets the case-URI allowance; ``object`` never does."""
    snapshot = _offer_participant_snapshot(CASE_ID)
    snapshot["object"] = "https://example.org/actors/vendor#participant"
    with pytest.raises(VultronCanonicalEntryError, match="object"):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=snapshot,
            event_type="offer_case_participant",
        )


def test_invite_with_a_bare_case_target_resolves_to_the_case_signature():
    """``Invite(Actor, target=<case uri>)`` is ``("Invite", "VulnerabilityCase")``."""
    snapshot = {
        "type": "Invite",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "Organization",
            "id": "https://example.org/actors/vendor",
        },
        "target": CASE_ID,
        "context": CASE_ID,
    }
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        event_type="invite_actor_to_case",
    )


@pytest.mark.spec("CM-11-013")
def test_invite_with_a_case_stub_target_resolves_to_the_stub_signature():
    """``Invite(Actor, target=VulnerabilityCaseStub)`` is its own signature.

    The stub Invite is told apart from the full-case Invite by its target's
    ``type`` (CM-11-013), and the ledger records it under that type.
    """
    snapshot = {
        "type": "Invite",
        "actor": OWNER_ACTOR_ID,
        "published": now_utc().isoformat(),
        "object": {
            "type": "Organization",
            "id": "https://example.org/actors/vendor",
        },
        "target": {
            "type": "VulnerabilityCaseStub",
            "id": f"{CASE_ID}/stub",
            "caseId": CASE_ID,
        },
        "context": CASE_ID,
    }
    assert _snapshot_object_type(snapshot, CASE_ID) == "VulnerabilityCaseStub"
    _validate_canonical_entry(
        case_id=CASE_ID,
        payload_snapshot=snapshot,
        event_type="invite_actor_to_case",
    )
