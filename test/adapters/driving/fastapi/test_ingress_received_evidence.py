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
the parser sealed: a by-ID re-read from a staging store, or an in-place hydration
for ``Announce(CaseLedgerEntry)``.  Neither is the received artifact, so the
evidence must be carried onto it, and it must still be the body as it arrived —
bare references included — rather than the hydrated form (ISSUE-3584).
"""

import copy
import json
import logging
from typing import Any

import pytest
from py_trees.common import Status

from test.support.received import archive_received
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.adapters.driving.fastapi.inbox_queue_drain import (
    StoredActivityIngressAdapter,
)
from vultron.adapters.inbox_staging import (
    InlineObjectStaging,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.models.deferred_inbox_activity import DeferredInboxActivity
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.errors import VultronWiringError
from vultron.wire.as2.factories import announce_log_entry_activity
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
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
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(body)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)
    assert isinstance(routed, as_TransitiveActivity)

    assert routed is not artifact
    report = routed.object_
    assert isinstance(report, VulnerabilityReport), "precondition: hydrated"
    evidence = routed.received_evidence
    assert evidence == received
    assert evidence is not None and evidence["object"] == REPORT_ID

    report.content = "edited after hydration"

    assert routed.received_evidence == received
    assert artifact.received_evidence == received


@pytest.mark.spec("VM-08-002")
def test_the_dispatched_event_carries_the_evidence_as_received(
    dl: SqliteDataLayer,
):
    """Core sees only the event, so the parse edge carries the evidence onto it.

    It is the artifact's text, not a rendering of the routing copy: the bare
    report id the routing copy hydrated is still bare (ADR-0107).
    """
    body = _offer_of_stored_report(dl)
    received = copy.deepcopy(body)
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(body)
    assert artifact is not None
    routed = adapter.rehydrate(artifact)

    event = prepare_for_dispatch(routed)

    assert event.received_evidence == artifact.received_evidence_json
    assert event.received_body() == received
    assert event.received_body() is not event.received_body()


def _defer(dl: SqliteDataLayer, body: dict[str, Any]) -> None:
    """Deliver *body* and hold it, as the inbox does for an unknown case."""
    staging = InlineObjectStaging(dl)
    adapter = FastAPIIngressAdapter(dl=dl, staging=staging)
    artifact = adapter.parse(body)
    assert artifact is not None
    adapter.rehydrate(artifact)
    assert staging.hold_for_replay(artifact.id_)


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("IE-10-001")
def test_resend_under_a_held_id_routes_without_this_body_evidence(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """A second body under a deferred id routes the held copy, unsealed.

    The held copy is the *first* delivery, so sealing the second body's text
    onto it would describe an activity other than the one routed.
    """
    first = _offer_of_stored_report(dl)
    first["summary"] = "first"
    _defer(dl, first)
    second = {**copy.deepcopy(first), "summary": "second"}
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(second)
    assert artifact is not None

    with caplog.at_level(logging.INFO):
        routed = adapter.rehydrate(artifact)

    assert routed.summary == "first", "precondition: held copy routed"
    assert routed.received_evidence is None
    assert prepare_for_dispatch(routed).received_evidence is None
    assert artifact.received_evidence == second
    held = dl.read(DeferredInboxActivity.build_id(first["id"]))
    assert isinstance(held, DeferredInboxActivity), "kept for its replay"
    assert held.received_body is not None
    assert json.loads(held.received_body) == first, "not held again"
    assert any(
        r.levelno == logging.INFO
        and first["id"] in r.getMessage()
        and ACTOR in r.getMessage()
        for r in caplog.records
    )


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("IE-10-001")
def test_resend_of_an_archived_activity_routes_the_archived_copy(
    dl: SqliteDataLayer,
):
    """Detected from intake's archive, a resend is routed as the archived
    body's parse, carrying the archived body as its evidence; the resend's
    own bytes are never routed, nothing is written, and the resend's own
    body is left untouched at ingress (ADR-0149, #3762)."""
    first = _offer_of_stored_report(dl)
    first["summary"] = "first"
    record = archive_received(dl, parse_activity(copy.deepcopy(first)))
    before = dl.count_all()
    second = {**copy.deepcopy(first), "summary": "second"}
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(second)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed.id_ == first["id"]
    archived = json.loads(record.received_body)
    assert routed.summary == "first", "the archived copy is routed"
    assert routed.received_evidence == archived
    assert prepare_for_dispatch(routed).received_body() == archived
    assert artifact.received_evidence == second
    assert dl.count_all() == before


@pytest.mark.spec("VM-08-002")
def test_replay_of_a_deferred_activity_carries_its_own_evidence(
    dl: SqliteDataLayer,
):
    """The replay parses the body held for it, so it carries that body."""
    body = _offer_of_stored_report(dl)
    _defer(dl, body)

    replayed = StoredActivityIngressAdapter(dl=dl).parse(body["id"])

    assert replayed is not None, "precondition: held activity replayed"
    assert replayed.received_evidence == body
    assert prepare_for_dispatch(replayed).received_body() == body


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("CLP-10-017")
def test_a_replayed_deferral_is_archived_as_its_first_delivery(
    dl: SqliteDataLayer,
):
    """Deferred, then replayed through the inbox and dispatched: intake
    archives the body the first delivery sealed, so a deferred replay records
    the same evidence as a first delivery would (ADR-0149)."""
    body = _offer_of_stored_report(dl)
    body["x-firstDelivery"] = True
    _defer(dl, body)
    replayed = StoredActivityIngressAdapter(dl=dl).parse(body["id"])
    assert replayed is not None
    event = prepare_for_dispatch(replayed)

    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=IntakeReceivedActivityNode(),
        actor_id="https://test.example/api/v2/actors/test-actor",
        activity=event,
    )

    assert result.status == Status.SUCCESS

    record = dl.read(ReceivedActivityRecord.build_id(body["id"]))
    assert isinstance(record, ReceivedActivityRecord)
    assert json.loads(record.received_body) == body


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
        semantic_type="accept_invite_actor_to_case",
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
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(body)
    assert artifact is not None

    routed = adapter.rehydrate(artifact)
    assert isinstance(routed, as_TransitiveActivity)

    assert routed is not artifact, "precondition: hydrate built a new object"
    routed_entry = routed.object_
    assert isinstance(routed_entry, CaseLedgerEntry), "precondition: hydrated"
    routed_entry.payload_snapshot["actor"] = "tampered"

    assert routed.received_evidence == received


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("IE-10-001")
def test_a_resend_whose_held_copy_does_not_rebuild_carries_no_evidence(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
):
    """Should the held copy fail to rebuild, the resend's own body is routed
    in its place, still without evidence: it is not the delivery held.  A
    deferral of it holds no evidence either, so its replay carries none."""
    first = _offer_of_stored_report(dl)
    archive_received(dl, parse_activity(copy.deepcopy(first)))
    monkeypatch.setattr(
        InlineObjectStaging, "rehydrate_archived", lambda *_args: None
    )
    staging = InlineObjectStaging(dl)
    adapter = FastAPIIngressAdapter(dl=dl, staging=staging)
    artifact = adapter.parse(copy.deepcopy(first))
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed.id_ == first["id"]
    assert routed.received_evidence is None
    assert staging.hold_for_replay(first["id"])
    held = dl.read(DeferredInboxActivity.build_id(first["id"]))
    assert isinstance(held, DeferredInboxActivity)
    assert held.received_body is None


@pytest.mark.spec("VM-08-002")
def test_a_resend_that_cannot_be_rebuilt_at_all_is_refused(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch
):
    """With neither copy rebuilt there is nothing to route without this
    body's evidence, so ingress raises rather than route it sealed."""
    first = _offer_of_stored_report(dl)
    archive_received(dl, parse_activity(copy.deepcopy(first)))
    monkeypatch.setattr(
        InlineObjectStaging, "rehydrate_archived", lambda *_args: None
    )
    monkeypatch.setattr(
        InlineObjectStaging, "rehydrate_resend", lambda *_args: None
    )
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(copy.deepcopy(first))
    assert artifact is not None

    with pytest.raises(VultronWiringError, match="neither the held copy"):
        adapter.rehydrate(artifact)


@pytest.mark.spec("VM-08-002")
def test_an_archived_resend_deferred_again_is_held_with_the_archived_body(
    dl: SqliteDataLayer,
):
    """A resend routed as the archived copy and then deferred is held with
    the archived body, so its replay carries the first delivery's evidence,
    never the resend's."""
    first = _offer_of_stored_report(dl)
    record = archive_received(dl, parse_activity(copy.deepcopy(first)))
    staging = InlineObjectStaging(dl)
    adapter = FastAPIIngressAdapter(dl=dl, staging=staging)
    artifact = adapter.parse({**copy.deepcopy(first), "summary": "resend"})
    assert artifact is not None
    adapter.rehydrate(artifact)

    assert staging.hold_for_replay(first["id"])

    held = dl.read(DeferredInboxActivity.build_id(first["id"]))
    assert isinstance(held, DeferredInboxActivity)
    archived = json.loads(record.received_body)
    assert held.received_body is not None
    assert json.loads(held.received_body) == archived
    replayed = StoredActivityIngressAdapter(dl=dl).parse(first["id"])
    assert replayed is not None
    assert replayed.received_evidence == archived
