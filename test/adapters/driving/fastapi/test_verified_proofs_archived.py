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
the author's profile.  The parsed activity and its event carry them, so
intake writes them in the record's first save and the archive keeps them;
a crash between saves loses none.  A refused body stores nothing, a reused
id from another sender leaves the first sender's key, and a delivery left
in holding keeps the proofs on its held record, so the replay that archives
it keeps them too.
"""

import json
from collections.abc import Iterator
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from test.adapters.driving.fastapi._redelivery import served_store
from test.core.use_cases.received._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from test.support.act_clock import ACT_AT
from test.support.objects import make
from test.support.signing import resigned
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.adapters.driving.fastapi.verified_proofs import (
    VerifiedProofs,
    payload_activity_id,
)
from vultron.adapters.inbox_staging import InlineObjectStaging
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models._helpers import now_utc
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.verified_proof import VerifiedProof
from vultron.core.services.received_holding import (
    hold_for_replay,
    hold_unjudged_for_replay,
)
from vultron.core.services.received_outcome import (
    archive_applied,
    write_receipt_stub,
)
from vultron.errors import VultronWiringError
from vultron.semantic_registry import extract_event
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
    dl.create(make(as_Note, id_=note_id, content="signed", context=CASE_ID))
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


@pytest.mark.integration
@pytest.mark.spec("SIG-03-004")
def test_a_reused_id_from_another_sender_leaves_the_first_senders_key(
    served_manager: tuple[TestClient, LedgerNetwork],
):
    """A different body under a held id is refused, so its key is never kept."""
    client, net = served_manager
    body = _owner_note(net, "https://example.org/notes/first")
    assert client.post(_INBOX, json=body).status_code == 202
    reused = resigned(body, actor=BYSTANDER, author=BYSTANDER)

    response = client.post(_INBOX, json=reused)

    assert response.status_code == 202, response.text
    record = _record(net.stores[MANAGER], body["id"])
    assert record is not None
    assert record.verified_proofs == [_proof()]


def _parsed(
    net: LedgerNetwork, note_id: str, proofs: tuple[VerifiedProof, ...]
) -> Any:
    """The owner's note as the inbox parses it, carrying *proofs*."""
    body = _owner_note(net, note_id)
    verified = VerifiedProofs()
    verified.note(body["id"], proofs)
    adapter = FastAPIIngressAdapter(
        dl=net.stores[MANAGER], verified_proofs=verified
    )
    activity = adapter.parse(body)
    assert activity is not None
    return activity


@pytest.mark.spec("SIG-03-004")
def test_the_parsed_activity_and_its_event_carry_the_verified_proofs():
    net = LedgerNetwork(CASE_ID)
    activity = _parsed(net, "https://example.org/notes/parsed", (_proof(),))

    assert activity.verified_proofs == (_proof(),)
    assert extract_event(activity).verified_proofs == [_proof()]


@pytest.mark.spec("SIG-03-004")
def test_a_deferred_delivery_keeps_its_proofs_through_its_replay():
    """Held from the staged rebuild, then replayed from the held record."""
    net = LedgerNetwork(CASE_ID)
    dl = net.stores[MANAGER]
    activity = _parsed(net, "https://example.org/notes/deferred", (_proof(),))
    staging = InlineObjectStaging(dl)
    assert staging.rehydrate_parsed(activity) is not None

    assert staging.hold_for_replay(activity.id_, received_at=now_utc())

    held = _record(dl, activity.id_)
    assert held is not None
    assert held.replay_owed
    assert held.verified_proofs == [_proof()]
    replay = InlineObjectStaging(dl).rehydrate_deferred(activity.id_)
    assert replay is not None
    assert replay.verified_proofs == (_proof(),)
    assert extract_event(replay).verified_proofs == [_proof()]


@pytest.mark.spec("SIG-03-004")
def test_a_replay_deferred_again_is_held_again_with_its_proofs():
    """The released record's proofs go into the hold that replaces it."""
    net = LedgerNetwork(CASE_ID)
    dl = net.stores[MANAGER]
    activity = _parsed(net, "https://example.org/notes/again", (_proof(),))
    staging = InlineObjectStaging(dl)
    assert staging.rehydrate_parsed(activity) is not None
    assert staging.hold_for_replay(activity.id_, received_at=now_utc())
    replaying = InlineObjectStaging(dl)
    assert replaying.rehydrate_deferred(activity.id_) is not None
    assert _record(dl, activity.id_) is None, "the replay released it"

    assert replaying.hold_for_replay(activity.id_, received_at=now_utc())

    held = _record(dl, activity.id_)
    assert held is not None
    assert held.replay_owed
    assert held.verified_proofs == [_proof()]


@pytest.mark.spec("SIG-03-004")
def test_a_new_hold_records_the_proofs_given(dl: SqliteDataLayer):
    hold_for_replay(
        dl,
        _ACTIVITY,
        _BODY,
        received_at=now_utc(),
        verified_proofs=[_proof()],
    )

    held = _record(dl, _ACTIVITY)
    assert held is not None
    assert held.verified_proofs == [_proof()]


def test_the_archive_keeps_the_proofs_the_record_holds(dl: SqliteDataLayer):
    hold_for_replay(
        dl,
        _ACTIVITY,
        _BODY,
        received_at=now_utc(),
        verified_proofs=[_proof()],
    )
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    archive_applied(dl, _ACTIVITY)

    archived = _record(dl, _ACTIVITY)
    assert archived is not None
    assert archived.stage is ReceivedStage.ARCHIVED
    assert archived.verified_proofs == [_proof()]


def test_sealing_other_proofs_on_an_activity_is_refused():
    net = LedgerNetwork(CASE_ID)
    activity = _parsed(net, "https://example.org/notes/sealed", (_proof(),))

    activity.seal_verified_proofs([_proof()])
    activity.seal_verified_proofs([])
    with pytest.raises(ValueError, match="different verified proofs"):
        activity.seal_verified_proofs([_proof(BYSTANDER)])


@pytest.mark.spec("SIG-03-005")
def test_a_receipt_stub_keeps_no_proofs(dl: SqliteDataLayer):
    hold_for_replay(
        dl,
        _ACTIVITY,
        _BODY,
        received_at=now_utc(),
        verified_proofs=[_proof()],
    )
    held = _record(dl, _ACTIVITY)
    assert held is not None
    dl.save(held.model_copy(update={"replay_owed": False}))

    stub = write_receipt_stub(
        dl, _ACTIVITY, sender_id=OWNER, reason="no", received_at=now_utc()
    )

    assert stub.stage is ReceivedStage.REFUSED
    assert stub.verified_proofs == []
    stored = _record(dl, _ACTIVITY)
    assert stored is not None
    assert stored.is_receipt_stub
    assert stored.verified_proofs == []


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
            received_at=ACT_AT,
        )


def test_an_unjudged_hold_keeps_the_proofs(dl: SqliteDataLayer):
    hold_for_replay(
        dl,
        _ACTIVITY,
        _BODY,
        received_at=now_utc(),
        verified_proofs=[_proof()],
    )
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


@pytest.mark.integration
@pytest.mark.spec("SIG-03-004")
def test_a_relayed_entry_archives_the_managers_proof_then_the_authors():
    """A replica's record of a relayed entry names both proofs it verified."""
    net = LedgerNetwork(CASE_ID)
    net.receive(MANAGER, _owner_note(net, "https://example.org/notes/relayed"))
    [announce] = net.queued(MANAGER, to=BYSTANDER, type_="Announce")[-1:]
    relayed = read_sealed_body_dict(net.stores[MANAGER], announce.id_)
    assert relayed is not None

    with served_store(net.stores[BYSTANDER], BYSTANDER, "Bystander") as (
        replica,
        _emitter,
    ):
        response = replica.post("/api/v2/actors/vendor-b/inbox/", json=relayed)

    assert response.status_code == 202, response.text
    record = _record(net.stores[BYSTANDER], relayed["id"])
    assert record is not None
    assert record.verified_proofs == [_proof(MANAGER), _proof(OWNER)]


def test_proofs_for_a_body_that_names_no_id_are_refused():
    """They could reach no record, so noting them raises, never drops them."""
    with pytest.raises(VultronWiringError, match="names no id"):
        VerifiedProofs().note(
            payload_activity_id({"type": "Create"}), [_proof()]
        )


def test_no_proofs_for_a_body_that_names_no_id_note_nothing():
    verified = VerifiedProofs()
    verified.note(None, ())
    assert verified.of(_ACTIVITY) == ()
