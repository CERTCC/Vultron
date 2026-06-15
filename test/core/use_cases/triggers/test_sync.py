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
"""Unit tests for SYNC trigger helpers."""

from typing import Any, cast
from unittest.mock import patch

import pytest

from vultron.core.models.pending_assertion import PendingAssertionStore
from vultron.core.use_cases.triggers.sync import (
    commit_log_entry_trigger,
    extract_activity_snapshot,
)
from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    VulnerabilityReport,
)


class _FakeWireActivity:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def model_dump(self, **_: object) -> dict[str, Any]:
        return dict(self._payload)


class _FakeEvent:
    def __init__(self, activity: object | None) -> None:
        self.activity = activity


def test_extract_activity_snapshot_returns_empty_without_activity() -> None:
    event = _FakeEvent(activity=None)
    assert extract_activity_snapshot(cast(Any, event)) == {}


def test_extract_activity_snapshot_inlines_nested_reference_fields(datalayer):
    embargo = EmbargoEvent(context="https://example.org/cases/case-001")
    report = VulnerabilityReport(
        name="TEST-REPORT-001",
        content="Demo content",
        context="https://example.org/cases/case-001",
    )
    datalayer.save(embargo)
    datalayer.save(report)

    payload = {
        "id": "https://example.org/activities/engage-001",
        "type": "Join",
        "context": "https://example.org/cases/case-001",
        "object": {
            "id": "https://example.org/statuses/status-001",
            "type": "ParticipantStatus",
            "activeEmbargo": embargo.id_,
            "proposedEmbargoes": [embargo.id_],
            "vulnerabilityReports": [report.id_],
        },
    }
    event = _FakeEvent(activity=_FakeWireActivity(payload))

    snapshot = extract_activity_snapshot(cast(Any, event), dl=datalayer)
    status_obj = snapshot["object"]

    assert snapshot["context"] == "https://example.org/cases/case-001"
    assert isinstance(status_obj["activeEmbargo"], dict)
    assert status_obj["activeEmbargo"]["id"] == embargo.id_
    assert isinstance(status_obj["proposedEmbargoes"][0], dict)
    assert status_obj["proposedEmbargoes"][0]["id"] == embargo.id_
    assert isinstance(status_obj["vulnerabilityReports"][0], dict)
    assert status_obj["vulnerabilityReports"][0]["id"] == report.id_


def test_extract_activity_snapshot_does_not_inline_cross_context_refs(
    datalayer,
):
    embargo = EmbargoEvent(context="https://example.org/cases/other-case")
    datalayer.save(embargo)

    payload = {
        "id": "https://example.org/activities/engage-001",
        "type": "Join",
        "context": "https://example.org/cases/case-001",
        "object": {
            "id": "https://example.org/statuses/status-001",
            "type": "ParticipantStatus",
            "activeEmbargo": embargo.id_,
        },
    }
    event = _FakeEvent(activity=_FakeWireActivity(payload))

    snapshot = extract_activity_snapshot(cast(Any, event), dl=datalayer)
    status_obj = snapshot["object"]

    assert status_obj["activeEmbargo"] == embargo.id_


# ---------------------------------------------------------------------------
# commit_log_entry_trigger — pending_assertions suppression
# ---------------------------------------------------------------------------

CASE_ID = "https://example.org/cases/case-001"
ACTOR_ID = "https://example.org/actors/case-actor"
OBJECT_ID = "https://example.org/activities/act-001"
EVENT_TYPE = "submit_report"


@pytest.fixture
def fresh_store():
    return PendingAssertionStore(timeout_seconds=180)


@pytest.fixture
def zero_store():
    return PendingAssertionStore(timeout_seconds=0)


def test_commit_adds_to_pending_store_on_success(datalayer, fresh_store):
    """After a new commit, the entry is added to pending_assertions."""
    commit_log_entry_trigger(
        case_id=CASE_ID,
        object_id=OBJECT_ID,
        event_type=EVENT_TYPE,
        actor_id=ACTOR_ID,
        dl=cast(Any, datalayer),
        pending_assertions=fresh_store,
    )
    assert fresh_store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)


def test_commit_suppressed_when_pending_and_unexpired(datalayer, fresh_store):
    """Second call is suppressed while the pending assertion is unexpired."""
    # First commit — seeds the DataLayer and pending store
    entry1 = commit_log_entry_trigger(
        case_id=CASE_ID,
        object_id=OBJECT_ID,
        event_type=EVENT_TYPE,
        actor_id=ACTOR_ID,
        dl=cast(Any, datalayer),
        pending_assertions=fresh_store,
    )
    # Second call — should be suppressed (returns same entry, no re-fan-out)
    with patch(
        "vultron.core.use_cases.triggers.sync._fan_out_log_entry"
    ) as mock_fan_out:
        entry2 = commit_log_entry_trigger(
            case_id=CASE_ID,
            object_id=OBJECT_ID,
            event_type=EVENT_TYPE,
            actor_id=ACTOR_ID,
            dl=cast(Any, datalayer),
            pending_assertions=fresh_store,
        )
    mock_fan_out.assert_not_called()
    assert entry2.id_ == entry1.id_


def test_commit_not_suppressed_when_store_zero_timeout(datalayer, zero_store):
    """Zero timeout disables suppression; second call fans out again."""
    commit_log_entry_trigger(
        case_id=CASE_ID,
        object_id=OBJECT_ID,
        event_type=EVENT_TYPE,
        actor_id=ACTOR_ID,
        dl=cast(Any, datalayer),
        pending_assertions=zero_store,
    )
    # Should NOT be suppressed — zero timeout means no suppression
    assert not zero_store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)


def test_commit_cleared_entry_allows_re_add(datalayer, fresh_store):
    """After clearing, a new commit re-adds the entry to pending."""
    commit_log_entry_trigger(
        case_id=CASE_ID,
        object_id=OBJECT_ID,
        event_type=EVENT_TYPE,
        actor_id=ACTOR_ID,
        dl=cast(Any, datalayer),
        pending_assertions=fresh_store,
    )
    # Simulate round-trip confirmation clearing the pending assertion
    fresh_store.clear(CASE_ID, EVENT_TYPE, OBJECT_ID)
    assert not fresh_store.is_suppressed(CASE_ID, EVENT_TYPE, OBJECT_ID)
