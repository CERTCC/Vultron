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

from vultron.core.use_cases.triggers.sync import extract_activity_snapshot
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
