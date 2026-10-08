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
"""A replica converges from the ledger alone (#3814 AC-6, convergence half).

Each actor has its own store (TB-06-007).  A participant sends an act to the
CASE_MANAGER; the replica under test never receives that act, only the
CASE_MANAGER's ``Announce(CaseLedgerEntry)`` broadcast, and still reaches the
CASE_MANAGER's state (RSH-08-004, PCR-03-001, ADR-0108).  The replica is
handed the ledger broadcast and nothing else the CASE_MANAGER sends — not the
``Announce(VulnerabilityCase)`` an engage also triggers — so the state it
reaches can only have come from the ledger.

The other half of AC-6 — that a replica receiving the act *directly* writes
nothing before the fan-out — lands with the gating change (RSH-08-003, #3814)
and is exercised below by ``test_*_writes_nothing_at_a_replica``: the activity
is delivered straight to a replica's store, which must change no state because
the state-writing effect now runs only inside the CASE_MANAGER gate.  Every
activity-typed RM move replays through one slot, keyed by ``RM_VERDICT_TARGETS``;
engage and defer exercise it end to end, and ``test_rm_verdict_effect.py`` pins
each other type's target state against its use case.
"""

import json
from typing import Any, cast

import pytest

from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import (
    EmDimension,
    PxaDimension,
    RmDimension,
)
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    add_embargo_to_case_activity,
    add_status_to_case_activity,
    remove_embargo_from_case_activity,
    rm_defer_case_activity,
    rm_engage_case_activity,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork


def _send(net: LedgerNetwork, activity: Any) -> None:
    """Deliver *activity* to the CASE_MANAGER, as its sender's outbox would."""
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(activity)))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _replay(net: LedgerNetwork, replica: str) -> list[str]:
    """Hand *replica* the CASE_MANAGER's ledger broadcast, and only that.

    Returns the event types delivered, in chain order.
    """
    event_types = []
    for activity in net.queued(MANAGER, to=replica, type_="Announce"):
        body = read_sealed_body_dict(net.stores[MANAGER], activity.id_) or {}
        entry = body.get("object") or {}
        if entry.get("type") != "CaseLedgerEntry":
            continue
        verdict = net.receive(replica, body)
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            entry.get("eventType"),
            verdict.reason,
        )
        event_types.append(entry["eventType"])
    return event_types


def _ledger(net: LedgerNetwork, actor_id: str) -> list[str]:
    """The ``event_type`` of each entry *actor_id*'s store holds, in order."""
    entries = [
        cast(CaseLedgerEntry, e)
        for e in net.stores[actor_id].list_objects("CaseLedgerEntry")
        if getattr(e, "case_id", None) == net.case_id
    ]
    return [e.event_type for e in sorted(entries, key=lambda e: e.log_index)]


def _embargo(net: LedgerNetwork) -> as_EmbargoEvent:
    embargo = net.stores[OWNER].read(net.initial_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    return embargo


def _owned(net: LedgerNetwork) -> LedgerNetwork:
    """Give OWNER the CASE_OWNER role in every store (EP-09-005, ADR-0115)."""
    for dl in net.stores.values():
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        participant = cast(
            CaseParticipant, dl.read(case.actor_participant_index[OWNER])
        )
        participant.add_role(CVDRole.CASE_OWNER)
        dl.save(participant)
    return net


def _rm(net: LedgerNetwork, store_of: str, member: str) -> RM:
    participant = net.stores[store_of].read(
        net.case(store_of).actor_participant_index[member]
    )
    assert isinstance(participant, CaseParticipant)
    status = participant.participant_status
    assert status is not None
    return status.rm.state


def _set_rm(net: LedgerNetwork, member: str, rm: RM) -> None:
    """Record *member* at *rm* in every store, as the ledger already had it."""
    for dl in net.stores.values():
        case = cast(VulnerabilityCase, dl.read(net.case_id))
        participant = cast(
            CaseParticipant, dl.read(case.actor_participant_index[member])
        )
        participant.add_participant_status(
            ParticipantStatus(
                context=net.case_id,
                attributed_to=member,
                rm=RmDimension(state=rm),
            )
        )
        dl.save(participant)


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("EMB-18-001")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_owners_embargo_activation():
    """Add(EmbargoEvent): PROPOSED → ACTIVE in the manager's store and the bystander's."""
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/replay-activation", em_state=EM.PROPOSED
        )
    )
    _send(
        net,
        add_embargo_to_case_activity(
            _embargo(net), target=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "add_embargo_event_to_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.ACTIVE, actor_id
        assert case.active_embargo_id == net.initial_embargo_id, actor_id
    assert _ledger(net, BYSTANDER) == _ledger(net, MANAGER)


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_the_owners_embargo_removal():
    """Remove(EmbargoEvent): ACTIVE → EXITED in both stores."""
    net = _owned(LedgerNetwork("https://example.org/cases/replay-removal"))
    _send(
        net,
        remove_embargo_from_case_activity(
            _embargo(net), origin=net.case_id, actor=OWNER, to=[MANAGER]
        ),
    )

    assert "remove_embargo_event_from_case" in _replay(net, BYSTANDER)
    for actor_id in (MANAGER, BYSTANDER):
        case = net.case(actor_id)
        assert case.current_status.em.state == EM.EXITED, actor_id
        assert case.active_embargo_id is None, actor_id


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("RSH-05-019")
@pytest.mark.spec("TB-06-007")
def test_a_replica_follows_a_participants_case_status():
    """Add(CaseStatus) from the bystander reaches the owner's replica as P set."""
    net = LedgerNetwork(
        "https://example.org/cases/replay-case-status", em_state=EM.NONE
    )
    status = CaseStatus(
        context=net.case_id,
        attributed_to=BYSTANDER,
        em=EmDimension(state=EM.NONE),
        pxa=PxaDimension(state=CS_pxa.Pxa),
    )
    _send(
        net,
        add_status_to_case_activity(
            status, target=net.case_id, actor=BYSTANDER, to=[MANAGER]
        ),
    )

    assert "add_case_status_to_case" in _replay(net, OWNER)
    manager, replica = net.case(MANAGER), net.case(OWNER)
    assert replica.current_status.id_ == manager.current_status.id_
    assert replica.current_status.pxa.state == CS_pxa.Pxa
    assert replica.current_status.em.state == manager.current_status.em.state
    assert [_as_id(s) for s in replica.case_statuses] == [
        _as_id(s) for s in manager.case_statuses
    ]


@pytest.mark.spec("RSH-08-004")
@pytest.mark.spec("RSH-08-001")
@pytest.mark.spec("TB-06-007")
@pytest.mark.parametrize(
    ("factory", "event_type", "target"),
    [
        (rm_engage_case_activity, "engage_case", RM.ACCEPTED),
        (rm_defer_case_activity, "defer_case", RM.DEFERRED),
    ],
    ids=["engage", "defer"],
)
def test_a_replica_follows_a_participants_engagement_decision(
    factory, event_type, target
):
    """Join/Ignore(Case) from the bystander moves its RM on the owner's replica."""
    net = LedgerNetwork(
        f"https://example.org/cases/replay-{event_type}", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.VALID)
    owner_before = {s: _rm(net, s, OWNER) for s in (MANAGER, OWNER)}
    _send(net, factory(net.case(BYSTANDER), actor=BYSTANDER, to=[MANAGER]))

    assert event_type in _replay(net, OWNER)
    for store_of in (MANAGER, OWNER):
        # The sender is the subject (RSH-08-001) in every store: the
        # replica's own participant does not move.
        assert _rm(net, store_of, BYSTANDER) == target, store_of
        assert _rm(net, store_of, OWNER) == owner_before[store_of], store_of


# ---------------------------------------------------------------------------
# AC-6, "writes nothing" half (RSH-08-003, #3814): an activity delivered
# straight to a replica — not the CASE_MANAGER — changes no participant or
# case state.  The replica archives it and takes the move from the ledger.
# ---------------------------------------------------------------------------
def _deliver_direct(
    net: LedgerNetwork, replica: str, activity: object
) -> None:
    """Deliver *activity* straight into *replica*'s store (never the manager)."""
    net.receive(replica, json.loads(dump_outbound_body(activity)))


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("TB-06-007")
def test_embargo_activation_writes_nothing_at_a_replica():
    """Add(EmbargoEvent) delivered straight to a replica leaves EM untouched."""
    net = _owned(
        LedgerNetwork(
            "https://example.org/cases/writes-nothing-activation",
            em_state=EM.PROPOSED,
        )
    )
    before = net.case(BYSTANDER).current_status.em.state
    _deliver_direct(
        net,
        BYSTANDER,
        add_embargo_to_case_activity(
            _embargo(net), target=net.case_id, actor=MANAGER, to=[BYSTANDER]
        ),
    )

    case = net.case(BYSTANDER)
    assert case.current_status.em.state == before
    assert case.active_embargo_id is None


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("CM-31-010")
@pytest.mark.spec("TB-06-007")
def test_embargo_removal_writes_nothing_at_an_active_replica():
    """Remove(EmbargoEvent) delivered straight to an active (non-paused) replica
    leaves the embargo in force: it is not awaiting an ending notice, so it
    takes the teardown from the ledger (CM-31-010)."""
    net = _owned(
        LedgerNetwork("https://example.org/cases/writes-nothing-removal")
    )
    before = net.case(BYSTANDER).current_status.em.state
    assert before == EM.ACTIVE
    _deliver_direct(
        net,
        BYSTANDER,
        remove_embargo_from_case_activity(
            _embargo(net), origin=net.case_id, actor=MANAGER, to=[BYSTANDER]
        ),
    )

    case = net.case(BYSTANDER)
    assert case.current_status.em.state == EM.ACTIVE
    assert case.active_embargo_id == net.initial_embargo_id


@pytest.mark.spec("RSH-08-003")
@pytest.mark.spec("RSH-05-019")
@pytest.mark.spec("TB-06-007")
def test_case_status_writes_nothing_at_a_replica():
    """Add(CaseStatus) delivered straight to a replica appends no status."""
    net = LedgerNetwork(
        "https://example.org/cases/writes-nothing-case-status",
        em_state=EM.NONE,
    )
    before = [_as_id(s) for s in net.case(OWNER).case_statuses]
    status = CaseStatus(
        context=net.case_id,
        attributed_to=BYSTANDER,
        em=EmDimension(state=EM.NONE),
        pxa=PxaDimension(state=CS_pxa.Pxa),
    )
    _deliver_direct(
        net,
        OWNER,
        add_status_to_case_activity(
            status, target=net.case_id, actor=BYSTANDER, to=[OWNER]
        ),
    )

    assert [_as_id(s) for s in net.case(OWNER).case_statuses] == before


# The report-verdict "writes nothing at a replica" half of AC-6
# (TentativeReject / Reject(Offer(Report))) is exercised in
# ``test/core/behaviors/report/test_received_report_trees.py`` (a
# non-CASE_MANAGER receiver archives the activity but the RM write is gated
# out), with the manager-path transition and sender-as-subject covered by
# ``test_report_routing_guard.py`` and ``test_receive_tree_ledger_commit.py``;
# #4304 made those verdicts committed and replayed, so gating them is safe
# (RSH-08-003).
