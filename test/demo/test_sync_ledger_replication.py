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
"""SYNC integration tests for single-peer CaseLedgerEntry replication (#901)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import anyio
import pytest

from vultron.adapters.driven.asgi_emitter import ASGIEmitter
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_ledger import GENESIS_HASH, HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.use_cases.received.sync import (
    RejectLedgerEntryReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from test.demo.conftest import _TestASGIRouter, create_isolated_actor_app
from vultron.adapters.driving.fastapi.inbox_handler import (
    handle_inbox_item,
    inbox_handler,
)
from vultron.adapters.driving.fastapi.outbox_handler import outbox_handler
from vultron.adapters.driving.fastapi.outbox_handler import (
    configure_default_emitter,
    get_default_emitter,
)
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    reject_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_actor import CaseActor
from vultron.wire.as2.vocab.objects.case_participant import CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase

_CASE_ACTOR_BASE = "http://case-actor-sync-901.test"
_PEER_BASE = "http://peer-sync-901.test"


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


def _make_log_entry(
    case_id: str,
    log_index: int,
    prev_hash: str,
    event_type: str,
) -> VultronCaseLedgerEntry:
    record = HashChainLedgerRecord(
        case_id=case_id,
        log_index=log_index,
        object_id=case_id,
        event_type=event_type,
        payload_snapshot={"event_type": event_type},
        prev_log_hash=prev_hash,
    )
    return _to_persistable_entry(record)


@pytest.fixture
def two_app_setup() -> Iterator[tuple]:
    """Create two isolated actor apps connected by ``_TestASGIRouter``."""
    router = _TestASGIRouter()
    case_actor_iso = create_isolated_actor_app(
        base_url=_CASE_ACTOR_BASE, router=router
    )
    peer_iso = create_isolated_actor_app(base_url=_PEER_BASE, router=router)

    previous_emitter = get_default_emitter()
    configure_default_emitter(router)  # type: ignore[arg-type]

    with case_actor_iso.client as case_actor_tc:
        with peer_iso.client as peer_tc:
            for iso in (case_actor_iso, peer_iso):
                emitter = getattr(iso.app.state, "emitter", None)
                if isinstance(emitter, ASGIEmitter):
                    emitter._http_fallback = router  # type: ignore[assignment]
            yield case_actor_iso, peer_iso, case_actor_tc, peer_tc

    configure_default_emitter(previous_emitter)  # type: ignore[arg-type]
    case_actor_iso.dl.close()
    peer_iso.dl.close()


@pytest.mark.spec("SYNC-07-002")
@pytest.mark.spec("SYNC-02-003")
def test_sync_single_peer_happy_path_replication(two_app_setup) -> None:
    """CaseActor commit should replicate one CaseLedgerEntry to a peer replica."""
    case_actor_iso, peer_iso, case_actor_tc, peer_tc = two_app_setup

    case_actor_base_api = f"{case_actor_iso.base_url}/api/v2"
    peer_base_api = f"{peer_iso.base_url}/api/v2"

    case_actor_id = _create_actor(
        case_actor_tc, case_actor_base_api, "case-actor-sync-901", "Service"
    )
    peer_actor_id = _create_actor(
        peer_tc, peer_base_api, "peer-sync-901", "Organization"
    )
    # CaseActor must know peer recipient for outbox routing.
    _create_actor(
        case_actor_tc, peer_base_api, "peer-sync-901", "Organization"
    )

    case = VulnerabilityCase(name="SYNC-901 integration case")
    case_actor_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
    )
    peer_participant = CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_

    case_actor_iso.dl.save(case_actor_participant)
    case_actor_iso.dl.save(peer_participant)
    case_actor_iso.dl.save(case)

    response = case_actor_tc.post(
        f"/api/v2/actors/{_actor_slug(case_actor_id)}/demo/sync-log-entry",
        json={
            "case_id": case.id_,
            "object_id": case.id_,
            "event_type": "sync_901_happy_path",
        },
    )
    assert response.status_code == 202, response.text
    payload = response.json()

    entry_id = payload["log_entry_id"]
    peer_entry = peer_iso.dl.read(entry_id)
    assert (
        peer_entry is not None
    ), "Expected peer replica to contain the announced CaseLedgerEntry."
    assert peer_entry.case_id == case.id_
    assert peer_entry.log_index == payload["log_index"]
    assert peer_entry.entry_hash == payload["entry_hash"]
    assert peer_entry.log_object_id == case.id_
    assert peer_entry.event_type == "sync_901_happy_path"

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
    # Cross-register actors so each app can route to the other.
    _create_actor(
        case_actor_tc, peer_base_api, "peer-sync-902", "Organization"
    )
    _create_actor(
        peer_tc, case_actor_base_api, "case-actor-sync-902", "Service"
    )

    case = VulnerabilityCase(name="SYNC-902 mismatch/replay integration case")
    case_actor_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
    )
    peer_participant = CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_
    case_actor_iso.dl.save(case_actor_participant)
    case_actor_iso.dl.save(peer_participant)
    case_actor_iso.dl.save(case)
    case_actor_iso.dl.save(CaseActor(id_=case_actor_id, context=case.id_))

    entry0 = _make_log_entry(case.id_, 0, GENESIS_HASH, "sync_902_base")
    entry1 = _make_log_entry(case.id_, 1, entry0.entry_hash, "sync_902_mid")
    entry2 = _make_log_entry(case.id_, 2, entry1.entry_hash, "sync_902_tail")
    case_actor_iso.dl.save(entry0)
    case_actor_iso.dl.save(entry1)
    case_actor_iso.dl.save(entry2)
    peer_iso.dl.save(entry0)

    wire_entry2 = WireCaseLedgerEntry.model_validate(
        entry2.model_dump(mode="json")
    )
    out_of_chain_announce = announce_log_entry_activity(
        entry=wire_entry2,
        actor=case_actor_id,
        to=[peer_actor_id],
    )
    peer_actor_dl = peer_iso.dl.clone_for_actor(peer_actor_id)
    case_actor_dl = case_actor_iso.dl.clone_for_actor(case_actor_id)
    try:
        handle_inbox_item(
            actor_id=peer_actor_id,
            obj=out_of_chain_announce,
            dl=peer_iso.dl,
            dispatcher=peer_iso.app.state.dispatcher,
        )
        peer_reject_events = [
            cast(RejectLogEntryReceivedEvent, extract_event(activity))
            for activity in peer_iso.dl.list_objects("Reject")
        ]
        assert (
            peer_reject_events
        ), "Expected peer to emit Reject(CaseLedgerEntry)."
        emitted_reject_event = peer_reject_events[-1]
        assert emitted_reject_event.actor_id == peer_actor_id
        assert emitted_reject_event.last_accepted_hash == entry0.entry_hash
        assert peer_iso.dl.read(entry2.id_) is None

        reject_for_case_actor = cast(
            RejectLogEntryReceivedEvent,
            extract_event(
                reject_log_entry_activity(
                    entry=wire_entry2,
                    context=entry0.entry_hash,
                    actor=peer_actor_id,
                    to=[case_actor_id],
                )
            ),
        )

        RejectLedgerEntryReceivedUseCase(
            case_actor_iso.dl,
            reject_for_case_actor,
            sync_port=SyncActivityAdapter(case_actor_iso.dl),
        ).execute()

        anyio.run(
            outbox_handler,
            case_actor_id,
            case_actor_dl,
            case_actor_iso.dl,
            case_actor_iso.app.state.emitter,
        )
        anyio.run(
            inbox_handler,
            peer_actor_id,
            peer_iso.dl,
            peer_actor_dl,
            peer_iso.app.state.emitter,
            peer_iso.app.state.dispatcher,
        )
    finally:
        case_actor_dl.close()
        peer_actor_dl.close()

    state_id = VultronReplicationState(
        case_id=case.id_, peer_id=peer_actor_id
    ).id_
    replication_state = case_actor_iso.dl.read(state_id)
    assert replication_state is not None
    assert replication_state.last_acknowledged_hash == entry0.entry_hash

    assert peer_iso.dl.read(entry1.id_) is not None
    assert peer_iso.dl.read(entry2.id_) is not None
    assert case_actor_iso.dl is not peer_iso.dl


@pytest.mark.spec("SYNC-03-003")
@pytest.mark.spec("SYNC-07-003")
def test_sync_duplicate_delivery_idempotency(
    two_app_setup, monkeypatch
) -> None:
    """Duplicate delivery of Announce(CaseLedgerEntry) must produce one replica.

    Delivers the same ``Announce(CaseLedgerEntry)`` twice to the peer actor
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

    case = VulnerabilityCase(
        name="SYNC-903 duplicate delivery integration case"
    )
    case_actor_participant = CaseParticipant(
        attributed_to=case_actor_id,
        context=case.id_,
    )
    peer_participant = CaseParticipant(
        attributed_to=peer_actor_id,
        context=case.id_,
    )
    case.case_participants.append(case_actor_participant.id_)
    case.case_participants.append(peer_participant.id_)
    case.actor_participant_index[case_actor_id] = case_actor_participant.id_
    case.actor_participant_index[peer_actor_id] = peer_participant.id_

    # Peer needs the case and participants in its DataLayer to process inbound
    # Announce(CaseLedgerEntry) as a participant, not as a CaseActor owner.
    peer_iso.dl.save(case_actor_participant)
    peer_iso.dl.save(peer_participant)
    peer_iso.dl.save(case)

    saved_case_ledger_entry_ids: list[str] = []
    original_save = peer_iso.dl.save

    def save_spy(obj, *args, **kwargs):
        if getattr(obj, "type_", None) == "CaseLedgerEntry":
            saved_case_ledger_entry_ids.append(getattr(obj, "id_", ""))
        return original_save(obj, *args, **kwargs)

    monkeypatch.setattr(peer_iso.dl, "save", save_spy)

    entry = _make_log_entry(case.id_, 0, GENESIS_HASH, "sync_903_dup")
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    announce = announce_log_entry_activity(
        entry=wire_entry,
        actor=case_actor_id,
        to=[peer_actor_id],
    )

    # Deliver the same Announce(CaseLedgerEntry) twice.
    for _ in range(2):
        handle_inbox_item(
            actor_id=peer_actor_id,
            obj=announce,
            dl=peer_iso.dl,
            dispatcher=peer_iso.app.state.dispatcher,
        )

    assert saved_case_ledger_entry_ids == [entry.id_]

    # Peer replica must contain exactly one copy (idempotent behavior).
    stored_entries = [
        e
        for e in peer_iso.dl.list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == case.id_
    ]
    assert (
        len(stored_entries) == 1
    ), f"Expected exactly 1 CaseLedgerEntry replica, got {len(stored_entries)}"
    assert stored_entries[0].id_ == entry.id_

    # AC-4 guard: each actor app must use its own isolated DataLayer.
    assert case_actor_iso.dl is not peer_iso.dl
