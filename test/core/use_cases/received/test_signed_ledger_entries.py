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
the sender's own trigger adapter, as its outbox would seal it, and moves it
between stores only as that sealed body (ADR-0164).  Nothing signs yet, so
each test of a proof the sender or a replica makes is a strict ``xfail``
naming the Task that turns it green; that Task replaces it with a passing
test.  The ledger snapshot is the body as received (VM-08-003), so a sender's
proof already survives the commit, and that test passes today.
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
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from ._ledger_network import MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-signed-entries"
_NOT_SIGNED = "the outbox does not sign activities yet. Tracked by #5382."
#: A proof of the right shape.  The network routes bodies past the ingress, so
#: nothing verifies it here, and the snapshot test uses it in place of the
#: real proof: whether the outbox signs at all is SIG-01-001's test.
_PLACEHOLDER_PROOF = {
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": f"{OWNER}#main-key",
    "proofPurpose": "assertionMethod",
    "created": "2026-10-28T00:00:00Z",
    "proofValue": "z" + "1" * 86,
}


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


@pytest.mark.xfail(strict=True, reason=f"SIG-01-001: {_NOT_SIGNED}")
@pytest.mark.spec("SIG-01-001")
def test_a_sent_activity_carries_its_authors_proof():
    net = LedgerNetwork(CASE_ID)

    body = _owner_note(net, "https://example.org/notes/signed-1")

    assert isinstance(body.get("proof"), dict)
    assert body["proof"].get("verificationMethod", "").startswith(f"{OWNER}#")


@pytest.mark.xfail(strict=True, reason=f"SIG-01-001: {_NOT_SIGNED}")
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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SIG-01-002: no proof is made yet. Tracked by #5380 (proof form) "
        "and #5382 (outbox signs)."
    ),
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


@pytest.mark.spec("SIG-04-001")
@pytest.mark.spec("VM-08-003")
def test_a_ledger_snapshot_keeps_the_senders_proof():
    net = LedgerNetwork(CASE_ID)
    body = _owner_note(net, "https://example.org/notes/signed-4")
    _commit(net, {**body, "proof": _PLACEHOLDER_PROOF})

    snapshot = _announce_of(net, body["id"])["object"]["payloadSnapshot"]

    assert snapshot.get("proof") == _PLACEHOLDER_PROOF


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
    # Announce.  The implementing Task re-signs the Announce through the shared
    # test helper (#5384), so only the author's proof fails; until then the
    # refusal must name the snapshot's author, so that a replica checking only
    # the outer proof cannot pass this test.

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
