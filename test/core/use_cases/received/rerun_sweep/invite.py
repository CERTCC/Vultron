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

"""Builders for the case-joining Invite semantics (CM-11, ADR-0114).

A joiner is seated inert at the CASE_MANAGER under a stub Invite
(CM-11-006).  It answers the stub at the CASE_MANAGER; an Accept seeds the
case at the joiner and is followed by the full-case Invite (CM-11-010),
which the joiner answers in turn with its own ledger position (CM-11-011).
The two Invites are also delivered to the joiner's own store.
"""

from typing import Any, cast

from test.support.ledger_rebuild import run_use_case
from test.support.objects import authored_at, make
from test.support.received import case_stub, received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.received_activity import held_received_record
from vultron.core.states.em import EM
from vultron.core.sync_helpers import ledger_tail_position
from vultron.enums.roles import CVDRole
from vultron.wire.as2.factories import (
    rm_accept_full_case_invite_activity,
    rm_accept_invite_to_case_activity,
    rm_invite_to_case_activity,
    rm_reject_full_case_invite_activity,
    rm_reject_invite_to_case_activity,
    rm_tentative_reject_full_case_invite_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Invite,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor

from .._ledger_network import MANAGER, LedgerNetwork
from ..conftest import seed_inert_invitee
from . import Scenario, applied, refused
from ._net import deliver, send_applied

_BASE = "https://example.org/cases/rerun-sweep-invite"

#: The actor invited to join the case.
JOINER = "https://example.org/users/rerun-sweep-joiner"


def _invited(name: str) -> tuple[LedgerNetwork, as_Invite]:
    """A network whose CASE_MANAGER seated JOINER inert under a stub Invite."""
    net = LedgerNetwork(f"{_BASE}/{name}", em_state=EM.NONE)
    dl = net.stores[MANAGER]
    invite = rm_invite_to_case_activity(
        make(as_Actor, id_=JOINER),
        to=[JOINER],
        target=case_stub(net.case_id),
        actor=MANAGER,
        roles=[CVDRole.VENDOR],
        id_=f"{net.case_id}/invitations/joiner",
        at=authored_at(),
    )
    dl.create(invite)
    case = cast(VulnerabilityCase, dl.read(net.case_id))
    seed_inert_invitee(dl, case, JOINER)
    dl.save(case)
    return net, invite


def _at_joiner(net: LedgerNetwork, activity_id: str) -> Any:
    """The CASE_MANAGER's queued *activity_id*, as JOINER's inbox extracts it."""
    body = read_sealed_body_dict(net.stores[MANAGER], activity_id)
    assert body is not None, f"'{activity_id}' was never sealed"
    return received_event(
        parse_activity(cast(dict[str, Any], body)),
        as_sent=True,
        receiving_actor_id=JOINER,
    )


def _joined(name: str) -> tuple[LedgerNetwork, as_Invite]:
    """JOINER accepted the stub Invite; returns the full-case Invite sent."""
    net, stub = _invited(name)
    send_applied(
        net,
        rm_accept_invite_to_case_activity(
            stub, actor=JOINER, to=[MANAGER], at=authored_at()
        ),
    )
    dl = net.stores[MANAGER]
    invites = [
        cast(as_Invite, dl.read(a.id_))
        for a in net.queued(MANAGER, to=JOINER, type_="Invite")
        if (read_sealed_body_dict(dl, a.id_) or {}).get("ledgerPosition")
        is not None
        and (read_sealed_body_dict(dl, a.id_) or {}).get("target")
        == net.case_id
    ]
    assert len(invites) == 1, invites
    return net, invites[0]


def _recorded(activity_id: str):
    """JOINER's intake recorded *activity_id*.

    The joiner's trees commit nothing (only the CASE_MANAGER does,
    CLP-09-001), so the record is what a re-run could write again.
    """

    def _check(dl: Any) -> str | None:
        if held_received_record(dl, activity_id) is None:
            return f"the joiner holds no record of '{activity_id}'"
        return None

    return _check


@applied(MessageSemantics.INVITE_ACTOR_TO_CASE)
def invite_actor_to_case() -> Scenario:
    """The stub Invite at JOINER's empty store: intake records it."""
    _, stub = _invited("invite")
    return Scenario(
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=JOINER),
        event=received_event(stub, receiving_actor_id=JOINER),
        reached=_recorded(stub.id_),
    )


@refused(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case_with_no_record() -> Scenario:
    """An Accept of a stub Invite that seated no record: refused."""
    net = LedgerNetwork(f"{_BASE}/accept-refused", em_state=EM.NONE)
    stub = rm_invite_to_case_activity(
        make(as_Actor, id_=JOINER),
        to=[JOINER],
        target=case_stub(net.case_id),
        actor=MANAGER,
        roles=[CVDRole.VENDOR],
        id_=f"{net.case_id}/invitations/joiner",
        at=authored_at(),
    )
    net.stores[MANAGER].create(stub)
    return deliver(
        net,
        rm_accept_invite_to_case_activity(
            stub, actor=JOINER, to=[MANAGER], at=authored_at()
        ),
    )


@applied(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_CASE)
def accept_invite_actor_to_case() -> Scenario:
    """JOINER accepts the stub Invite: joined, case seeded, full Invite sent."""
    net, stub = _invited("accept")
    return deliver(
        net,
        rm_accept_invite_to_case_activity(
            stub, actor=JOINER, to=[MANAGER], at=authored_at()
        ),
    )


@applied(MessageSemantics.REJECT_INVITE_ACTOR_TO_CASE)
def reject_invite_actor_to_case() -> Scenario:
    """JOINER declines the stub Invite: its record closes, committed."""
    net, stub = _invited("reject")
    return deliver(
        net,
        rm_reject_invite_to_case_activity(
            stub, actor=JOINER, to=[MANAGER], at=authored_at()
        ),
    )


@applied(MessageSemantics.INVITE_ACTOR_TO_FULL_CASE)
def invite_actor_to_full_case() -> Scenario:
    """The full-case Invite at JOINER, which holds the case's replica.

    JOINER records the stub's trust anchor, then the CASE_MANAGER's
    ``Announce(VulnerabilityCase)`` creates its replica (PCR-03-004).  The
    inbox judges a full-case Invite only once the replica exists, so it is
    on the participant-replica path (CM-11-033, HP-01-041).
    """
    net, full = _joined("invite-full")
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=JOINER)
    stub = net.stores[MANAGER].read(f"{net.case_id}/invitations/joiner")
    assert stub is not None
    anchored = run_use_case(
        dl, received_event(cast(as_Activity, stub), receiving_actor_id=JOINER)
    )
    assert anchored.disposition is HandlerDisposition.APPLIED, anchored.reason
    (announce,) = [
        a
        for a in net.queued(MANAGER, to=JOINER, type_="Announce")
        if (read_sealed_body_dict(net.stores[MANAGER], a.id_) or {})
        .get("object", {})
        .get("type")
        == "VulnerabilityCase"
    ]
    replica = run_use_case(dl, _at_joiner(net, announce.id_))
    assert replica.disposition is HandlerDisposition.APPLIED, replica.reason
    assert isinstance(dl.read(net.case_id), VulnerabilityCase)
    return Scenario(
        dl=dl, event=_at_joiner(net, full.id_), reached=_recorded(full.id_)
    )


_REPLIES = {
    "accept": rm_accept_full_case_invite_activity,
    "tentative_reject": rm_tentative_reject_full_case_invite_activity,
    "reject": rm_reject_full_case_invite_activity,
}


def _full_reply(kind: str, name: str, *, behind: bool = False) -> Scenario:
    """JOINER's *kind* reply to the full-case Invite, stating its position.

    The position is the CASE_MANAGER's tail, the replier caught up; with
    *behind*, the ledger's first entry, behind the Invite's floor, which
    the reply check refuses (CM-11-012).
    """
    net, full = _joined(name)
    dl = net.stores[MANAGER]
    position = ledger_tail_position(net.case_id, dl)
    if behind:
        first = min(
            (
                e
                for e in dl.list_objects("CaseLedgerEntry")
                if isinstance(e, CaseLedgerEntry) and e.case_id == net.case_id
            ),
            key=lambda e: e.log_index,
        )
        position = LedgerPosition(
            log_index=first.log_index, entry_hash=first.entry_hash
        )
    return deliver(
        net,
        _REPLIES[kind](
            full, position, actor=JOINER, to=[MANAGER], at=authored_at()
        ),
    )


@applied(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE)
def accept_invite_actor_to_full_case() -> Scenario:
    """JOINER accepts the full-case Invite at the tail: R -> V, committed."""
    return _full_reply("accept", "accept-full")


@applied(MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE)
def tentative_reject_invite_actor_to_full_case() -> Scenario:
    """JOINER tentatively declines the full-case Invite: R -> I, committed."""
    return _full_reply("tentative_reject", "tentative-reject-full")


@applied(MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE)
def reject_invite_actor_to_full_case() -> Scenario:
    """JOINER declines the full-case Invite: R -> C, committed."""
    return _full_reply("reject", "reject-full")


@refused(MessageSemantics.ACCEPT_INVITE_ACTOR_TO_FULL_CASE)
def accept_invite_actor_to_full_case_behind() -> Scenario:
    """An Accept stating a position behind the Invite's floor: refused."""
    return _full_reply("accept", "accept-full-refused", behind=True)


@refused(MessageSemantics.TENTATIVE_REJECT_INVITE_ACTOR_TO_FULL_CASE)
def tentative_reject_invite_actor_to_full_case_behind() -> Scenario:
    """A tentative Reject stating a position behind the floor: refused."""
    return _full_reply(
        "tentative_reject", "tentative-full-refused", behind=True
    )


@refused(MessageSemantics.REJECT_INVITE_ACTOR_TO_FULL_CASE)
def reject_invite_actor_to_full_case_behind() -> Scenario:
    """A Reject stating a position behind the floor: refused."""
    return _full_reply("reject", "reject-full-refused", behind=True)
