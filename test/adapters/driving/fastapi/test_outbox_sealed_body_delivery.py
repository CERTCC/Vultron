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

"""End to end through a real store: adapter seals, handler relays (VM-08-003).

These tests use the real ``SqliteDataLayer`` and the real
``TriggerActivityAdapter`` so that the body the adapter hands core is
demonstrably the body the outbox handler hands the emitter — with the case
stub, the ``context``, and every inline object exactly as the factory built
them.  A ``MagicMock`` store cannot show that; only the round trip can.

Module under test: ``vultron/adapters/driving/fastapi/outbox_handler.py`` and
``vultron/adapters/outbox_sealed_body.py``.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi import outbox_handler as oh
from vultron.adapters.outbox_sealed_body import read_sealed_body
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.actor import EmitInviteActorToCaseNode
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.em import EM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_ACTOR = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/vendor"
_ZERO_HASH = "0" * 64


@pytest.fixture
def dl():
    _dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_ACTOR)
    yield _dl
    _dl.clear_all()
    _dl.close()


def _deliver(dl, activity_id: str) -> tuple[str, str, list[str]]:
    """Run the handler once and return what the emitter was handed."""
    emitter = AsyncMock()
    asyncio.run(oh.handle_outbox_item(_ACTOR, activity_id, dl, emitter))
    emitter.emit.assert_called_once()
    delivered_id, body, recipients = emitter.emit.call_args[0]
    return str(delivered_id), str(body), list(recipients)


@pytest.mark.spec("VM-08-003")
def test_the_emitter_receives_the_blob_the_adapter_returned_to_core(dl):
    """Port blob == sealed body == delivered body, byte for byte."""
    case = as_VulnerabilityCase(
        name="CVE-2026-0002",
        attributed_to=_ACTOR,
        stub_summary="Security issue — details shared after acceptance",
    )
    dl.create(case)
    adapter = TriggerActivityAdapter(dl)

    activity_id, blob = adapter.invite_actor_to_case(
        invitee_id=_INVITEE,
        case_id=case.id_,
        actor=_ACTOR,
        to=[_INVITEE],
        roles=["vendor"],
    )

    sealed = read_sealed_body(dl, activity_id)
    assert sealed is not None and sealed.body == blob
    delivered_id, delivered_body, recipients = _deliver(dl, activity_id)
    assert delivered_id == activity_id
    assert delivered_body == blob
    assert recipients == [_INVITEE]


@pytest.mark.spec("CM-17-002")
@pytest.mark.spec("VM-08-003")
def test_the_invite_case_stub_survives_to_the_emitter(dl):
    """The Invite's ``target`` reaches the wire as the stub the factory built.

    Reading the record back would have rehydrated ``target`` into the full
    stored case and then collapsed it to a bare URI, which is how the enriched
    stub CM-17-002 requires was being lost before delivery.
    """
    _stub_summary = "Security issue — details shared after acceptance"
    case = as_VulnerabilityCase(
        name="CVE-2026-0003",
        attributed_to=_ACTOR,
        stub_summary=_stub_summary,
    )
    dl.create(case)
    activity_id, _ = TriggerActivityAdapter(dl).invite_actor_to_case(
        invitee_id=_INVITEE, case_id=case.id_, actor=_ACTOR, to=[_INVITEE]
    )

    _, body, _ = _deliver(dl, activity_id)
    delivered = json.loads(body)
    assert delivered["target"] == {
        "@context": delivered["target"]["@context"],
        "type": "VulnerabilityCaseStub",
        "id": f"{case.id_}/stub",
        "caseId": case.id_,
        "summary": _stub_summary,
    }
    assert delivered["context"] == case.id_


@pytest.mark.spec("SYNC-02-004")
def test_the_sync_adapter_seals_the_announce_it_queues(dl):
    """Announce(CaseLedgerEntry) is sealed at emission and relayed whole."""
    entry = _to_persistable_entry(
        HashChainLedgerRecord(
            case_id="https://example.org/cases/c-sync",
            log_index=0,
            object_id="https://example.org/activities/logged",
            event_type="log_entry_committed",
            payload_snapshot={"state": "replicated"},
            prev_log_hash=_ZERO_HASH,
        )
    )
    dl.save(entry)
    assert SyncActivityAdapter(dl).send_announce_log_entry(
        entry, actor_id=_ACTOR, to=[_INVITEE]
    )
    (activity_id,) = dl.outbox_list()

    _, body, recipients = _deliver(dl, activity_id)
    delivered = json.loads(body)
    assert recipients == [_INVITEE]
    assert delivered["object"]["type"] == "CaseLedgerEntry"
    assert delivered["object"]["id"] == entry.id_
    assert delivered["object"]["logIndex"] == 0


def test_a_queued_id_with_no_sealed_body_is_dropped_not_delivered(dl, caplog):
    """The activity record alone is not enough: no seal, no delivery."""
    case = as_VulnerabilityCase(name="CVE-2026-0004", attributed_to=_ACTOR)
    dl.create(case)
    emitter = AsyncMock()
    with caplog.at_level("ERROR"):
        asyncio.run(oh.handle_outbox_item(_ACTOR, case.id_, dl, emitter))
    emitter.emit.assert_not_called()
    assert any("No sealed body" in r.message for r in caplog.records)


@pytest.mark.spec("VM-08-003")
@pytest.mark.spec("CM-17-002")
def test_ledger_snapshot_equals_delivered_body_end_to_end(dl):
    """#2654 AC-4 in one store: emit node → sealed → ledger → handler → emitter.

    The CASE_MANAGER emits an Invite for a case under an active embargo (so the
    stub is enriched), commits its canonical entry, and the outbox delivers.
    The entry's ``payloadSnapshot`` is the delivered text decoded — nothing in
    between rewrote either side.
    """
    case_id = "urn:uuid:e2e-sealed-ledger"
    manager = CaseParticipant(
        id_=f"{case_id}/participants/cm",
        attributed_to=_ACTOR,
        case_roles=[CVDRole.COORDINATOR, CVDRole.CASE_MANAGER],
    )
    embargo = EmbargoEvent(
        id_=f"{case_id}/embargoes/e0",
        context=case_id,
        end_time=days_from_now_utc(45),
    )
    case = VulnerabilityCase(
        id_=case_id,
        name="e2e",
        attributed_to=_ACTOR,
        stub_summary="Security issue — e2e sealed ledger test",
        case_participants=[manager],
        actor_participant_index={_ACTOR: str(manager.id_)},
        case_statuses=[
            CaseStatus(
                context=case_id,
                attributed_to=_ACTOR,
                em=EmDimension(state=EM.ACTIVE),
            )
        ],
        active_embargo=str(embargo.id_),
    )
    for obj in (manager, embargo, case):
        dl.create(obj)

    result = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        sync_port=SyncActivityAdapter(dl),
    ).execute_with_setup(
        tree=EmitInviteActorToCaseNode(case_id=case_id, invitee_id=_INVITEE),
        actor_id=_ACTOR,
    )
    assert result.status.name == "SUCCESS", result.feedback_message

    (entry,) = [
        e
        for e in dl.list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry)
        and e.event_type == "invite_actor_to_case"
    ]
    _, delivered_body, recipients = _deliver(dl, entry.log_object_id)

    assert recipients == [_INVITEE]
    assert entry.payload_snapshot == json.loads(delivered_body)
    assert "activeEmbargo" in entry.payload_snapshot["target"]
