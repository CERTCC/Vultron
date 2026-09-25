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
"""Ingress rehydration carries the received evidence, untouched (VM-08-002).

``FastAPIIngressAdapter.rehydrate`` returns a *different* object from the one
the parser sealed: a by-ID re-read built from storage, or an in-place hydration
for ``Announce(CaseLedgerEntry)``.  Neither is the received artifact, so the
evidence must be carried onto it, and it must still be the body as it arrived —
bare references included — rather than the hydrated form (ISSUE-3584).
"""

import copy
from typing import Any

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as CaseLedgerEntry,
)

ACTOR = "https://example.org/actors/finder"
REPORT_ID = "https://example.org/reports/r1"
CASE_ID = "https://example.org/cases/c1"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        db_url="sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


def _offer_of_stored_report(dl: SqliteDataLayer) -> dict[str, Any]:
    """An ``Offer`` naming a report the receiver already holds by bare ID."""
    dl.save(
        VulnerabilityReport(
            id_=REPORT_ID, name="r", content="stored", attributed_to=ACTOR
        )
    )
    return {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Offer",
        "id": "https://example.org/activities/offer-1",
        "actor": ACTOR,
        "published": "2026-01-02T03:04:05+00:00",
        "object": REPORT_ID,
        "to": ["https://example.org/actors/vendor"],
    }


@pytest.mark.spec("VM-08-002")
def test_by_id_rehydration_carries_the_evidence_as_received(
    dl: SqliteDataLayer,
):
    """The re-read copy carries the body with its bare ID, not the expansion."""
    body = _offer_of_stored_report(dl)
    received = copy.deepcopy(body)
    adapter = FastAPIIngressAdapter(dl=dl, body=body)
    artifact = adapter.parse(body)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed is not artifact
    report = getattr(routed, "object_")
    assert isinstance(report, VulnerabilityReport), "precondition: hydrated"
    evidence = routed.received_evidence
    assert evidence == received
    assert evidence is not None and evidence["object"] == REPORT_ID

    report.content = "edited after hydration"

    assert routed.received_evidence == received
    assert artifact.received_evidence == received


@pytest.mark.spec("VM-08-002")
def test_resend_under_a_held_id_routes_without_this_body_evidence(
    dl: SqliteDataLayer,
):
    """A second body under an id already stored does not lend it its evidence.

    The by-ID read rebuilds the *first* delivery, so sealing the second body's
    text onto it would describe an activity other than the one routed.
    """
    first = _offer_of_stored_report(dl)
    first["summary"] = "first"
    FastAPIIngressAdapter(dl=dl, body=first).parse(first)
    second = {**copy.deepcopy(first), "summary": "second"}
    adapter = FastAPIIngressAdapter(dl=dl, body=second)
    artifact = adapter.parse(second)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed.summary == "first", "precondition: stored copy routed"
    assert routed.received_evidence is None
    assert artifact.received_evidence == second


@pytest.mark.spec("VM-08-002")
def test_in_place_hydration_carries_the_evidence(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
):
    """``Announce(CaseLedgerEntry)`` skips the re-read and still keeps it.

    ``SqliteDataLayer.hydrate`` happens to return the object it is given, which
    would let the evidence survive without being carried at all, so ``hydrate``
    is made to return a fresh copy with no evidence of its own.
    """

    def _fresh_copy(obj: Any) -> Any:
        fresh = obj.model_copy(deep=True)
        fresh._received_evidence = None
        return fresh

    monkeypatch.setattr(dl, "hydrate", _fresh_copy)
    entry = CaseLedgerEntry(
        id_=f"{CASE_ID}/log/entry-1",
        case_id=CASE_ID,
        log_object_id=ACTOR,
        event_type="accept_invite_actor_to_case",
        payload_snapshot={"actor": ACTOR},
        entry_hash="hash-1",
        prev_log_hash="hash-0",
        log_index=1,
    )
    body = announce_log_entry_activity(
        entry,
        id_="https://example.org/activities/announce-entry-1",
        actor="https://example.org/actors/case-actor",
        to=[ACTOR],
    ).model_dump(mode="json", by_alias=True, exclude_none=True)
    received = copy.deepcopy(body)
    adapter = FastAPIIngressAdapter(dl=dl, body=body)
    artifact = adapter.parse(body)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed is not artifact, "precondition: hydrate built a new object"
    getattr(routed, "object_").payload_snapshot["actor"] = "tampered"

    assert routed.received_evidence == received
