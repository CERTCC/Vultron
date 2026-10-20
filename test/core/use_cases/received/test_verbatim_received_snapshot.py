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
"""A received entry records the received JSON verbatim (CLP-07-011, ADR-0107).

Each test delivers an ``Add(Note)`` to the CASE_MANAGER through the inbox's own
parse edge: ``FastAPIIngressAdapter`` parses the body (the artifact, A) and
rehydrates it into the routing copy (B), and ``prepare_for_dispatch`` extracts
the event the use case runs on.  The entry records A, which the parser sealed;
B, the receiver's store and the parsed object graph are not consulted, so a
replica receiving the entry holds what the sender sent.
"""

import copy
import json
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import run_use_case
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.wire.as2.factories import add_note_to_case_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-verbatim"


def _add_note_body(note_id: str, **extra: Any) -> dict[str, Any]:
    """The body *OWNER*'s outbox delivers for a new note on the case.

    The note travels inline, since the Add introduces it (AKM-02-004); the
    case is named by URI, as every replica holds it (AKM-02-002).
    """
    activity = add_note_to_case_activity(
        as_Note(id_=note_id, content="verbatim", context=CASE_ID),
        target=CASE_ID,
        actor=OWNER,
        to=[MANAGER],
    )
    return {**json.loads(dump_outbound_body(activity)), **extra}


def _deliver(net: LedgerNetwork, body: dict[str, Any]) -> Any:
    """Route *body* to the CASE_MANAGER through the inbox's parse edge.

    Returns the routing copy the use case ran on (B).
    """
    dl = net.stores[MANAGER]
    ingress = FastAPIIngressAdapter(dl)
    artifact = ingress.parse(copy.deepcopy(body))
    assert artifact is not None
    routed = ingress.rehydrate(artifact)
    event = prepare_for_dispatch(routed).model_copy(
        update={"receiving_actor_id": MANAGER}
    )
    verdict = run_use_case(dl, event)
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    return routed


def _note_entry(net: LedgerNetwork, actor_id: str) -> CaseLedgerEntry:
    entries = [
        entry
        for entry in ledger_entries(net.stores[actor_id], CASE_ID)
        if entry.semantic_type == "add_note_to_case"
    ]
    assert len(entries) == 1, [e.semantic_type for e in entries]
    return entries[0]


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("CLP-07-006")
def test_the_entry_records_the_received_body_unchanged():
    """No field dropped, re-dumped, inlined, patched or merged.

    The bare case URI stays bare even though the receiver holds the case,
    and the ``context`` is the sender's, not one written in.
    """
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body("https://example.org/notes/verbatim-1")

    _deliver(net, body)

    snapshot = _note_entry(net, MANAGER).payload_snapshot
    assert snapshot == body
    assert list(snapshot) == list(body), "key order is the sender's"
    assert snapshot["target"] == CASE_ID


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-011")
def test_a_change_to_the_received_body_changes_the_snapshot():
    """A body differing only by a key this receiver does not read (MV-11-003)
    and by key order is recorded with that key, in that order."""
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body("https://example.org/notes/verbatim-2")
    changed = dict(
        reversed(list({**body, "exampleExtension": {"kept": [1, 2]}}.items()))
    )

    _deliver(net, changed)

    snapshot = _note_entry(net, MANAGER).payload_snapshot
    assert snapshot == changed
    assert list(snapshot) == list(changed)
    assert snapshot != body


@pytest.mark.spec("CLP-07-006")
@pytest.mark.spec("CLP-07-011")
def test_nothing_but_the_received_body_changes_the_snapshot():
    """The receiver's store does not reach it.

    The CASE_MANAGER's stored case is renamed, so the routing copy is
    hydrated with a case its sender never sent; the entry is the body still.
    That
    the parsed graph cannot reach the evidence either is VM-08-002's
    (``test/architecture/test_wire_artifact_immutability.py``).
    """
    net = LedgerNetwork(CASE_ID)
    net.bypass_ledger()
    manager_dl = net.stores[MANAGER]
    manager_dl.save(
        net.case(MANAGER).model_copy(update={"name": "renamed by receiver"})
    )
    body = _add_note_body("https://example.org/notes/verbatim-3")

    _deliver(net, body)

    assert _note_entry(net, MANAGER).payload_snapshot == body


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("CLP-02-003")
def test_the_recorded_snapshot_revalidates_through_its_wire_class():
    """The snapshot is an AS2 activity as it stands, with no key renamed."""
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body("https://example.org/notes/verbatim-5")

    _deliver(net, body)

    snapshot = _note_entry(net, MANAGER).payload_snapshot
    activity = cast(
        as_Activity,
        find_in_vocabulary(snapshot["type"]).model_validate(snapshot),
    )
    assert activity.id_ == body["id"]
    note = cast(
        as_Note,
        find_in_vocabulary(snapshot["object"]["type"]).model_validate(
            snapshot["object"]
        ),
    )
    assert note.id_ == body["object"]["id"]


@pytest.mark.spec("CLP-07-011")
@pytest.mark.spec("VM-08-002")
@pytest.mark.spec("VM-08-003")
def test_a_replica_records_the_received_artifact_not_the_routing_copy():
    """A replica's copy of the entry is A, as the sender sent it (#2656 AC-5).

    The routing copy (B) the CASE_MANAGER ran on holds the receiver's stored
    case in ``target`` and drops the key the parser set aside; neither reaches
    the entry, so neither reaches the replica.
    """
    net = LedgerNetwork(CASE_ID)
    body = _add_note_body(
        "https://example.org/notes/verbatim-4",
        exampleExtension="set aside at parse",
    )

    routed = _deliver(net, body)
    assert net.replay_ledger(BYSTANDER)[-1] == "add_note_to_case"

    replica_snapshot = _note_entry(net, BYSTANDER).payload_snapshot
    assert replica_snapshot == body
    assert replica_snapshot == _note_entry(net, MANAGER).payload_snapshot
    assert not isinstance(routed.target, str), "precondition: B is hydrated"
    assert not hasattr(routed, "exampleExtension"), "precondition: set aside"
    assert cast(dict[str, Any], replica_snapshot)["target"] == CASE_ID
