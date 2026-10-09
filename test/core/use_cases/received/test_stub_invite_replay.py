#!/usr/bin/env python
"""Replicas build the inert participant record from the stub Invite's entry.

Each actor has its own store (TB-06-007).  The CASE_MANAGER sends the stub
Invite, records the invitee as an inert participant and commits the Invite as a
ledger entry (CM-11-006).  A replica that never sees the Invite or the invitee's
Accept directly learns of the joiner from the ``Announce(CaseLedgerEntry)``
broadcast alone: it holds the same inert record after the Invite entry, and the
same joined record after the Accept entry (CM-31-012, RSH-08-004).
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
    """The stub Invite's entry reaches another replica, which builds the record.

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
