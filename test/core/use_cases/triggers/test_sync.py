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

import pytest
from typing import Any

from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models.activity import VultronActivity
from vultron.core.use_cases._helpers import build_activity_payload_snapshot
from vultron.errors import VultronValidationError
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)
from vultron.core.models._helpers import days_from_now_utc

_PORT = As2WireRenderAdapter()


def _activity(payload: dict[str, Any]) -> VultronActivity:
    """A core activity whose ``object`` is carried as the given dict."""
    return VultronActivity(
        id_=payload["id"],
        type_=payload["type"],
        actor="https://example.org/actors/participant",
        context=payload["context"],
        object_=payload["object"],
    )


@pytest.mark.spec("CLP-07-011")
def test_extract_activity_snapshot_returns_empty_without_activity() -> None:
    assert (
        build_activity_payload_snapshot(None, None, wire_render_port=_PORT)
        == {}
    )


@pytest.mark.spec("ARCH-20-001")
@pytest.mark.spec("CLP-07-009")
def test_extract_activity_snapshot_is_the_ports_rendering(datalayer) -> None:
    """The snapshot is the port's AS2 rendering, never a core-side dump."""
    activity = _activity(
        {
            "id": "https://example.org/activities/engage-002",
            "type": "Join",
            "context": "https://example.org/cases/case-001",
            "object": "https://example.org/statuses/unknown",
        }
    )

    snapshot = build_activity_payload_snapshot(
        activity, datalayer, wire_render_port=_PORT
    )

    assert snapshot == _PORT.render(activity)


@pytest.mark.spec("ARCH-20-003")
@pytest.mark.spec("CLP-07-009")
def test_extract_activity_snapshot_refuses_an_object_with_no_as2_shape() -> (
    None
):
    """A model the port cannot render fails closed instead of dumping."""

    class _NotAnAs2Object:
        def model_dump(self, **_: object) -> dict[str, Any]:
            return {"type": "Join"}

    with pytest.raises(VultronValidationError):
        build_activity_payload_snapshot(
            _NotAnAs2Object(), None, wire_render_port=_PORT
        )


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-011")
def test_extract_activity_snapshot_inlines_nested_reference_fields(datalayer):
    embargo = as_EmbargoEvent(
        context="https://example.org/cases/case-001",
        end_time=days_from_now_utc(45),
    )
    report = as_VulnerabilityReport(
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

    snapshot = build_activity_payload_snapshot(
        _activity(payload), datalayer, wire_render_port=_PORT
    )
    status_obj = snapshot["object"]

    assert snapshot["context"] == "https://example.org/cases/case-001"
    assert isinstance(status_obj["activeEmbargo"], dict)
    assert status_obj["activeEmbargo"]["id"] == embargo.id_
    assert isinstance(status_obj["proposedEmbargoes"][0], dict)
    assert status_obj["proposedEmbargoes"][0]["id"] == embargo.id_
    assert isinstance(status_obj["vulnerabilityReports"][0], dict)
    assert status_obj["vulnerabilityReports"][0]["id"] == report.id_


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-007")
def test_extract_activity_snapshot_does_not_inline_cross_context_refs(
    datalayer,
):
    embargo = as_EmbargoEvent(
        context="https://example.org/cases/other-case",
        end_time=days_from_now_utc(45),
    )
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

    snapshot = build_activity_payload_snapshot(
        _activity(payload), datalayer, wire_render_port=_PORT
    )
    status_obj = snapshot["object"]

    assert status_obj["activeEmbargo"] == embargo.id_


# ---------------------------------------------------------------------------
# commit_log_entry_trigger — removed (BT-06-006)
# ---------------------------------------------------------------------------
# commit_log_entry_trigger was removed: all ledger commits now go through
# CommitCaseLedgerEntryNode via BTBridge.execute_with_setup().
# Per SYNC-11-004, the CaseActor MUST NOT use the pending-assertion store
# for its own commits; DataLayer idempotency (_find_equivalent_recorded_entry)
# already guards against duplicate CaseActor commits.
#
# Participant-side pending assertions are recorded in trigger use cases
# (e.g., SvcAddNoteToCaseUseCase) after the activity is successfully
# enqueued, and cleared in AnnounceLedgerEntryReceivedUseCase when the
# matching Announce(CaseLedgerEntry) arrives — see SYNC-11-002/003 and
# test/core/use_cases/triggers/test_note.py for the end-to-end test.

CASE_ID = "https://example.org/cases/case-001"
ACTOR_ID = "https://example.org/actors/case-actor"
OBJECT_ID = "https://example.org/activities/act-001"
EVENT_TYPE = "submit_report"
