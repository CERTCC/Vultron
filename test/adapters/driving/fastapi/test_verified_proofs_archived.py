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
"""The archived record names each proof the inbox verified (SIG-03-004).

A delivery is verified in the inbox route, before it is parsed, and
archived later by the background run.  The record the receiver archives
keeps, for each proof, the author, the key id and the key as fetched from
the author's profile, written in the archive's own save.  A refused body
stores nothing, and a delivery left in holding keeps the proofs on its held
record, so the replay that archives it keeps them too.
"""

import json
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import served_store
from test.core.use_cases.received._ledger_network import (
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.inbox_orchestration.ports import (
    FastAPIReceivedOutcomePort,
)
from vultron.adapters.driving.fastapi.verified_proofs import (
    VerifiedProofs,
    payload_activity_id,
)
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.verified_proof import VerifiedProof
from vultron.core.services.received_holding import (
    hold_for_replay,
    hold_unjudged_for_replay,
    keep_verified_proofs,
)
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)
from vultron.wire.as2 import signing
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

CASE_ID = "https://example.org/cases/verified-proofs-archived"
_INBOX = "/api/v2/actors/coord/inbox/"
_ACTIVITY = "https://example.org/activities/held"
_BODY = json.dumps({"id": _ACTIVITY, "type": "Create", "actor": OWNER})


def _proof(author: str = OWNER) -> VerifiedProof:
    key = signing.seeded_signing_key(author)
    return VerifiedProof(
        author_id=author,
        verification_method=key.key_id,
        public_key_multibase=key.public_key_multibase,
    )


@pytest.fixture
def served_manager() -> Iterator[tuple[TestClient, LedgerNetwork]]:
    """The CASE_MANAGER's store served by a real app, plus its network."""
    net = LedgerNetwork(CASE_ID)
    with served_store(net.stores[MANAGER], MANAGER, "Coordinator") as (
        client,
        _emitter,
    ):
        yield client, net


def _owner_note(net: LedgerNetwork, note_id: str) -> dict[str, Any]:
    """The sealed, signed body the owner's adapter builds for a new note."""
    dl = net.stores[OWNER]
    dl.create(as_Note(id_=note_id, content="signed", context=CASE_ID))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=CASE_ID, actor=OWNER, to=[MANAGER]
    )
    return cast(dict[str, Any], json.loads(body))


def _record(dl: Any, activity_id: str) -> ReceivedActivityRecord | None:
    stored = dl.read(ReceivedActivityRecord.build_id(activity_id))
    return stored if isinstance(stored, ReceivedActivityRecord) else None


@pytest.fixture
def dl() -> Iterator[SqliteDataLayer]:
    store = SqliteDataLayer("sqlite:///:memory:", actor_id=MANAGER)
    yield store
    store.close()


@pytest.mark.integration
@pytest.mark.spec("SIG-03-004")
def test_an_archived_delivery_names_the_proof_and_key_it_verified(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/archived")

    response = client.post(_INBOX, json=body)

    assert response.status_code == 202, response.text
    record = _record(net.stores[MANAGER], body["id"])
    assert record is not None
    assert record.stage is ReceivedStage.ARCHIVED
    assert record.verified_proofs == [_proof()]


@pytest.mark.integration
@pytest.mark.spec("SIG-03-004")
def test_a_refused_body_stores_no_record(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/refused")
    body.pop("proof")

    response = client.post(_INBOX, json=body)

    assert response.status_code == 422, response.text
    assert _record(net.stores[MANAGER], body["id"]) is None


@pytest.mark.spec("SIG-03-004")
def test_the_archive_writes_the_proofs_in_its_own_save(dl: SqliteDataLayer):
    hold_for_replay(dl, _ACTIVITY, _BODY)
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    archive_applied(dl, _ACTIVITY, [_proof()])

    archived = _record(dl, _ACTIVITY)
    assert archived is not None
    assert archived.stage is ReceivedStage.ARCHIVED
    assert archived.verified_proofs == [_proof()]


@pytest.mark.spec("SIG-03-004")
def test_a_held_delivery_keeps_its_proofs_through_to_its_archive(
    dl: SqliteDataLayer,
):
    """The replay that archives a held delivery notes them from its record."""
    hold_for_replay(dl, _ACTIVITY, _BODY)
    assert keep_verified_proofs(dl, _ACTIVITY, [_proof()])

    # The replay's inbox run reads them back off the held record.
    replay = VerifiedProofs()
    replay.note_held(dl, _ACTIVITY)
    assert replay.of(_ACTIVITY) == (_proof(),)
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    FastAPIReceivedOutcomePort(dl, replay).apply(_ACTIVITY)

    archived = _record(dl, _ACTIVITY)
    assert archived is not None
    assert archived.verified_proofs == [_proof()]


def test_an_archive_given_no_proofs_keeps_the_ones_held(dl: SqliteDataLayer):
    hold_for_replay(dl, _ACTIVITY, _BODY)
    keep_verified_proofs(dl, _ACTIVITY, [_proof()])
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    archive_applied(dl, _ACTIVITY)

    archived = _record(dl, _ACTIVITY)
    assert archived is not None
    assert archived.verified_proofs == [_proof()]


def test_keeping_proofs_writes_only_a_record_in_holding(dl: SqliteDataLayer):
    assert not keep_verified_proofs(dl, _ACTIVITY, [_proof()])
    hold_for_replay(dl, _ACTIVITY, _BODY)
    assert not keep_verified_proofs(dl, _ACTIVITY, [])
    assert keep_verified_proofs(dl, _ACTIVITY, [_proof()])
    # Already kept: not written again.
    assert not keep_verified_proofs(dl, _ACTIVITY, [_proof("https://x/y")])


@pytest.mark.spec("SIG-03-005")
def test_a_receipt_stub_keeps_no_proofs(dl: SqliteDataLayer):
    hold_for_replay(dl, _ACTIVITY, _BODY)
    keep_verified_proofs(dl, _ACTIVITY, [_proof()])
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    stub = write_receipt_stub(dl, _ACTIVITY, sender_id=OWNER, reason="no")

    assert stub.stage is ReceivedStage.REFUSED
    assert stub.verified_proofs == []


@pytest.mark.spec("SIG-03-005")
def test_a_stub_carrying_proofs_is_refused_at_construction():
    with pytest.raises(ValueError, match="verified proofs"):
        ReceivedActivityRecord(
            activity_id=_ACTIVITY,
            stage=ReceivedStage.REFUSED,
            sender_id=OWNER,
            refusal_reason="no",
            body_hash="abc",
            verified_proofs=[_proof()],
        )


def test_an_unjudged_hold_keeps_the_proofs(dl: SqliteDataLayer):
    hold_for_replay(dl, _ACTIVITY, _BODY)
    keep_verified_proofs(dl, _ACTIVITY, [_proof()])
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    hold_unjudged_for_replay(dl, _ACTIVITY)

    rehold = _record(dl, _ACTIVITY)
    assert rehold is not None
    assert rehold.verified_proofs == [_proof()]


def test_payload_activity_id_reads_only_a_named_id():
    assert payload_activity_id({"id": _ACTIVITY}) == _ACTIVITY
    assert payload_activity_id({"id": ""}) is None
    assert payload_activity_id({}) is None
    assert payload_activity_id("not a body") is None
