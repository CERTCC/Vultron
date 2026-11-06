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

"""Builders for the ownership-transfer semantics (CM-21, ADR-0148).

The owner proposes the case to a bystander; the CASE_MANAGER makes the
Offer from the proposal and sends it to the transferee, which accepts or
rejects it, and the owner may withdraw it with ``Undo``.
"""

from typing import Any, cast

from test.support.case_owner import CASE_OWNER_ID
from test.support.received import received_event
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models.events.base import MessageSemantics
from vultron.core.participants.ownership_offer import ownership_offer_id
from vultron.core.services.received_activity import held_received_record
from vultron.wire.as2.factories import (
    accept_case_ownership_transfer_activity,
    propose_case_ownership_transfer_activity,
    reject_case_ownership_transfer_activity,
    undo_case_ownership_transfer_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

from .._ledger_network import BYSTANDER, MANAGER, OWNER, LedgerNetwork
from . import Scenario, applied, refused
from ._net import deliver, send_applied

_BASE = "https://example.org/cases/rerun-sweep-ownership"


def _network(name: str) -> LedgerNetwork:
    return LedgerNetwork(f"{_BASE}/{name}")


def _proposal(net: LedgerNetwork) -> Any:
    """OWNER's proposal to transfer the case to BYSTANDER."""
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=net.case_id, name="Rerun sweep"
    )
    return propose_case_ownership_transfer_activity(
        case,
        target=as_Service(id_=BYSTANDER, name="Transferee"),
        actor=OWNER,
        to=[MANAGER],
        id_=f"{net.case_id}/proposals/1",
    )


def _offered(name: str) -> tuple[LedgerNetwork, Any, Any]:
    """The network after the CASE_MANAGER made its Offer, the proposal and
    the Offer."""
    net = _network(name)
    proposal = _proposal(net)
    send_applied(net, proposal)
    offer = net.stores[MANAGER].read(
        ownership_offer_id(MANAGER, net.case_id, proposal.id_, OWNER)
    )
    assert offer is not None
    return net, proposal, offer


@applied(MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER)
def propose_ownership_transfer() -> Scenario:
    """The owner's proposal: the CASE_MANAGER commits it and makes the Offer."""
    net = _network("propose")
    return deliver(net, _proposal(net))


@refused(MessageSemantics.PROPOSE_CASE_OWNERSHIP_TRANSFER)
def propose_ownership_transfer_while_one_is_open() -> Scenario:
    """A second proposal while the first Offer is unanswered: refused."""
    net, _, _ = _offered("propose-refused")
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=net.case_id, name="Rerun sweep"
    )
    second = propose_case_ownership_transfer_activity(
        case,
        target=as_Service(id_=BYSTANDER, name="Transferee"),
        actor=OWNER,
        to=[MANAGER],
        id_=f"{net.case_id}/proposals/2",
    )
    return deliver(net, second)


def _offer_recorded(offer_id: str):
    """The transferee's intake recorded the Offer, the copy it answers.

    The tree commits nothing: the CASE_MANAGER ledgered the Offer when it
    made it (CM-21-013), so the record is the tree's only effect.
    """

    def _check(dl: Any) -> str | None:
        if held_received_record(dl, offer_id) is None:
            return f"the transferee holds no record of the Offer '{offer_id}'"
        return None

    return _check


@applied(MessageSemantics.OFFER_CASE_OWNERSHIP_TRANSFER)
def offer_ownership_transfer() -> Scenario:
    """The CASE_MANAGER's Offer, delivered to the transferee's replica."""
    net, _, offer = _offered("offer")
    body = read_sealed_body_dict(net.stores[MANAGER], offer.id_)
    assert body is not None, "the Offer was never sealed"
    event = received_event(
        parse_activity(cast(dict[str, Any], body)),
        as_sent=True,
        receiving_actor_id=BYSTANDER,
    )
    return Scenario(
        dl=net.stores[BYSTANDER],
        event=event,
        reached=_offer_recorded(offer.id_),
    )


@applied(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_ownership_transfer() -> Scenario:
    """The transferee accepts: the Accept and the role moves commit."""
    net, _, offer = _offered("accept")
    return deliver(
        net,
        accept_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )


@refused(MessageSemantics.ACCEPT_CASE_OWNERSHIP_TRANSFER)
def accept_ownership_transfer_after_reject() -> Scenario:
    """An Accept of an Offer its transferee already rejected: refused."""
    net, _, offer = _offered("accept-refused")
    send_applied(
        net,
        reject_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )
    return deliver(
        net,
        accept_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )


@applied(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_ownership_transfer() -> Scenario:
    """The transferee declines: committed and announced, ownership stays."""
    net, _, offer = _offered("reject")
    return deliver(
        net,
        reject_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )


@refused(MessageSemantics.REJECT_CASE_OWNERSHIP_TRANSFER)
def reject_ownership_transfer_after_accept() -> Scenario:
    """A Reject of an Offer its transferee already accepted: refused."""
    net, _, offer = _offered("reject-refused")
    send_applied(
        net,
        accept_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )
    return deliver(
        net,
        reject_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )


@applied(MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER)
def undo_ownership_transfer() -> Scenario:
    """The owner withdraws its proposal: the withdrawal commits."""
    net, proposal, _ = _offered("undo")
    return deliver(
        net,
        undo_case_ownership_transfer_activity(
            proposal, actor=OWNER, to=[MANAGER]
        ),
    )


@refused(MessageSemantics.UNDO_CASE_OWNERSHIP_TRANSFER)
def undo_ownership_transfer_after_reject() -> Scenario:
    """A withdrawal of an Offer already rejected: refused with a notice."""
    net, proposal, offer = _offered("undo-refused")
    send_applied(
        net,
        reject_case_ownership_transfer_activity(
            cast(Any, offer), actor=BYSTANDER, to=[MANAGER]
        ),
    )
    return deliver(
        net,
        undo_case_ownership_transfer_activity(
            proposal, actor=OWNER, to=[MANAGER]
        ),
    )
