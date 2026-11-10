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
"""Ingress rehydration carries the received evidence, untouched (VM-08-007).

``FastAPIIngressAdapter.rehydrate`` returns a *different* object from the one
the parser sealed: a by-ID re-read from a staging store, or an in-place hydration
for ``Announce(CaseLedgerEntry)``.  Neither is the received artifact, so the
evidence must be carried onto it, and it must still be the body as it arrived —
bare references included — rather than the hydrated form (ISSUE-3584).
"""

import copy
import json
import logging
from typing import Any, cast

import pytest
from py_trees.common import Status

from test.support.received import archive_received, intake_received
from test.support.signing import resigned, signed_body
from vultron.adapters.driven.clock import SystemClock
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
    FastAPIQueuePort,
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
from vultron.core.behaviors.inbox import InboxOutcomeStatus, process_payload
from vultron.core.models._helpers import now_utc
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.services.received_activity import sealed_body_of
from vultron.core.services.received_outcome import write_receipt_stub
from vultron.errors import VultronReusedActivityIdError, VultronWiringError
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
CASE_ACTOR = "https://example.org/actors/case-actor"
RECEIVER = "https://test.example/api/v2/actors/test-actor"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer(
        db_url="sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


def _offer_of_stored_report(
    dl: SqliteDataLayer, **extra: Any
) -> dict[str, Any]:
    """An ``Offer`` naming a report the receiver already holds by bare ID.

    Signed by its actor, as the sender delivers it (SIG-01-001); *extra*
    adds top-level keys before it is signed.
    """
    dl.save(
        VulnerabilityReport(
            id_=REPORT_ID, name="r", content="stored", attributed_to=ACTOR
        )
    )
    return signed_body(
        {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Offer",
            "id": "https://example.org/activities/offer-1",
            "actor": ACTOR,
            "published": "2026-01-02T03:04:05+00:00",
            "object": REPORT_ID,
            "to": ["https://example.org/actors/vendor"],
            **extra,
        }
    )


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("VM-08-006")
@pytest.mark.spec("VM-08-007")
@pytest.mark.spec("SE-01-002")
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
    assert staging.hold_for_replay(artifact.id_, received_at=now_utc())


def _announce_entry_body() -> dict[str, Any]:
    """An ``Announce(CaseLedgerEntry)``, signed, as a CASE_MANAGER sends it."""
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
    return signed_body(
        announce_log_entry_activity(
            entry,
            id_="https://example.org/activities/announce-entry-1",
            actor=CASE_ACTOR,
            to=[ACTOR],
        ).model_dump(mode="json", by_alias=True, exclude_none=True)
    )


def _store_state(dl: SqliteDataLayer) -> dict[str, Any]:
    """Every record in *dl*, as JSON, plus its inbox queue."""
    records = cast(dict[str, Any], dl.all())
    return {
        "records": {
            key: obj.model_dump(mode="json", by_alias=True)
            for key, obj in records.items()
        },
        "inbox": list(dl.inbox_list()),
    }


class _RecordingDispatch:
    """A dispatch adapter that records what reaches it."""

    def __init__(self) -> None:
        self.dispatched: list[Any] = []

    def dispatch(self, event: Any) -> HandlerResult:
        self.dispatched.append(event)
        return HandlerResult.applied()

    def emit_processing_fault(self, event: Any, failure_class: str) -> None:
        raise AssertionError("a refused delivery is never dispatched")


def _refusal_warnings(
    caplog: pytest.LogCaptureFixture, activity_id: str, sender: str
) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and activity_id in r.getMessage()
        and sender in r.getMessage()
    ]


def _assert_refused_through_the_inbox(
    dl: SqliteDataLayer,
    second: dict[str, Any],
    sender: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Run *second* through ``process_payload`` and assert IE-10-002's refusal.

    Nothing is dispatched or deferred, the store (held record and archive
    included) is unchanged, and one WARNING names the activity id and sender.
    """
    before = _store_state(dl)
    staging = InlineObjectStaging(dl)
    dispatch_adp = _RecordingDispatch()
    queue = FastAPIQueuePort(dl=dl, actor_dl=dl, staging=staging)

    with caplog.at_level(logging.INFO):
        outcome = process_payload(
            copy.deepcopy(second),
            FastAPIIngressAdapter(dl=dl, staging=staging),
            dispatch_adp,
            queue,
            arrived_at=SystemClock().now(),
        )

    assert outcome.status is InboxOutcomeStatus.REJECTED
    assert outcome.failure_reason is not None
    assert "reused" in outcome.failure_reason
    assert second["id"] in outcome.failure_reason
    assert dispatch_adp.dispatched == []
    assert _store_state(dl) == before
    assert len(_refusal_warnings(caplog, second["id"], sender)) == 1


@pytest.mark.spec("VM-08-010")
@pytest.mark.spec("IE-10-001")
def test_resend_of_the_held_body_under_a_deferred_id_routes_the_held_copy(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """The same body under a deferred id routes the held copy, unsealed.

    The held copy is the *first* delivery, so sealing the resend's text onto
    it would describe a delivery other than the one routed; the record is
    kept for its replay and not held again.
    """
    first = _offer_of_stored_report(dl, summary="first")
    _defer(dl, first)
    before = _store_state(dl)
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(copy.deepcopy(first))
    assert artifact is not None

    with caplog.at_level(logging.INFO):
        routed = adapter.rehydrate(artifact)

    assert routed is not artifact
    assert routed.summary == "first"
    assert routed.received_evidence is None
    assert prepare_for_dispatch(routed).received_evidence is None
    assert artifact.received_evidence == first
    assert _store_state(dl) == before, "not held again"
    assert any(
        r.levelno == logging.INFO
        and first["id"] in r.getMessage()
        and ACTOR in r.getMessage()
        and "already held" in r.getMessage()
        for r in caplog.records
    )
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("IE-10-003", "IE-10-004", "IE-10-005")
def test_a_different_body_under_a_deferred_id_is_refused(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """A second body under a deferred id is refused, not routed as the held
    copy, and the deferred record is left exactly as it was (#3762)."""
    first = _offer_of_stored_report(dl, summary="first")
    _defer(dl, first)
    held_before = dl.read(ReceivedActivityRecord.build_id(first["id"]))
    assert isinstance(held_before, ReceivedActivityRecord)
    assert held_before.stage is ReceivedStage.HELD
    assert held_before.replay_owed
    second = resigned(first, summary="second")

    _assert_refused_through_the_inbox(dl, second, ACTOR, caplog)

    held = dl.read(ReceivedActivityRecord.build_id(first["id"]))
    assert isinstance(held, ReceivedActivityRecord)
    assert held == held_before
    assert json.loads(sealed_body_of(held)) == first


@pytest.mark.spec("IE-10-002")
def test_the_refusal_raises_a_reused_id_error_naming_the_sender(
    dl: SqliteDataLayer,
):
    """``rehydrate`` raises the domain error, carrying the id and sender."""
    _, first = _archive_sealed(dl, _offer_of_stored_report(dl))
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(resigned(first, summary="second"))
    assert artifact is not None

    with pytest.raises(VultronReusedActivityIdError) as raised:
        adapter.rehydrate(artifact)

    assert raised.value.activity_id == first["id"]
    assert raised.value.actor_id == ACTOR


@pytest.mark.spec("IE-10-002")
def test_a_body_that_differs_only_in_key_order_is_refused(
    dl: SqliteDataLayer,
):
    """The match is exact, with no normalisation (IE-10-002 ``note:``)."""
    first = _offer_of_stored_report(dl)
    record = archive_received(dl, parse_activity(copy.deepcopy(first)))
    reordered = dict(
        reversed(list(json.loads(sealed_body_of(record)).items()))
    )
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(reordered)
    assert artifact is not None
    assert artifact.received_evidence == json.loads(sealed_body_of(record))

    with pytest.raises(VultronReusedActivityIdError):
        adapter.rehydrate(artifact)


@pytest.mark.spec("VM-08-009")
@pytest.mark.spec("IE-10-001")
def test_resend_of_an_archived_body_routes_the_archived_copy(
    dl: SqliteDataLayer,
):
    """Detected from intake's archive, a resend of the same body is routed
    as the archived body's parse, carrying the archived body as its
    evidence, and nothing is written (ADR-0149)."""
    first = _offer_of_stored_report(dl, summary="first")
    record = archive_received(dl, parse_activity(copy.deepcopy(first)))
    before = _store_state(dl)
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(json.loads(sealed_body_of(record)))
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert routed is not artifact
    assert routed.id_ == first["id"]
    archived = json.loads(sealed_body_of(record))
    assert routed.summary == "first"
    assert routed.received_evidence == archived
    assert prepare_for_dispatch(routed).received_body() == archived
    assert _store_state(dl) == before


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("IE-10-003", "IE-10-004", "IE-10-005")
def test_a_different_body_under_an_archived_id_is_refused(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """A second body under an archived id is refused; the archive is left
    exactly as it was and neither body is routed (#3762)."""
    record, first = _archive_sealed(dl, _offer_of_stored_report(dl))
    second = resigned(first, summary="second")

    _assert_refused_through_the_inbox(dl, second, ACTOR, caplog)

    assert dl.read(ReceivedActivityRecord.build_id(first["id"])) == record


def _archive_sealed(
    dl: SqliteDataLayer, body: dict[str, Any]
) -> tuple[ReceivedActivityRecord, dict[str, Any]]:
    """Archive *body*; return the record and the body exactly as archived.

    A test changes the archived body itself (``resigned``), so a refusal of
    the resend is for that change alone, never for a difference in how the
    test spelled its first body.
    """
    record = archive_received(dl, parse_activity(copy.deepcopy(body)))
    return record, json.loads(sealed_body_of(record))


def _refuse_and_stub(
    dl: SqliteDataLayer, body: dict[str, Any]
) -> tuple[ReceivedActivityRecord, dict[str, Any]]:
    """Archive *body*, then reduce it to the receipt stub a refusal leaves.

    Returns the stub and the body exactly as it was sealed, which is what a
    same-body resend delivers.
    """
    record = intake_received(dl, parse_activity(copy.deepcopy(body)))
    sealed = json.loads(sealed_body_of(record))
    stub = write_receipt_stub(
        dl,
        body["id"],
        sender_id=ACTOR,
        reason="refused for this test",
        received_at=now_utc(),
    )
    return stub, sealed


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("CLP-10-018")
def test_a_different_body_under_a_refused_id_is_refused(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """The stub keeps the digest of the body it gave up, so a reused id is
    still refused after a refusal; the stub is left exactly as it was."""
    stub, first = _refuse_and_stub(dl, _offer_of_stored_report(dl))
    second = resigned(first, summary="second")

    _assert_refused_through_the_inbox(dl, second, ACTOR, caplog)

    assert dl.read(ReceivedActivityRecord.build_id(first["id"])) == stub


@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("CLP-10-018")
def test_the_same_body_under_a_refused_id_is_routed_on_its_own(
    dl: SqliteDataLayer,
):
    """A stub holds no copy to route, so the same body goes on, on its own.

    The seen-before door of the tree it reaches answers it from the stub
    (ADR-0154, ``test/adapters/driving/fastapi/test_seen_before_door.py``).
    """
    first = _offer_of_stored_report(dl)
    _, sealed = _refuse_and_stub(dl, first)
    staging = InlineObjectStaging(dl)
    dispatch_adp = _RecordingDispatch()

    outcome = process_payload(
        sealed,
        FastAPIIngressAdapter(dl=dl, staging=staging),
        dispatch_adp,
        FastAPIQueuePort(dl=dl, actor_dl=dl, staging=staging),
        arrived_at=SystemClock().now(),
    )

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert [event.activity_id for event in dispatch_adp.dispatched] == [
        first["id"]
    ]


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("SYNC-12-003")
def test_a_repeat_of_an_archived_ledger_announce_is_hydrated_in_place(
    dl: SqliteDataLayer,
):
    """The same ``Announce(CaseLedgerEntry)`` body still takes the in-place
    path, so the SYNC-12-003 already-stored gate answers it (SYNC-13-004)."""
    body = _announce_entry_body()
    archive_received(dl, parse_activity(copy.deepcopy(body)))
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(copy.deepcopy(body))
    assert artifact is not None

    routed = adapter.rehydrate(artifact)

    assert isinstance(routed, as_TransitiveActivity)
    assert isinstance(routed.object_, CaseLedgerEntry), "hydrated in place"
    assert routed.received_evidence == body


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("IE-10-003", "IE-10-004", "IE-10-005")
def test_a_different_body_under_an_archived_ledger_announce_id_is_refused(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """The in-place path gets the same comparison: a rewritten entry under
    a held ``Announce`` id is refused, not hydrated (IE-10-002)."""
    _, body = _archive_sealed(dl, _announce_entry_body())

    def rewrite(entry: dict[str, Any]) -> None:
        entry["object"]["payload_snapshot"] = {"actor": "rewritten"}

    second = resigned(body, alter=rewrite)

    _assert_refused_through_the_inbox(dl, second, CASE_ACTOR, caplog)


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("IE-10-003", "IE-10-004", "IE-10-005")
def test_a_different_body_under_a_held_ledger_announce_id_is_refused(
    dl: SqliteDataLayer, caplog: pytest.LogCaptureFixture
):
    """A held ``Announce(CaseLedgerEntry)`` is compared with the body held
    for its replay (SYNC-14-001, IO-03-004)."""
    body = _announce_entry_body()
    _defer(dl, body)

    def rewrite(entry: dict[str, Any]) -> None:
        entry["object"]["payload_snapshot"] = {"actor": "rewritten"}

    second = resigned(body, alter=rewrite)

    _assert_refused_through_the_inbox(dl, second, CASE_ACTOR, caplog)


@pytest.mark.spec("IE-10-002")
@pytest.mark.spec("ARCH-15-001")
def test_an_unsealed_activity_under_a_held_id_is_a_wiring_fault(
    dl: SqliteDataLayer,
):
    """Every delivery the inbox parses is sealed, so an activity under a held
    id with no sealed body was handed in in process (AC-7)."""
    body = _offer_of_stored_report(dl)
    archive_received(dl, parse_activity(copy.deepcopy(body)))
    unsealed = parse_activity(copy.deepcopy(body))
    unsealed._received_evidence = None

    with pytest.raises(VultronWiringError, match="carries no sealed body"):
        FastAPIIngressAdapter(dl=dl).rehydrate(unsealed)


@pytest.mark.spec("VM-08-008")
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
    body = _offer_of_stored_report(dl, **{"x-firstDelivery": True})
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
    assert json.loads(sealed_body_of(record)) == body


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("VM-08-007")
@pytest.mark.spec("SE-01-002")
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
    body = _announce_entry_body()
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


@pytest.mark.spec("IE-10-001")
@pytest.mark.spec("ARCH-15-001")
@pytest.mark.parametrize("kind", ["awaiting_replay", "archived"])
def test_a_resend_whose_held_copy_does_not_rebuild_is_a_wiring_fault(
    dl: SqliteDataLayer, monkeypatch: pytest.MonkeyPatch, kind: str
):
    """The held copy is the resend's own text, so if it does not rebuild,
    neither would this body: ingress raises rather than route either."""
    first = _offer_of_stored_report(dl)
    if kind == "awaiting_replay":
        _defer(dl, first)
        held = dl.read(ReceivedActivityRecord.build_id(first["id"]))
        assert isinstance(held, ReceivedActivityRecord)
        assert held.replay_owed
        resend = sealed_body_of(held)
        monkeypatch.setattr(
            InlineObjectStaging, "rehydrate_held", lambda *_args: None
        )
    else:
        resend = sealed_body_of(
            archive_received(dl, parse_activity(copy.deepcopy(first)))
        )
        monkeypatch.setattr(
            InlineObjectStaging, "rehydrate_archived", lambda *_args: None
        )
    adapter = FastAPIIngressAdapter(dl=dl)
    artifact = adapter.parse(json.loads(resend))
    assert artifact is not None

    with pytest.raises(VultronWiringError, match="does not rebuild"):
        adapter.rehydrate(artifact)


@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("CLP-10-074")
def test_a_resend_deferred_again_is_held_with_the_body_left_in_holding(
    dl: SqliteDataLayer,
):
    """A resend of a message a run left in holding with no verdict, routed
    as that copy and then deferred, is held with the first body, so its
    replay carries the first delivery's evidence (CLP-10-074)."""
    first = _offer_of_stored_report(dl)
    record = intake_received(dl, parse_activity(copy.deepcopy(first)))
    staging = InlineObjectStaging(dl)
    adapter = FastAPIIngressAdapter(dl=dl, staging=staging)
    artifact = adapter.parse(json.loads(sealed_body_of(record)))
    assert artifact is not None
    adapter.rehydrate(artifact)

    assert staging.hold_for_replay(first["id"], received_at=now_utc())

    held = dl.read(ReceivedActivityRecord.build_id(first["id"]))
    assert isinstance(held, ReceivedActivityRecord)
    assert held.stage is ReceivedStage.HELD, "still not at its outcome"
    assert held.replay_owed
    first_body = json.loads(sealed_body_of(record))
    assert json.loads(sealed_body_of(held)) == first_body
    replayed = StoredActivityIngressAdapter(dl=dl).parse(first["id"])
    assert replayed is not None
    assert replayed.received_evidence == first_body


@pytest.mark.spec("CLP-10-073")
def test_an_archived_resend_deferred_again_is_not_held(dl: SqliteDataLayer):
    """An applied message is not held for a replay that would apply it
    again: the archive stands, and the resend's seen-before door skips it."""
    first = _offer_of_stored_report(dl)
    record = archive_received(dl, parse_activity(copy.deepcopy(first)))
    staging = InlineObjectStaging(dl)
    adapter = FastAPIIngressAdapter(dl=dl, staging=staging)
    artifact = adapter.parse(json.loads(sealed_body_of(record)))
    assert artifact is not None
    adapter.rehydrate(artifact)

    assert staging.hold_for_replay(first["id"], received_at=now_utc()) is False

    assert dl.read(ReceivedActivityRecord.build_id(first["id"])) == record
