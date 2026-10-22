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

"""A replica whose chain is short is replaced by a fresh case copy, then
backfilled to the CASE_MANAGER's tail (SYNC-16-006, SYNC-16-007, ADR-0142).

Every activity moves between stores only as the sealed body the sender's
outbox would deliver (:class:`LedgerNetwork`).
"""

import json
import logging
from typing import Any, cast

import pytest

from test.support.ledger import ledger_entries
from test.support.received import received_event
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.events.sync import RejectLogEntryReceivedEvent
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.wire.as2.factories import genesis_replay_reject_activity
from vultron.wire.as2.parser import parse_activity

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

_REFLECTED = "storing it as a no-op"


def _send(net: LedgerNetwork, activity: Any) -> None:
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(activity)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _case_copy(net: LedgerNetwork) -> dict[str, Any]:
    """The CASE_MANAGER's full-case announcement to the bystander, sealed."""
    activity_id = TriggerActivityAdapter(
        net.stores[MANAGER]
    ).announce_vulnerability_case(
        case_id=net.case_id,
        actor=MANAGER,
        context_id=net.case_id,
        to=[BYSTANDER],
    )
    body = read_sealed_body_dict(net.stores[MANAGER], activity_id)
    assert body is not None
    return cast(dict[str, Any], body)


def _deliver_entries(net: LedgerNetwork, replica: str) -> None:
    """Deliver every queued ``Announce(CaseLedgerEntry)`` once, in order.

    A replay resends entries the fan-out already queued, so a repeat is
    stored once and answered as a repeat; nothing is refused.
    """
    for _type, verdict in net.deliver(MANAGER, to=replica, type_="Announce"):
        assert verdict.disposition in {
            HandlerDisposition.APPLIED,
            HandlerDisposition.SKIPPED,
        }, verdict.reason


def _tail(net: LedgerNetwork, actor_id: str) -> tuple[int, str]:
    last = ledger_entries(net.stores[actor_id], net.case_id)[-1]
    return last.log_index, last.entry_hash


def _statuses(net: LedgerNetwork, holder: str) -> list[str]:
    case = net.case(holder)
    participant = cast(
        CaseParticipant,
        net.stores[holder].read(case.actor_participant_index[OWNER]),
    )
    return [str(_as_id(s)) for s in participant.participant_statuses]


def _short_replica(net: LedgerNetwork) -> None:
    """The bystander takes the first report's entries; the second's are still
    in flight, so its chain stops short of the CASE_MANAGER's."""
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    _deliver_entries(net, BYSTANDER)
    _send(net, net.pxa_report(OWNER, CS_pxa.pXA))
    assert _tail(net, BYSTANDER) < _tail(net, MANAGER)


@pytest.mark.spec("SYNC-16-006")
@pytest.mark.spec("SYNC-16-007")
@pytest.mark.spec("CM-23-016")
def test_a_short_replica_is_replaced_then_backfilled_to_the_tail(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Replace, ask for the rest, store each reflected entry as a no-op.

    The copy names the CASE_MANAGER's tail, ahead of the replica's chain.
    The replica replaces its case with it and sends ``Reject(CaseLedgerEntry)``
    naming its own tail; the CASE_MANAGER answers it, and each entry the copy
    reflects, whether in flight or replayed, is stored without its effects.
    The replica ends where seed-plus-replay leaves it: the CASE_MANAGER's tail
    and case file.
    """
    net = LedgerNetwork("https://example.org/cases/copy-backfill")
    _short_replica(net)
    replica_tail = _tail(net, BYSTANDER)

    verdict = net.receive(BYSTANDER, _case_copy(net))

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    assert net.case(BYSTANDER).current_status.id_ == (
        net.case(MANAGER).current_status.id_
    )
    manager_at = LedgerPosition(
        log_index=_tail(net, MANAGER)[0], entry_hash=_tail(net, MANAGER)[1]
    )
    assert net.case(BYSTANDER).ledger_position == manager_at
    rejects = [
        read_sealed_body_dict(net.stores[BYSTANDER], a.id_)
        for a in net.queued(BYSTANDER, to=MANAGER, type_="Reject")
    ]
    assert [r["context"] for r in rejects if r] == [replica_tail[1]]

    for _type, answered in net.deliver(BYSTANDER, to=MANAGER, type_="Reject"):
        assert answered.disposition is HandlerDisposition.APPLIED
    with caplog.at_level(logging.INFO):
        _deliver_entries(net, BYSTANDER)

    assert _tail(net, BYSTANDER) == _tail(net, MANAGER)
    # The replayed entries the copy reflects never moved the case back.
    assert net.case(BYSTANDER).ledger_position == manager_at
    assert _statuses(net, BYSTANDER) == _statuses(net, MANAGER)
    assert [_as_id(s) for s in net.case(BYSTANDER).case_statuses] == [
        _as_id(s) for s in net.case(MANAGER).case_statuses
    ]
    assert any(_REFLECTED in r.getMessage() for r in caplog.records)


@pytest.mark.spec("SYNC-16-006")
def test_a_late_copy_from_before_the_replicas_tail_changes_nothing() -> None:
    """A copy taken before entries the replica now holds arrives late:
    ``SKIPPED``, the case file as it was (HP-01-003)."""
    net = LedgerNetwork("https://example.org/cases/copy-late")
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    late = _case_copy(net)
    _send(net, net.pxa_report(OWNER, CS_pxa.pXA))
    _deliver_entries(net, BYSTANDER)
    before = net.case(BYSTANDER).model_dump(mode="json")

    verdict = net.receive(BYSTANDER, late)

    assert verdict.disposition is HandlerDisposition.SKIPPED, verdict.reason
    assert net.case(BYSTANDER).model_dump(mode="json") == before


@pytest.mark.spec("SYNC-16-007")
@pytest.mark.spec("SYNC-15-002")
def test_a_replica_with_no_entry_is_replayed_from_genesis() -> None:
    """A replica holding the case but no entry is replaced by a copy ahead
    of it, asks for a replay from genesis with the Reject that names no
    entry, and the CASE_MANAGER's genesis answer brings it to its tail."""
    net = LedgerNetwork("https://example.org/cases/copy-genesis")
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    # The fan-out left the outbox and was lost in transit.
    for activity in net.queued(MANAGER, to=BYSTANDER, type_="Announce"):
        net.stores[MANAGER].outbox_withdraw(activity.id_)
    assert ledger_entries(net.stores[BYSTANDER], net.case_id) == []

    verdict = net.receive(BYSTANDER, _case_copy(net))

    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason
    (reject,) = [
        read_sealed_body_dict(net.stores[BYSTANDER], a.id_)
        for a in net.queued(BYSTANDER, to=MANAGER, type_="Reject")
    ]
    assert reject is not None
    assert "object" not in reject
    assert reject["target"] == net.case_id

    for _type, answered in net.deliver(BYSTANDER, to=MANAGER, type_="Reject"):
        assert answered.disposition is HandlerDisposition.APPLIED, (
            answered.reason
        )
    _deliver_entries(net, BYSTANDER)

    assert _tail(net, BYSTANDER) == _tail(net, MANAGER)
    assert _statuses(net, BYSTANDER) == _statuses(net, MANAGER)


def _genesis_request(case_id: str, sender: str) -> dict[str, Any]:
    """The objectless genesis-replay Reject *sender* sends the CASE_MANAGER."""
    return genesis_replay_reject_activity(
        case_id, actor=sender, to=[MANAGER]
    ).model_dump(mode="json", by_alias=True, exclude_none=True)


@pytest.mark.spec("SYNC-16-007")
@pytest.mark.spec("SYNC-03-005")
def test_a_genesis_request_for_a_case_the_manager_lacks_is_refused() -> None:
    """The Reject's target is the only case it names; one the CASE_MANAGER
    does not hold has nothing to replay and is refused."""
    net = LedgerNetwork("https://example.org/cases/copy-genesis-unknown")
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    queued = len(net.queued(MANAGER, to=BYSTANDER))

    verdict = net.receive(
        MANAGER,
        _genesis_request("https://example.org/cases/not-held", BYSTANDER),
    )

    assert verdict.disposition is HandlerDisposition.REFUSED, verdict.reason
    assert len(net.queued(MANAGER, to=BYSTANDER)) == queued
    assert (
        list(net.stores[MANAGER].list_objects("VultronReplicationState")) == []
    )


@pytest.mark.spec("SYNC-16-007")
def test_a_reject_naming_neither_an_entry_nor_a_case_is_refused() -> None:
    """The parser admits no such Reject; one that reaches the use case all
    the same names nothing to replay, and is refused before any tree runs."""
    net = LedgerNetwork("https://example.org/cases/copy-genesis-nothing")
    _send(net, net.pxa_report(OWNER, CS_pxa.pXa))
    event = cast(
        RejectLogEntryReceivedEvent,
        received_event(
            parse_activity(_genesis_request(net.case_id, BYSTANDER)),
            receiving_actor_id=MANAGER,
        ),
    ).model_copy(update={"target": None})
    assert event.rejected_case_id is None
    queued = len(net.queued(MANAGER, to=BYSTANDER))

    verdict = net.receive_event(MANAGER, event)

    assert verdict.disposition is HandlerDisposition.REFUSED, verdict.reason
    assert "names neither" in (verdict.reason or "")
    assert len(net.queued(MANAGER, to=BYSTANDER)) == queued
