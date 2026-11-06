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
"""A redelivered ``Join(VulnerabilityCase)`` changes nothing (ID-02-003, #5006).

The CASE_MANAGER answers an engage by recording the sender's RM move to
``ACCEPTED`` and announcing the case to every eligible participant.  A second
delivery of the same ``Join`` has no move left to record, so it has nothing to
announce either: the store and the outbox stand as the first delivery left
them and the handler reports ``SKIPPED``.  Duplicate detection by activity id
runs ahead of dispatch but does not replace the handler's own check, which is
what keeps the redelivery from producing a second side effect (ID-02-003,
ID-05-003, HP-01-014).

The sweep in ``test/adapters/driving/fastapi/test_inbox_redelivery.py`` cannot
see this: its examples run against a store that holds no case, so the engage
tree is refused before it reaches its CASE_MANAGER effects.  These tests run
against a case-holding CASE_MANAGER store instead.
"""

import copy
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.ledger_rebuild import run_use_case
from test.support.received import delivered_body
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driving.fastapi.inbox_handler import prepare_for_dispatch
from vultron.adapters.driving.fastapi.inbox_orchestration import (
    FastAPIIngressAdapter,
)
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus

from ._ledger_network import BYSTANDER, MANAGER, LedgerNetwork

CASE_ID = "https://example.org/cases/case-engage-redelivery"


def _engage_body(net: LedgerNetwork, sender: str) -> dict[str, Any]:
    """The body *sender*'s outbox delivers for its ``Join`` of the case."""
    return delivered_body(
        rm_engage_case_activity(net.case(MANAGER), actor=sender, to=[MANAGER]),
        at=net.stores[MANAGER],
    )


def _declare_accepted_body(net: LedgerNetwork, sender: str) -> dict[str, Any]:
    """The body *sender* delivers to declare ``RM.ACCEPTED`` on the case.

    The ``Add(ParticipantStatus)`` arm of the same move the ``Join`` makes:
    one move, declared two ways (RSH-08-002, ADR-0108).
    """
    record = net.record(MANAGER, sender)
    return delivered_body(
        add_status_to_participant_activity(
            status=as_ParticipantStatus(
                id_=f"{record.id_}/statuses/declared-accepted",
                context=CASE_ID,
                attributed_to=sender,
                rm=RmDimension(state=RM.ACCEPTED),
            ),
            target=as_CaseParticipant(
                id_=record.id_, context=CASE_ID, attributed_to=sender
            ),
            actor=sender,
            to=[MANAGER],
            context=CASE_ID,
        ),
        at=net.stores[MANAGER],
    )


def _deliver(net: LedgerNetwork, body: dict[str, Any]) -> HandlerResult:
    """Route *body* to the CASE_MANAGER through the inbox's own parse edge.

    Every delivery is parsed and rehydrated again, so the second one is
    routed as the inbox routes a redelivery: against the archived copy of
    the first (IE-10-001).
    """
    dl = net.stores[MANAGER]
    ingress = FastAPIIngressAdapter(dl)
    artifact = ingress.parse(copy.deepcopy(body))
    assert artifact is not None
    event = prepare_for_dispatch(ingress.rehydrate(artifact)).model_copy(
        update={"receiving_actor_id": MANAGER}
    )
    return cast(HandlerResult, run_use_case(dl, event))


def _snapshot(dl: SqliteDataLayer) -> dict[str, Any]:
    """The store's object ids and its outbox, as compared across deliveries."""
    return {
        "object_ids": frozenset(cast(dict[str, Any], dl.all())),
        "outbox": tuple(dl.outbox_list()),
    }


def _case_announces(net: LedgerNetwork) -> list[dict[str, Any]]:
    """The ``Announce(VulnerabilityCase)`` bodies queued for the bystander.

    The ledger fan-out announces every committed entry too (SYNC-02-003);
    only the case broadcast is counted here.
    """
    return net.sealed_bodies(
        MANAGER,
        to=BYSTANDER,
        type_="Announce",
        object_type="VulnerabilityCase",
    )


@pytest.mark.spec("ID-02-003")
@pytest.mark.spec("ID-05-003")
@pytest.mark.spec("HP-01-003")
def test_a_redelivered_engage_queues_no_second_case_announce():
    """The second ``Join`` adds no outbox item and no object (#5006 AC-1).

    The first delivery records the sender's ``ACCEPTED`` and announces the
    case; the second finds that state already recorded, so the whole act is
    a no-op and the CASE_MANAGER announces nothing again.
    """
    net = LedgerNetwork(CASE_ID)
    dl = net.stores[MANAGER]
    body = _engage_body(net, BYSTANDER)

    first = _deliver(net, body)
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    after_first = _snapshot(dl)
    entries_after_first = [e.id_ for e in ledger_entries(dl, CASE_ID)]
    # Preconditions: the first delivery did reach the CASE_MANAGER's effects.
    status = net.record(MANAGER, BYSTANDER).participant_status
    assert status is not None and status.rm.state is RM.ACCEPTED
    assert _case_announces(net), "precondition: the first delivery announced"

    second = _deliver(net, body)
    after_second = _snapshot(dl)

    assert after_second["outbox"] == after_first["outbox"], (
        "the redelivered Join queued another activity: "
        f"{set(after_second['outbox']) - set(after_first['outbox'])}"
    )
    assert after_second["object_ids"] == after_first["object_ids"], (
        "the redelivered Join stored new objects: "
        f"{after_second['object_ids'] - after_first['object_ids']}"
    )
    assert [e.id_ for e in ledger_entries(dl, CASE_ID)] == entries_after_first
    # AC-1 admits either reading of a repeat that changes nothing: the
    # disposition the first delivery reported, or ``SKIPPED``.  The behaviour
    # pinned here is that it is one of the two and never a refusal or a fault,
    # so the generic repeat door planned in #5045 may pick either.
    assert second.disposition in (
        HandlerDisposition.SKIPPED,
        first.disposition,
    ), second.reason


@pytest.mark.spec("ID-05-003")
@pytest.mark.spec("HP-01-003")
def test_a_restated_engage_under_a_fresh_id_announces_nothing_again():
    """A restated ``Join`` is judged on its effect, not on its id (ID-05-003).

    Duplicate detection and the outbox both recognize a repeat by its
    activity id, so a sender that restates its ``Join`` under a new id gets
    past them and only the handler's domain-state check can stop a second
    apply (ID-01-002, ID-05-003).  The guard reads the sender's recorded RM
    state, so the restatement records nothing and announces nothing, and the
    handler reports it as ``SKIPPED``.

    The receipt is a new activity, so it earns its own ledger entry and the
    fan-out announces that entry; only the case broadcast is counted here.
    """
    net = LedgerNetwork(CASE_ID)
    body = _engage_body(net, BYSTANDER)
    first = _deliver(net, body)
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    announces_after_first = len(_case_announces(net))
    assert announces_after_first, "precondition: the first delivery announced"

    restated = _engage_body(net, BYSTANDER)
    assert restated["id"] != body["id"], (
        "precondition: the restatement carries its own activity id"
    )

    second = _deliver(net, restated)

    assert second.disposition is HandlerDisposition.SKIPPED, second.reason
    assert len(_case_announces(net)) == announces_after_first, (
        "the restated Join queued another Announce(VulnerabilityCase)"
    )


@pytest.mark.spec("RSH-08-002")
@pytest.mark.spec("ID-05-003")
def test_an_engage_confirming_an_already_declared_move_announces_nothing():
    """One move declared twice announces once (RSH-08-002).

    An act and a status declaration for the same move both arrive, in either
    order, and the receiver treats the second as a same-state confirmation.
    When the ``Add(ParticipantStatus)`` lands first, the ``Join`` that follows
    has no move left to record, so the CASE_MANAGER has no case change to
    announce: the receipt is committed and the handler reports ``SKIPPED``.

    The participants still learn the move.  Every change the CASE_MANAGER
    makes to the case file is its own ledger entry and the fan-out carries it
    as ``Announce(CaseLedgerEntry)`` (CM-06-001, CLP-07-013, SYNC-02-003);
    the full-case copy is what the restatement does not repeat.
    """
    net = LedgerNetwork(CASE_ID)
    _deliver(net, _declare_accepted_body(net, BYSTANDER))
    # The precondition is the recorded state, not the declaration's own
    # disposition: the adoption gate it answers is a separate rule
    # (RSH-01-002) whose conservative default is expected to change
    # (RSH-07-004), and this test must not pin it.
    status = net.record(MANAGER, BYSTANDER).participant_status
    assert status is not None and status.rm.state is RM.ACCEPTED, (
        "precondition: the declaration recorded the sender's ACCEPTED"
    )
    announces_after_declaration = len(_case_announces(net))

    engaged = _deliver(net, _engage_body(net, BYSTANDER))

    assert engaged.disposition is HandlerDisposition.SKIPPED, engaged.reason
    assert len(_case_announces(net)) == announces_after_declaration, (
        "the confirming Join queued an Announce(VulnerabilityCase)"
    )
