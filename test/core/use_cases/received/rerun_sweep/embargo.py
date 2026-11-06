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

"""Builders for the embargo semantics.

Each CASE_MANAGER scenario runs on a ``LedgerNetwork`` and reuses the
embargo test harness (``test_embargo_relay_replay``,
``test_embargo_answer_idempotency``, ``test_embargo_refusal_notice``), so
the delivery is the one those tests already prove applied or refused.
The ``Announce(EmbargoEvent)`` is received by a paused replica, the one
receiver that applies it (CM-31-010).
"""

import json
from typing import Any, cast

from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.outbox_sealed_body import dump_outbound_body
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_termination import OtherCause
from vultron.core.models.events.base import MessageSemantics
from vultron.core.states.embargo_register import TerminationReason
from vultron.wire.as2.factories import (
    announce_embargo_activity,
    em_propose_embargo_activity,
    remove_embargo_from_case_activity,
    withdraw_from_embargo_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent

from .._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    PROPOSER,
    LedgerNetwork,
)
from ..test_embargo_answer_idempotency import _answer_body, _invited
from ..test_embargo_ending_notices import (
    CASE_ID as _PAUSED_CASE_ID,
    MANAGER as _PAUSED_MANAGER,
    REMOVED as _PAUSED_REPLICA,
    REVISION_ID as _PAUSED_REVISION,
    _Replica,
)
from ..test_embargo_refusal_notice import _decided
from ..test_embargo_relay_replay import _propose
from . import Scenario, applied, refused

_BASE = "https://example.org/cases/rerun-sweep"


def _net(tag: str) -> LedgerNetwork:
    return LedgerNetwork(f"{_BASE}/embargo-{tag}")


def _from_body(
    net: LedgerNetwork, body: dict[str, Any], *, to: str = MANAGER
) -> Scenario:
    """A scenario delivering the wire *body* to *to*, stamped as sent.

    Signed by its author unless it is the body its sender's outbox sealed
    (:meth:`LedgerNetwork.delivered_body`).
    """
    stamped = net.delivered_body(body, receiver=to)
    event = received_event(
        parse_activity(stamped), as_sent=True, receiving_actor_id=to
    )
    return Scenario(dl=net.stores[to], event=event)


def _proposal_body(net: LedgerNetwork, tag: str) -> dict[str, Any]:
    """PROPOSER's revision, sent to the CASE_MANAGER only (EP-09-001)."""
    revision = as_EmbargoEvent(
        id_=f"{net.case_id}/embargo_events/{tag}",
        content=f"Terms {tag}",
        context=net.case_id,
        end_time=days_from_now_utc(90),
    )
    proposal = em_propose_embargo_activity(
        revision,
        context=net.case_id,
        actor=PROPOSER,
        to=[MANAGER],
        id_=f"{net.case_id}/embargo_proposals/{tag}",
    )
    return cast(dict[str, Any], json.loads(dump_outbound_body(proposal)))


def _remove_body(
    net: LedgerNetwork, *, reason: TerminationReason, tag: str
) -> dict[str, Any]:
    """OWNER asks the CASE_MANAGER to end the embargo in force."""
    embargo = net.stores[MANAGER].read(net.initial_embargo_id)
    assert isinstance(embargo, as_EmbargoEvent)
    activity = remove_embargo_from_case_activity(
        embargo,
        origin=net.case_id,
        context=net.case_id,
        actor=OWNER,
        to=[MANAGER],
        reason=reason,
        cause=OtherCause() if reason is TerminationReason.EARLY else None,
        id_=f"{OWNER}/removes/{tag}",
    )
    return activity.model_dump(mode="json", by_alias=True, exclude_none=True)


def _owner_decision_body(
    net: LedgerNetwork, embargo_id: str, *, accept: bool
) -> dict[str, Any]:
    """OWNER's decision on *embargo_id*, built by its trigger adapter."""
    adapter = TriggerActivityAdapter(net.stores[OWNER])
    build = (
        adapter.activate_embargo if accept else adapter.reject_embargo_proposal
    )
    _, sealed = build(
        embargo_id=embargo_id, case_id=net.case_id, actor=OWNER, to=[MANAGER]
    )
    return cast(dict[str, Any], json.loads(sealed))


def _owner_decision_on_a_proposal(tag: str, *, accept: bool) -> Scenario:
    net = _net(tag)
    embargo_id = _propose(net, tag, 90)
    net.deliver(MANAGER, to=OWNER, type_="Invite")
    return _from_body(
        net, _owner_decision_body(net, embargo_id, accept=accept)
    )


def _owner_decision_on_no_proposal(tag: str, *, accept: bool) -> Scenario:
    """The embargo in force is no open proposal: refused with the notice."""
    net = _net(tag)
    return _from_body(
        net, _owner_decision_body(net, net.initial_embargo_id, accept=accept)
    )


def _withdraw_body(
    net: LedgerNetwork, actor: str, embargo_id: str, *, tag: str
) -> dict[str, Any]:
    """*actor* leaves *embargo_id* with ``Leave(EmbargoEvent)``."""
    embargo = cast(Any, net.stores[actor].read(embargo_id))
    activity = withdraw_from_embargo_activity(
        embargo,
        context=net.case_id,
        actor=actor,
        to=[MANAGER],
        id_=f"{actor}/withdrawals/{tag}",
    )
    return cast(dict[str, Any], json.loads(dump_outbound_body(activity)))


@applied(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo() -> Scenario:
    """A participant proposes a revision: committed and relayed."""
    net = _net("invite")
    return _from_body(net, _proposal_body(net, "invite"))


@refused(MessageSemantics.INVITE_TO_EMBARGO_ON_CASE)
def invite_to_embargo_after_the_embargo_ended() -> Scenario:
    """A proposal once the embargo ended: refused, ``Reject(Invite)`` sent."""
    net = _net("invite-refused")
    ending = _from_body(
        net,
        _remove_body(net, reason=TerminationReason.EARLY, tag="ends"),
    )
    net.receive_event(MANAGER, ending.event)
    return _from_body(net, _proposal_body(net, "too-late"))


@applied(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_embargo() -> Scenario:
    """A participant accepts a relayed revision Invite: consent committed."""
    net = _net("accept")
    _, invite_id = _invited(net, BYSTANDER, "accept")
    return _from_body(
        net, _answer_body(net, BYSTANDER, invite_id, accept=True, tag="1")
    )


@refused(MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE)
def accept_invite_to_a_decided_embargo() -> Scenario:
    """An Accept of a proposal the owner already rejected: refused."""
    net = _net("accept-refused")
    _, invite_id = _decided(net, "accept-refused")
    return _from_body(
        net, _answer_body(net, BYSTANDER, invite_id, accept=True, tag="late")
    )


@applied(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_embargo() -> Scenario:
    """A participant rejects a relayed revision Invite: consent committed."""
    net = _net("reject")
    _, invite_id = _invited(net, BYSTANDER, "reject")
    return _from_body(
        net, _answer_body(net, BYSTANDER, invite_id, accept=False, tag="1")
    )


@refused(MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE)
def reject_invite_to_a_decided_embargo() -> Scenario:
    """A Reject of a proposal the owner already rejected: refused."""
    net = _net("reject-refused")
    _, invite_id = _decided(net, "reject-refused")
    return _from_body(
        net,
        _answer_body(net, BYSTANDER, invite_id, accept=False, tag="late"),
    )


@applied(MessageSemantics.ACTIVATE_EMBARGO_ON_CASE)
def activate_embargo() -> Scenario:
    """The owner activates an open revision: committed and announced."""
    return _owner_decision_on_a_proposal("activate", accept=True)


@refused(MessageSemantics.ACTIVATE_EMBARGO_ON_CASE)
def activate_no_open_proposal() -> Scenario:
    """The owner activates the embargo already in force: refused."""
    return _owner_decision_on_no_proposal("activate-refused", accept=True)


@applied(MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE)
def reject_embargo_proposal() -> Scenario:
    """The owner rejects an open revision: committed and announced."""
    return _owner_decision_on_a_proposal("owner-reject", accept=False)


@refused(MessageSemantics.REJECT_EMBARGO_PROPOSAL_ON_CASE)
def reject_no_open_proposal() -> Scenario:
    """The owner rejects the embargo already in force: refused."""
    return _owner_decision_on_no_proposal("owner-reject-refused", accept=False)


@applied(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo() -> Scenario:
    """The owner ends the embargo in force early: torn down and announced."""
    net = _net("remove")
    return _from_body(
        net, _remove_body(net, reason=TerminationReason.EARLY, tag="early")
    )


@refused(MessageSemantics.REMOVE_EMBARGO_EVENT_FROM_CASE)
def remove_embargo_before_its_end_time() -> Scenario:
    """An END_TIME_REACHED claimed before the end time: refused."""
    net = _net("remove-refused")
    return _from_body(
        net,
        _remove_body(
            net, reason=TerminationReason.END_TIME_REACHED, tag="untimely"
        ),
    )


@applied(MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE)
def withdraw_from_embargo() -> Scenario:
    """A signatory leaves the embargo in force: committed and announced."""
    net = _net("withdraw")
    return _from_body(
        net,
        _withdraw_body(net, BYSTANDER, net.initial_embargo_id, tag="leave"),
    )


@refused(MessageSemantics.WITHDRAW_FROM_EMBARGO_ON_CASE)
def withdraw_from_embargo_as_the_owner() -> Scenario:
    """The case owner may not leave the embargo it holds: refused."""
    net = _net("withdraw-refused")
    return _from_body(
        net, _withdraw_body(net, OWNER, net.initial_embargo_id, tag="owner")
    )


def _revision_adopted(dl: SqliteDataLayer) -> str | None:
    case = cast(Any, dl.read(_PAUSED_CASE_ID))
    if case is not None and case.active_embargo_id == _PAUSED_REVISION:
        return None
    return "the paused replica did not adopt the announced revision"


@applied(MessageSemantics.ANNOUNCE_EMBARGO_EVENT_TO_CASE)
def announce_embargo_to_a_paused_replica() -> Scenario:
    """The CASE_MANAGER announces a shorter revision to a paused replica.

    The replica applies it (CM-31-010): a state write, nothing committed
    or sent, so the scenario names the write it checks.
    """
    replica = _Replica(_PAUSED_REPLICA)
    revision = as_EmbargoEvent(
        id_=_PAUSED_REVISION,
        context=_PAUSED_CASE_ID,
        end_time=days_from_now_utc(30),
    )
    activity = announce_embargo_activity(
        revision,
        context=_PAUSED_CASE_ID,
        actor=_PAUSED_MANAGER,
        to=[replica.actor_id],
    )
    event = received_event(activity, at=replica.dl).model_copy(
        update={"receiving_actor_id": replica.actor_id}
    )
    return Scenario(dl=replica.dl, event=event, reached=_revision_adopted)
