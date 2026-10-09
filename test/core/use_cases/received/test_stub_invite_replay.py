#!/usr/bin/env python
"""Replicas store the participant record the ledger's entries carry.

Each actor has its own store (TB-06-007).  The ledger holds the wire messages
exchanged (ADR-0114): sending the stub Invite commits the Invite and, separately,
``create_case_participant`` for the inert record the CASE_MANAGER created; the invitee's own ``Accept`` and ``Reject`` messages are the entries for
their effects (consent, ``joined``, ``DECLINED``), and a vendor's VF ``Vf`` and the
reject's closing status are ``add_participant_status_to_participant`` entries.  A
replica that never sees the Invite or the reply directly stores what those
entries carry, as received, and equals the CASE_MANAGER's whole record at the
same ledger position (CM-11-006, CM-31-012, RSH-08-004).
"""

import json
from typing import Any, cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_vf
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.states.rm import RM
from vultron.core.use_cases.triggers.actor import SvcInviteActorToCaseUseCase
from vultron.core.use_cases.triggers.requests import (
    InviteActorToCaseTriggerRequest,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

from ._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork

JOINER = "https://example.org/users/vendor-new"


def _record(net: LedgerNetwork, holder: str) -> CaseParticipant:
    case = net.case(holder)
    record_id = case.actor_participant_index[JOINER]
    record = net.stores[holder].read(record_id)
    assert isinstance(record, CaseParticipant), (holder, record_id)
    return record


def _view(net: LedgerNetwork, holder: str) -> dict[str, Any]:
    """The WHOLE of the joiner's record and the roster, as one store holds them.

    Not a subset: every field, including each status's id and times, the
    consent rows and the record's own times.  Two stores at the same ledger
    position must agree on all of it (ADR-0124).
    """
    return {
        "record": _record(net, holder).model_dump(mode="json"),
        "roster": sorted(net.case(holder).actor_participant_index),
        "members": sorted(
            str(getattr(p, "id_", p))
            for p in net.case(holder).case_participants
        ),
    }


def _the_owner_invites_the_joiner(
    net: LedgerNetwork, roles: list[CVDRole] | None = None
) -> None:
    """The owner's Offer(Actor, Case) makes the CASE_MANAGER send the stub."""
    owner_dl = net.stores[OWNER]
    for store in (net.stores[MANAGER], owner_dl):
        case = cast(VulnerabilityCase, store.read(net.case_id))
        owner_record = store.read(case.actor_participant_index[OWNER])
        assert isinstance(owner_record, CaseParticipant)
        owner_record.add_role(CVDRole.CASE_OWNER)
        store.save(owner_record)
    manager_case = net.case(MANAGER)
    manager_case.stub_summary = "Details shared after acceptance"
    net.stores[MANAGER].save(manager_case)
    owner_dl.save(as_Actor(id_=OWNER))
    owner_dl.save(as_Actor(id_=MANAGER))
    before = set(owner_dl.outbox_list())
    SvcInviteActorToCaseUseCase(
        owner_dl,
        InviteActorToCaseTriggerRequest(
            actor_id=OWNER,
            case_id=net.case_id,
            invitee_id=JOINER,
            roles=roles or [CVDRole.VENDOR],
        ),
        trigger_activity=TriggerActivityAdapter(owner_dl),
        sync_port=SyncActivityAdapter(owner_dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
    new = [i for i in owner_dl.outbox_list() if i not in before]
    assert new, "the owner queued nothing"
    for item in new:
        body = read_sealed_body_dict(owner_dl, item)
        assert body is not None
        verdict = net.receive(MANAGER, body)
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            verdict.reason
        )


def _deliver_announcements(net: LedgerNetwork, to: str) -> None:
    for type_, verdict in net.deliver(MANAGER, to=to, type_="Announce"):
        assert verdict.disposition is HandlerDisposition.APPLIED, (
            type_,
            verdict.reason,
        )


def _the_joiner_accepts(net: LedgerNetwork) -> None:
    joiner_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=JOINER)
    net.stores[JOINER] = joiner_dl
    delivered = net.deliver(MANAGER, to=JOINER, type_="Invite")
    assert delivered, "the CASE_MANAGER sent the joiner no stub Invite"
    (invite,) = net.queued(MANAGER, to=JOINER, type_="Invite")
    _, sealed = TriggerActivityAdapter(joiner_dl).accept_case_invite(
        invite_id=invite.id_, actor=JOINER
    )
    verdict = net.receive(MANAGER, json.loads(sealed))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


#: (roles the owner names, the case's EM state).  An embargo in force gives the
#: joiner a consent row; a case with no embargo in force gives none.  A vendor
#: carries VF; no other role does.
SCENARIOS = [
    pytest.param([CVDRole.VENDOR], EM.ACTIVE, id="vendor-embargo"),
    pytest.param([CVDRole.COORDINATOR], EM.ACTIVE, id="coordinator-embargo"),
    pytest.param([CVDRole.VENDOR], EM.NONE, id="vendor-no-embargo"),
    pytest.param([CVDRole.COORDINATOR], EM.NONE, id="coordinator-no-embargo"),
    pytest.param(
        [CVDRole.VENDOR, CVDRole.COORDINATOR],
        EM.ACTIVE,
        id="vendor-and-coordinator-embargo",
    ),
]


def _net(em_state: EM) -> LedgerNetwork:
    return LedgerNetwork(
        "https://example.org/cases/stub-invite-replay", em_state=em_state
    )


@pytest.fixture
def net() -> LedgerNetwork:
    return _net(EM.ACTIVE)


@pytest.mark.spec("CM-11-006")
@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("SYNC-02-002")
def test_the_stub_invite_entry_fans_out_and_gives_a_replica_the_inert_record(
    net: LedgerNetwork,
) -> None:
    """The creation entry reaches another replica, which stores the record.

    Verifies that ``emit_stub_invite``'s commit is fanned out to the case's
    active participants even though it passes no ``sync_port`` of its own.
    """
    _the_owner_invites_the_joiner(net)
    announced = net.queued(MANAGER, to=BYSTANDER, type_="Announce")
    entry_types = [
        (read_sealed_body_dict(net.stores[MANAGER], a.id_) or {})
        .get("object", {})
        .get("eventType")
        for a in announced
    ]
    assert "invite_actor_to_case" in entry_types, entry_types

    _deliver_announcements(net, BYSTANDER)

    replica = _record(net, BYSTANDER)
    assert replica.joined is False
    assert replica.case_roles == [CVDRole.VENDOR]
    status = replica.participant_statuses[-1]
    assert status.rm.state == RM.RECEIVED
    assert status.vf is not None
    assert status.vf.state == CS_vf.vf
    assert _view(net, BYSTANDER) == _view(net, MANAGER)


@pytest.mark.spec("CM-11-006")
@pytest.mark.spec("CM-31-012")
@pytest.mark.parametrize(("roles", "em_state"), SCENARIOS)
def test_replicas_hold_the_managers_whole_record_after_invite_and_accept(
    roles: list[CVDRole], em_state: EM
) -> None:
    """At each ledger position every replica equals the CASE_MANAGER, in full.

    The owner and the bystander never receive the Invite or the Accept
    directly.  After the Invite entry and again after the Accept entry, each
    holds a record equal to the CASE_MANAGER's in every field: ids, times,
    VF, consent rows, ``joined`` (AC-5, ADR-0124).
    """
    net = _net(em_state)
    _the_owner_invites_the_joiner(net, roles)
    for replica in (OWNER, BYSTANDER):
        _deliver_announcements(net, replica)
        assert _record(net, replica).joined is False, replica
        assert _view(net, replica) == _view(net, MANAGER), replica

    _the_joiner_accepts(net)
    manager = _record(net, MANAGER)
    assert manager.joined is True
    for replica in (OWNER, BYSTANDER):
        _deliver_announcements(net, replica)
        assert _view(net, replica) == _view(net, MANAGER), replica

    # What the Accept did, so the equality above is not two blanks.
    vfs = [s.vf.state for s in manager.participant_statuses if s.vf]
    if CVDRole.VENDOR in roles:
        assert vfs == [CS_vf.vf, CS_vf.Vf]
    else:
        assert vfs == []
    if em_state is EM.ACTIVE:
        rows = {c.embargo_id: c.state for c in manager.embargo_consents}
        assert rows == {net.initial_embargo_id: EmbargoConsentState.AGREED}
    else:
        assert manager.embargo_consents == []


@pytest.mark.spec("CM-31-012")
@pytest.mark.spec("SYNC-12-003")
def test_replaying_the_whole_stream_leaves_one_record(
    net: LedgerNetwork,
) -> None:
    """A replay of every delivered Announce changes nothing (AC-4)."""
    _the_owner_invites_the_joiner(net)
    _the_joiner_accepts(net)
    _deliver_announcements(net, BYSTANDER)
    before = _view(net, BYSTANDER)
    assert before["record"]["joined"] is True
    assert before == _view(net, MANAGER)

    for activity in net.queued(MANAGER, to=BYSTANDER, type_="Announce"):
        body = read_sealed_body_dict(net.stores[MANAGER], activity.id_)
        assert body is not None
        verdict = net.receive(BYSTANDER, body)
        assert verdict.disposition in (
            HandlerDisposition.APPLIED,
            HandlerDisposition.SKIPPED,
        ), verdict.reason

    assert _view(net, BYSTANDER) == before


def _the_joiner_rejects(net: LedgerNetwork) -> None:
    joiner_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=JOINER)
    net.stores[JOINER] = joiner_dl
    delivered = net.deliver(MANAGER, to=JOINER, type_="Invite")
    assert delivered, "the CASE_MANAGER sent the joiner no stub Invite"
    (invite,) = net.queued(MANAGER, to=JOINER, type_="Invite")
    _, sealed = TriggerActivityAdapter(joiner_dl).reject_case_invite(
        invite_id=invite.id_, actor=JOINER
    )
    verdict = net.receive(MANAGER, json.loads(sealed))
    assert verdict.disposition is HandlerDisposition.APPLIED, verdict.reason


def _entry_types(net: LedgerNetwork) -> list[str]:
    entries = [
        e
        for e in net.stores[MANAGER].list_objects("CaseLedgerEntry")
        if isinstance(e, CaseLedgerEntry) and e.case_id == net.case_id
    ]
    return [
        str(e.event_type) for e in sorted(entries, key=lambda e: e.log_index)
    ]


@pytest.mark.spec("CM-11-006")
@pytest.mark.spec("CM-31-012")
def test_the_ledger_holds_the_messages_and_the_one_creation_entry() -> None:
    """The Invite, the CASE_MANAGER's creation, the Accept, and a vendor's VF.

    The ledger holds the wire messages exchanged: the invitee's Accept is the
    entry for its consent and ``joined``, so no entry of the CASE_MANAGER's own
    repeats it.  Creating the record is the CASE_MANAGER's act and has its own
    entry; the vendor's VF status is its own object and entry.
    """
    net = _net(EM.ACTIVE)
    before = len(_entry_types(net))
    _the_owner_invites_the_joiner(net)
    _the_joiner_accepts(net)

    new = _entry_types(net)[before:]
    assert new[:4] == [
        "offer_actor_to_case",
        "invite_actor_to_case",
        "create_case_participant",
        "accept_invite_actor_to_case",
    ], new
    assert new[4:5] == ["add_participant_status_to_participant"], new
    assert "update_case_participant" not in new


@pytest.mark.spec("CM-11-007")
@pytest.mark.parametrize(("roles", "em_state"), SCENARIOS)
def test_replicas_hold_the_managers_whole_record_after_a_reject(
    roles: list[CVDRole], em_state: EM
) -> None:
    """The reject's closing status and DECLINED row reach every replica whole."""
    net = _net(em_state)
    _the_owner_invites_the_joiner(net, roles)
    _the_joiner_rejects(net)

    manager = _record(net, MANAGER)
    assert manager.rm_closed
    for replica in (OWNER, BYSTANDER):
        _deliver_announcements(net, replica)
        assert _view(net, replica) == _view(net, MANAGER), replica
    if em_state is EM.ACTIVE:
        rows = {c.embargo_id: c.state for c in manager.embargo_consents}
        assert rows == {net.initial_embargo_id: EmbargoConsentState.DECLINED}
