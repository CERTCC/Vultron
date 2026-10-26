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
"""SYNC integration tests for single-peer as_CaseLedgerEntry replication (#901)."""

from __future__ import annotations

import functools
from collections.abc import Iterator
from typing import cast

import anyio
import pytest

from test.demo.conftest import _TestClientRouter, create_isolated_actor_app
from test.support.received import delivered, received_event
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driving.fastapi.inbox_handler import (
    handle_inbox_item,
)
from vultron.adapters.driving.fastapi.outbox_handler import (
    configure_default_emitter,
    get_default_emitter,
    outbox_handler,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger import (
    HashChainLedgerRecord,
)
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.core.use_cases.triggers.sync import (
    state_ledger_positions_trigger,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ACTOR_BASE = "http://case-actor-sync-901.test"
_PEER_BASE = "http://peer-sync-901.test"
# The case owner the genesis hash is anchored to (CLP-08-002); an owned case
# has a ledger, and so a ledger position (SYNC-16-005).
_OWNER_ID = "http://vendor-sync-901.test/actors/vendor"


def _actor_slug(actor_id: str) -> str:
    return actor_id.rstrip("/").rsplit("/", 1)[-1]


def _create_actor(client, base_api: str, slug: str, actor_type: str) -> str:
    actor_id = f"{base_api}/actors/{slug}"
    response = client.post(
        "/api/v2/actors/",
        json={"type": actor_type, "name": slug, "id": actor_id},
    )
    assert response.status_code in (
        200,
        201,
    ), f"Actor creation failed ({response.status_code}): {response.text}"
    return actor_id


def _register_peer(
    client,
    host_slug: str,
    peer_id: str,
    name: str,
    actor_type: str = "Organization",
) -> None:
    """Register a peer in the hosted actor's address book (ADR-0081)."""
    resp = client.post(
        f"/api/v2/actors/{host_slug}/peers/",
        json={"id": peer_id, "name": name, "actor_type": actor_type},
    )
    assert resp.status_code in (
        200,
        201,
    ), f"Peer registration failed ({resp.status_code}): {resp.text}"


def _make_log_entry(
    case_id: str,
    log_index: int,
    prev_hash: str,
    semantic_type: str,
) -> CaseLedgerEntry:
    record = HashChainLedgerRecord(
        case_id=case_id,
        log_index=log_index,
        object_id=case_id,
        semantic_type=semantic_type,
        payload_snapshot={"semantic_type": semantic_type},
        prev_log_hash=prev_hash,
    )
    return _to_persistable_entry(record)


@pytest.fixture
def two_app_setup() -> Iterator[tuple]:
    """Create two isolated actor apps connected by ``_TestClientRouter``."""
    router = _TestClientRouter()
    case_actor_iso = create_isolated_actor_app(
        base_url=_CASE_ACTOR_BASE, router=router
    )
    peer_iso = create_isolated_actor_app(base_url=_PEER_BASE, router=router)

    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with case_actor_iso.client as case_actor_tc:
        with peer_iso.client as peer_tc:
            yield case_actor_iso, peer_iso, case_actor_tc, peer_tc

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    case_actor_iso.dl.close()
    peer_iso.dl.close()


@pytest.mark.spec("SYNC-07-002")
@pytest.mark.spec("SYNC-02-003")
def test_sync_single_peer_happy_path_replication(two_app_setup) -> None:
    """The CaseActor commit should replicate one as_CaseLedgerEntry to a peer replica."""
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_base_api = f"{case_actor_iso.base_url}/api/v2"
    peer_base_api = f"{peer_iso.base_url}/api/v2"

    case_actor_id = _create_actor(
        case_actor_tc, case_actor_base_api, "case-actor-sync-901", "Service"
    )
    peer_actor_id = _create_actor(
        peer_tc, peer_base_api, "peer-sync-901", "Organization"
    )
    # Register peer as address-book entry on case-actor's app for outbox routing (ADR-0081).
    _register_peer(
        case_actor_tc, "case-actor-sync-901", peer_actor_id, "peer-sync-901"
    )

    case = as_VulnerabilityCase(
        name="SYNC-901 integration case", attributed_to=_OWNER_ID
    )
    case_actor_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        # Authority is the role, so the actor managing this case must hold it:
        # `FindCaseActorNode` and the commit gate both read the roster, not an
        # the case actor `Service`'s hosting `context` (ADR-0088, ARCH-24-004).
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer_participant = as_CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_

    # Each actor's *own* store, not the app's default-slug `dl`: the actors above
    # are created under per-test slugs, and a BT runs against the store of the
    # actor executing it (BT-05-005).  Saving into `dl` left the case actor's own
    # store without the case, so the commit could not derive the per-case genesis
    # hash and was refused (CLP-08-005) — surfacing as "Log entry commit did not
    # persist".
    case_actor_dl = case_actor_iso.store_for(case_actor_id)
    case_actor_dl.save(case_actor_participant)
    case_actor_dl.save(peer_participant)
    case_actor_dl.save(case)

    # The peer must already hold the case replica (with its genesis hash) before
    # it can validate a replicated CaseLedgerEntry: ReconstructChainTail anchors
    # the first entry on the per-case genesis hash (CLP-08-005).  Previously this
    # precondition was masked because the ingress adapter pre-stored the inline
    # entry directly; that write is now forbidden (SYNC-13-002), so seed the peer
    # with the case as a participant realistically would have it.
    peer_dl = peer_iso.store_for(peer_actor_id)
    peer_dl.save(case_actor_participant)
    peer_dl.save(peer_participant)
    peer_dl.save(case)

    response = case_actor_tc.post(
        f"/api/v2/actors/{_actor_slug(case_actor_id)}/demo/sync-log-entry",
        json={
            "case_id": case.id_,
            "object_id": case.id_,
        },
    )
    assert response.status_code == 202, response.text
    payload = response.json()

    entry_id = payload["log_entry_id"]
    # `peer_dl` above, not the app's default-slug `dl`: the Announce was delivered
    # to `peer_actor_id`, so that is the replica that received the entry.
    peer_entry = peer_dl.read(entry_id)
    assert peer_entry is not None, (
        "Expected peer replica to contain the announced as_CaseLedgerEntry."
    )
    assert peer_entry.case_id == case.id_
    assert peer_entry.log_index == payload["log_index"]
    assert peer_entry.entry_hash == payload["entry_hash"]
    assert peer_entry.log_object_id == case.id_
    assert peer_entry.semantic_type == "announce_vulnerability_case"

    # AC-4 guard: each actor app uses its own isolated DataLayer.
    assert case_actor_iso.dl is not peer_iso.dl


@pytest.mark.spec("SYNC-03-001")
@pytest.mark.spec("SYNC-03-002")
@pytest.mark.spec("SYNC-04-001")
@pytest.mark.spec("SYNC-04-002")
def test_sync_predecessor_mismatch_reject_and_replay(two_app_setup) -> None:
    """Reject mismatch entry, then replay from last accepted hash."""
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_base_api = f"{case_actor_iso.base_url}/api/v2"
    peer_base_api = f"{peer_iso.base_url}/api/v2"

    case_actor_id = _create_actor(
        case_actor_tc, case_actor_base_api, "case-actor-sync-902", "Service"
    )
    peer_actor_id = _create_actor(
        peer_tc, peer_base_api, "peer-sync-902", "Organization"
    )

    # Each actor's own store, not the app's default-slug `dl`: the actors are
    # created under per-test slugs and a BT runs against the store of the actor
    # executing it (BT-05-005), so `dl` is a different database (BT-05-005,
    # CLP-08-005).
    case_actor_dl = case_actor_iso.store_for(case_actor_id)
    peer_dl = peer_iso.store_for(peer_actor_id)
    # Cross-register actors as peers so each app can route to the other (ADR-0081).
    _register_peer(
        case_actor_tc, "case-actor-sync-902", peer_actor_id, "peer-sync-902"
    )
    _register_peer(
        peer_tc,
        "peer-sync-902",
        case_actor_id,
        "case-actor-sync-902",
        "Service",
    )

    case = as_VulnerabilityCase(
        name="SYNC-902 mismatch/replay integration case",
        attributed_to=_OWNER_ID,
    )
    case_actor_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        # Authority is the role, so the actor managing this case must hold it:
        # `FindCaseActorNode` and the commit gate both read the roster, not an
        # the case actor `Service`'s hosting `context` (ADR-0088, ARCH-24-004).
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer_participant = as_CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_
    case_actor_dl.save(case_actor_participant)
    case_actor_dl.save(peer_participant)
    case_actor_dl.save(case)
    case_actor_dl.save(VultronService(id_=case_actor_id, context=case.id_))

    entry0 = _make_log_entry(case.id_, 0, case.genesis_hash, "sync_902_base")
    entry1 = _make_log_entry(case.id_, 1, entry0.entry_hash, "sync_902_mid")
    entry2 = _make_log_entry(case.id_, 2, entry1.entry_hash, "sync_902_tail")
    case_actor_dl.save(entry0)
    case_actor_dl.save(entry1)
    case_actor_dl.save(entry2)
    # The peer's replica: the case at the one entry it holds (SYNC-16-005).
    peer_dl.save(
        case.model_copy(
            update={
                "ledger_position": LedgerPosition(
                    log_index=0, entry_hash=entry0.entry_hash
                )
            }
        )
    )
    peer_dl.save(entry0)

    wire_entry2 = WireCaseLedgerEntry.model_validate(
        entry2.model_dump(mode="json")
    )
    out_of_chain_announce = announce_log_entry_activity(
        entry=wire_entry2,
        actor=case_actor_id,
        to=[peer_actor_id],
    )
    try:
        handle_inbox_item(
            actor_id=peer_actor_id,
            obj=delivered(out_of_chain_announce),
            dl=peer_dl,
            dispatcher=peer_iso.app.state.dispatcher,
        )
        peer_reject_events = [
            cast(RejectLogEntryReceivedEvent, extract_event(activity))
            for activity in peer_dl.list_objects("Reject")
        ]
        assert peer_reject_events, (
            "Expected peer to emit Reject(as_CaseLedgerEntry)."
        )
        emitted_reject_event = peer_reject_events[-1]
        assert emitted_reject_event.actor_id == peer_actor_id
        assert emitted_reject_event.last_accepted_hash == entry0.entry_hash
        assert peer_dl.read(entry2.id_) is None

        reject_for_case_actor = cast(
            RejectLogEntryReceivedEvent,
            received_event(
                reject_log_entry_activity(
                    entry=wire_entry2,
                    context=entry0.entry_hash,
                    actor=peer_actor_id,
                    to=[case_actor_id],
                )
            ),
        )

        RejectLedgerEntryReceivedUseCase(
            case_actor_dl,
            reject_for_case_actor,
            sync_port=SyncActivityAdapter(case_actor_dl),
        ).execute()

        # `outbox_handler(actor_id, dl, emitter=None)` — the shared-DataLayer
        # third positional is gone (ADR-0073), and passing a store where the
        # emitter is expected made `emit()` be called on a SqliteDataLayer.
        # `anyio.run` cannot forward keywords, hence the partial.
        anyio.run(
            functools.partial(
                outbox_handler,
                case_actor_id,
                case_actor_dl,
                emitter=getattr(case_actor_iso.app.state, "emitter", None),
            )
        )
    finally:
        # Deliberately no `close()` here. These are the actors' *live* stores,
        # shared with the running apps — not the throwaway clones this block used
        # to build. Closing disposes the engine, and because an in-memory store is
        # named, that destroys the database every other holder is using: the next
        # read fails with "no such table: vultron_objects".
        pass

    state_id = VultronReplicationState(
        case_id=case.id_, peer_id=peer_actor_id
    ).id_
    replication_state = case_actor_dl.read(state_id)
    assert replication_state is not None
    assert replication_state.last_acknowledged_hash == entry0.entry_hash

    assert peer_dl.read(entry1.id_) is not None
    assert peer_dl.read(entry2.id_) is not None
    assert case_actor_dl is not peer_dl


@pytest.mark.spec("SYNC-03-003")
@pytest.mark.spec("SYNC-07-003")
def test_sync_duplicate_delivery_idempotency(
    two_app_setup, monkeypatch
) -> None:
    """Duplicate delivery of Announce(as_CaseLedgerEntry) must produce one replica.

    Delivers the same ``Announce(as_CaseLedgerEntry)`` twice to the peer actor
    and verifies the peer replica contains exactly one copy of the entry
    (SYNC-03-003: replication MUST be idempotent; repeated delivery MUST NOT
    produce duplicate entries).
    """
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_base_api = f"{case_actor_iso.base_url}/api/v2"
    peer_base_api = f"{peer_iso.base_url}/api/v2"

    case_actor_id = _create_actor(
        case_actor_tc, case_actor_base_api, "case-actor-sync-903", "Service"
    )
    peer_actor_id = _create_actor(
        peer_tc, peer_base_api, "peer-sync-903", "Organization"
    )

    # Each actor's own store, not the app's default-slug `dl`: the actors are
    # created under per-test slugs and a BT runs against the store of the actor
    # executing it (BT-05-005), so `dl` is a different database (BT-05-005,
    # CLP-08-005).
    case_actor_dl = case_actor_iso.store_for(case_actor_id)
    peer_dl = peer_iso.store_for(peer_actor_id)

    case = as_VulnerabilityCase(
        name="SYNC-903 duplicate delivery integration case",
        attributed_to=_OWNER_ID,
    )
    case_actor_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        # Authority is the role, so the actor managing this case must hold it:
        # `FindCaseActorNode` and the commit gate both read the roster, not an
        # the case actor `Service`'s hosting `context` (ADR-0088, ARCH-24-004).
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer_participant = as_CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_

    # Peer needs the case and participants in its DataLayer to process inbound
    # Announce(as_CaseLedgerEntry) as a participant, not as the CaseActor.
    peer_dl.save(case_actor_participant)
    peer_dl.save(peer_participant)
    peer_dl.save(case)

    saved_case_ledger_entry_ids: list[str] = []
    original_save = peer_dl.save

    def save_spy(obj, *args, **kwargs):
        if getattr(obj, "type_", None) == "CaseLedgerEntry":
            saved_case_ledger_entry_ids.append(getattr(obj, "id_", ""))
        return original_save(obj, *args, **kwargs)

    monkeypatch.setattr(peer_dl, "save", save_spy)

    entry = _make_log_entry(case.id_, 0, case.genesis_hash, "sync_903_dup")
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    announce = announce_log_entry_activity(
        entry=wire_entry,
        actor=case_actor_id,
        to=[peer_actor_id],
    )

    # Deliver the same Announce(as_CaseLedgerEntry) twice.
    for _ in range(2):
        handle_inbox_item(
            actor_id=peer_actor_id,
            obj=delivered(announce),
            dl=peer_dl,
            dispatcher=peer_iso.app.state.dispatcher,
        )

    assert saved_case_ledger_entry_ids == [entry.id_]

    # Peer replica must contain exactly one copy (idempotent behavior).
    stored_entries = [
        e
        for e in peer_dl.list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == case.id_
    ]
    assert len(stored_entries) == 1, (
        f"Expected exactly 1 as_CaseLedgerEntry replica, got {len(stored_entries)}"
    )
    assert stored_entries[0].id_ == entry.id_

    # AC-4 guard: each actor app must use its own isolated DataLayer.
    assert case_actor_dl is not peer_dl


@pytest.mark.spec("SYNC-17-004")
@pytest.mark.spec("SYNC-17-003")
@pytest.mark.spec("SYNC-00-008")
def test_lost_last_entry_is_recovered_by_a_position_statement(
    two_app_setup,
) -> None:
    """A dropped last Announce is recovered by the participant's own Read.

    The CASE_MANAGER holds three entries; the peer's replica received only
    the first two, and nothing further is committed, so no later entry
    arrives with a gap and the peer sends no ``Reject``.  Its
    ``Read(CaseLedgerEntry)``, delivered through the CASE_MANAGER's inbox,
    records its position and replays the lost entry, so the peer's tail
    reaches the CASE_MANAGER's (ADR-0155).
    """
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_id = _create_actor(
        case_actor_tc,
        f"{case_actor_iso.base_url}/api/v2",
        "case-actor-sync-917",
        "Service",
    )
    peer_actor_id = _create_actor(
        peer_tc, f"{peer_iso.base_url}/api/v2", "peer-sync-917", "Organization"
    )
    case_actor_dl = case_actor_iso.store_for(case_actor_id)
    peer_dl = peer_iso.store_for(peer_actor_id)
    _register_peer(
        case_actor_tc, "case-actor-sync-917", peer_actor_id, "peer-sync-917"
    )

    case = as_VulnerabilityCase(
        name="SYNC-17 lost last entry case", attributed_to=_OWNER_ID
    )
    case_actor_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer_participant = as_CaseParticipant(
        attributed_to=peer_actor_id, context=case.id_
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_
    for store in (case_actor_dl, peer_dl):
        store.save(case_actor_participant)
        store.save(peer_participant)
    case_actor_dl.save(case)

    entry0 = _make_log_entry(case.id_, 0, case.genesis_hash, "sync_917_a")
    entry1 = _make_log_entry(case.id_, 1, entry0.entry_hash, "sync_917_b")
    entry2 = _make_log_entry(case.id_, 2, entry1.entry_hash, "sync_917_c")
    for entry in (entry0, entry1, entry2):
        case_actor_dl.save(entry)
    # The peer's replica: the Announce of entry2 was lost (SYNC-16-005).
    peer_dl.save(
        case.model_copy(
            update={
                "ledger_position": LedgerPosition(
                    log_index=1, entry_hash=entry1.entry_hash
                )
            }
        )
    )
    peer_dl.save(entry0)
    peer_dl.save(entry1)

    sent = state_ledger_positions_trigger(
        peer_dl, peer_actor_id, SyncActivityAdapter(peer_dl)
    )
    assert sent == 1
    reads = peer_dl.list_objects("Read")
    assert len(reads) == 1
    assert peer_dl.list_objects("Reject") == []

    handle_inbox_item(
        actor_id=case_actor_id,
        obj=delivered(reads[0]),
        dl=case_actor_dl,
        dispatcher=case_actor_iso.app.state.dispatcher,
    )
    anyio.run(
        functools.partial(
            outbox_handler,
            case_actor_id,
            case_actor_dl,
            emitter=getattr(case_actor_iso.app.state, "emitter", None),
        )
    )

    state = case_actor_dl.read(
        VultronReplicationState(case_id=case.id_, peer_id=peer_actor_id).id_
    )
    assert state is not None
    assert state.last_acknowledged_hash == entry1.entry_hash
    peer_tail = max(
        (
            e
            for e in peer_dl.list_objects("CaseLedgerEntry")
            if getattr(e, "case_id", None) == case.id_
        ),
        key=lambda e: e.log_index,
    )
    assert peer_tail.entry_hash == entry2.entry_hash


def _drain_outbox(iso, actor_id: str, dl) -> None:
    """Deliver everything *actor_id* has queued, through the shared router."""
    anyio.run(
        functools.partial(
            outbox_handler,
            actor_id,
            dl,
            emitter=getattr(iso.app.state, "emitter", None),
        )
    )


@pytest.mark.spec("SYNC-16-001")
@pytest.mark.spec("SYNC-16-003")
@pytest.mark.spec("SYNC-16-007")
def test_a_diverged_replica_converges_after_the_case_managers_reseed(
    two_app_setup,
) -> None:
    """A replica whose embargo state diverged is repaired by a re-seed.

    The peer's replica lost its consent row for the proposed embargo, so the
    CASE_MANAGER's next copied entry, which updates that row, extends the
    peer's chain but does not apply to its case.  Every hop is a delivery
    between the two isolated apps: the peer holds the entry and sends a
    case-diverged fault (SYNC-16-001); the CASE_MANAGER answers with
    ``Announce(VulnerabilityCase)`` naming its ledger position (SYNC-16-003);
    the peer replaces its case and stores the held entry as the no-op the
    copy reflects (SYNC-16-007).  The peer ends with the CASE_MANAGER's case
    file and chain tail, and neither ledger records the fault (SYNC-16-002).
    """
    from test.support.embargo_register import propose, write_consent_rows
    from test.support.inbox_replay import held_depth
    from test.support.ledger import chain_tail, ledger_entries
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
    from vultron.core.behaviors.embargo.copy_commit import (
        commit_and_apply_embargo_entries,
        consent_row_entry,
    )
    from vultron.core.models._helpers import days_from_now_utc
    from vultron.core.models.case import VulnerabilityCase
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.core.models.embargo_apply import (
        ConsentRowChange,
        ConsentRowVerb,
    )
    from vultron.core.models.embargo_consent import EmbargoConsent
    from vultron.core.models.fault_classes import (
        VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED,
    )
    from vultron.core.states.participant_embargo_consent import (
        EmbargoConsentState,
    )
    from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup
    case_actor_id = _create_actor(
        case_actor_tc,
        f"{case_actor_iso.base_url}/api/v2",
        "case-actor-sync-1603",
        "Service",
    )
    peer_actor_id = _create_actor(
        peer_tc,
        f"{peer_iso.base_url}/api/v2",
        "peer-sync-1603",
        "Organization",
    )
    case_actor_dl = case_actor_iso.store_for(case_actor_id)
    peer_dl = peer_iso.store_for(peer_actor_id)
    _register_peer(
        case_actor_tc, "case-actor-sync-1603", peer_actor_id, "peer-sync-1603"
    )
    _register_peer(
        peer_tc,
        "peer-sync-1603",
        case_actor_id,
        "case-actor-sync-1603",
        "Service",
    )

    case = as_VulnerabilityCase(
        name="SYNC-16 divergence recovery case", attributed_to=_OWNER_ID
    )
    embargo = as_EmbargoEvent(
        id_=f"{case.id_}/embargo_events/e1",
        context=case.id_,
        end_time=days_from_now_utc(45),
    )
    manager_participant = as_CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    peer_participant = as_CaseParticipant(
        attributed_to=peer_actor_id, context=case.id_
    )
    for participant in (manager_participant, peer_participant):
        case.case_participants.append(participant.id_)
        case.actor_participant_index[str(participant.attributed_to)] = (
            participant.id_
        )
    # An open proposal and no embargo in force, so both are active
    # participants and every case-content send reaches the peer (CM-10-004).
    propose(case, embargo.id_)
    case_actor_dl.save(embargo)
    case_actor_dl.save(manager_participant)
    case_actor_dl.save(peer_participant)
    case_actor_dl.save(case)
    case_actor_dl.save(VultronService(id_=case_actor_id, context=case.id_))
    write_consent_rows(
        case_actor_dl, cast(VulnerabilityCase, case_actor_dl.read(case.id_))
    )
    # The peer's replica holds the same case file, then diverges: its copy
    # of its own record loses the consent row the next entry updates.
    for obj_id in (
        case.id_,
        embargo.id_,
        manager_participant.id_,
        peer_participant.id_,
    ):
        peer_dl.save(case_actor_dl.read(obj_id))
    diverged = cast(CaseParticipant, peer_dl.read(peer_participant.id_))
    diverged.embargo_consents = []
    peer_dl.save(diverged)

    commit_and_apply_embargo_entries(
        case_actor_dl,
        case.id_,
        [
            consent_row_entry(
                datalayer=case_actor_dl,
                trigger_activity=TriggerActivityAdapter(case_actor_dl),
                actor_id=case_actor_id,
                case_id=case.id_,
                change=ConsentRowChange(
                    verb=ConsentRowVerb.UPDATE,
                    row=EmbargoConsent(
                        embargo_id=embargo.id_,
                        state=EmbargoConsentState.INVITED,
                        attributed_to=peer_actor_id,
                    ),
                ),
                cause_id=f"{case.id_}/activities/invite",
                sync_port=SyncActivityAdapter(case_actor_dl),
            )
        ],
    )
    manager_ledger = ledger_entries(case_actor_dl, case.id_)
    assert len(manager_ledger) == 1

    # Each app's inbox delivers what it queues in answer, so draining the
    # CASE_MANAGER's outbox, then each again, runs every hop to quiescence.
    _drain_outbox(case_actor_iso, case_actor_id, case_actor_dl)
    _drain_outbox(peer_iso, peer_actor_id, peer_dl)
    _drain_outbox(case_actor_iso, case_actor_id, case_actor_dl)

    sealed = (
        read_sealed_body_dict(peer_dl, create.id_) or {}
        for create in peer_dl.list_objects("Create")
    )
    faults = [
        body
        for body in sealed
        if (body.get("object") or {}).get("failureClass")
        == VULTRON_FAILURE_LEDGER_ENTRY_REFUSED_CASE_DIVERGED
    ]
    assert len(faults) == 1, "the peer reported the divergence once"

    state = cast(
        VultronReplicationState,
        case_actor_dl.read(
            VultronReplicationState(
                case_id=case.id_, peer_id=peer_actor_id
            ).id_
        ),
    )
    assert state is not None and state.last_reseeded_at is not None
    assert held_depth(peer_dl, case.id_) == 0
    manager_case = cast(VulnerabilityCase, case_actor_dl.read(case.id_))
    peer_case = cast(VulnerabilityCase, peer_dl.read(case.id_))
    assert chain_tail(peer_dl, peer_case) == chain_tail(
        case_actor_dl, manager_case
    )
    assert peer_case.ledger_position == manager_case.ledger_position
    assert (
        cast(
            CaseParticipant, peer_dl.read(peer_participant.id_)
        ).embargo_consents
        == cast(
            CaseParticipant, case_actor_dl.read(peer_participant.id_)
        ).embargo_consents
    )
    assert ledger_entries(case_actor_dl, case.id_) == manager_ledger
