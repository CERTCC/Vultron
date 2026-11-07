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
"""Sent activities carry their author's proof, and the ledger keeps it (SIG).

Each test has a participant or the CASE_MANAGER send an ``Add(Note)`` built by
the sender's own trigger adapter, as its outbox seals it, and moves it between
stores only as that sealed body (ADR-0164).  The outbox signs every body
before sealing it (#5382), so each sealed body verifies by its author's
published key.  Nothing verifies on receipt yet, so the replica refusal test
is a strict ``xfail`` naming the Task that turns it green.
"""

import json
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.errors import VultronError
from vultron.wire.as2 import signing
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._ledger_network import MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-signed-entries"


def _published_key(actor_id: str) -> str:
    """The key *actor_id*'s profile publishes (``signing.published_multikey``).

    The profile route is what a verifier reads (SIG-02-001); here the test
    reads the same value without serving the profile.
    """
    key = signing.seeded_signing_key(actor_id)
    return signing.published_multikey(key, actor_id).public_key_multibase


def _note_body(
    dl: SqliteDataLayer, note_id: str, *, actor: str, to: str
) -> dict[str, Any]:
    """The sealed body *actor*'s adapter builds for a new note on the case."""
    if dl.read(note_id) is None:
        dl.create(as_Note(id_=note_id, content="signed", context=CASE_ID))
    _activity_id, body = TriggerActivityAdapter(dl).add_note_to_case(
        note_id=note_id, case_id=CASE_ID, actor=actor, to=[to]
    )
    return cast(dict[str, Any], json.loads(body))


def _owner_note(net: LedgerNetwork, note_id: str) -> dict[str, Any]:
    return _note_body(net.stores[OWNER], note_id, actor=OWNER, to=MANAGER)


def _commit(net: LedgerNetwork, body: dict[str, Any]) -> None:
    verdict = net.receive(MANAGER, body)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _announce_of(net: LedgerNetwork, activity_id: str) -> dict[str, Any]:
    """The ``Announce(CaseLedgerEntry)`` relaying *activity_id* to the owner."""
    [announce] = [
        body
        for body in net.ledger_announcements(OWNER)
        if (body["object"].get("payloadSnapshot") or {}).get("id")
        == activity_id
    ]
    return announce


def _owner_note_entries(net: LedgerNetwork) -> list[Any]:
    return [
        entry
        for entry in ledger_entries(net.stores[OWNER], CASE_ID)
        if entry.semantic_type == "add_note_to_case"
    ]


@pytest.mark.spec("SIG-01-001")
def test_a_sent_activity_carries_its_authors_proof():
    net = LedgerNetwork(CASE_ID)

    body = _owner_note(net, "https://example.org/notes/signed-1")

    assert isinstance(body.get("proof"), dict)
    assert body["proof"].get("verificationMethod", "").startswith(f"{OWNER}#")


@pytest.mark.spec("SIG-01-001")
def test_a_ledger_announce_carries_the_case_managers_proof():
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-2")
    _commit(net, body)

    announce = _announce_of(net, body["id"])

    assert isinstance(announce.get("proof"), dict)
    assert (
        announce["proof"]
        .get("verificationMethod", "")
        .startswith(f"{MANAGER}#")
    )


@pytest.mark.spec("SIG-01-002")
def test_a_sent_proof_names_the_cryptosuite_and_the_authors_key():
    net = LedgerNetwork(CASE_ID)

    proof = _owner_note(net, "https://example.org/notes/signed-3").get("proof")

    assert isinstance(proof, dict)
    assert proof.get("type") == "DataIntegrityProof"
    assert proof.get("cryptosuite") == "eddsa-jcs-2022"
    assert proof.get("proofPurpose") == "assertionMethod"
    assert proof.get("verificationMethod", "").startswith(f"{OWNER}#")
    assert proof.get("proofValue", "").startswith("z")


@pytest.mark.spec("SIG-01-001")
def test_a_sent_proof_verifies_by_the_authors_published_key():
    net = LedgerNetwork(CASE_ID)

    body = _owner_note(net, "https://example.org/notes/signed-6")

    signing.verify(body, _published_key(OWNER))
    assert signing.DATA_INTEGRITY_CONTEXT in body["@context"]


@pytest.mark.spec("SIG-01-001")
def test_a_ledger_announce_verifies_by_the_case_managers_published_key():
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-7")
    _commit(net, body)

    signing.verify(_announce_of(net, body["id"]), _published_key(MANAGER))


@pytest.mark.spec("SIG-04-001")
@pytest.mark.spec("VM-08-003")
def test_a_ledger_snapshot_keeps_the_senders_proof():
    """The relayed snapshot is the sender's sealed body, proof unchanged."""
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-4")
    _commit(net, body)

    snapshot = _announce_of(net, body["id"])["object"]["payloadSnapshot"]

    assert snapshot == body
    signing.verify(snapshot, _published_key(OWNER))


@pytest.mark.spec("SIG-04-001")
def test_a_snapshots_proof_survives_the_stores_rekeying():
    """A stored entry, read back after a restart, keeps a proof that verifies.

    The store rewrites ``id_``/``type_``/``context_`` keys at every nesting
    level on write (``_rekey_wire_identity``); the proof and the body it
    covers must come back as they were sealed.
    """
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-8")
    _commit(net, body)

    [entry] = [
        entry
        for entry in ledger_entries(net.reopen(MANAGER), CASE_ID)
        if entry.payload_snapshot.get("id") == body["id"]
    ]

    assert entry.payload_snapshot == body
    signing.verify(entry.payload_snapshot, _published_key(OWNER))


@pytest.mark.xfail(
    strict=True,
    reason="SIG-04-002: replicas do not check proofs yet. Tracked by #5386.",
)
@pytest.mark.spec("SIG-04-002")
def test_a_replica_refuses_an_entry_whose_author_proof_is_missing():
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-5")
    _commit(net, body)
    announce = _announce_of(net, body["id"])
    announce["object"]["payloadSnapshot"].pop("proof", None)
    # Removing the author's proof also breaks the CASE_MANAGER's proof on the
    # Announce, so ``net.receive`` re-signs the altered Announce through the
    # shared test helper and only the author's proof fails.  The refusal must
    # still name the snapshot's author, so that a replica checking only the
    # outer proof cannot pass this test.

    try:
        verdict = net.receive(OWNER, announce)
        refusal = str(verdict.reason or "")
    except VultronError as error:
        verdict, refusal = None, str(error)

    assert (
        verdict is None
        or verdict.disposition is not HandlerDisposition.APPLIED
    )
    assert "payloadSnapshot" in refusal and OWNER in refusal, refusal
    assert _owner_note_entries(net) == []
