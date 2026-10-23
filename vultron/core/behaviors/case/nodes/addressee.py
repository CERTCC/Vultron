#!/usr/bin/env python

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

"""The addressee door guard of every received tree (HP-01-005, CLP-10-010).

A receiver acts on an activity only when it is addressed to it.  Any other
store holds a misaddressed copy: it refuses it, commits nothing, changes no
state and answers nothing, and its refusal names the receiver and the
recipients the sender chose, so the misrouting can be traced (HP-01-005,
ADR-0118, #4132).

"Addressed to the receiver" has one definition,
:func:`addressed_to_receiver`, and everything that asks the question reads
it: the door guard here, and the late check an exempt tree runs in its own
place (``CheckOfferAddressedToReceiverNode``, CM-15-002), which reads its
``to`` half, :func:`named_in_to`, because an ``Offer(Report)`` makes its
receiver eligible to create a case from ``to`` alone (HP-09-001).  The
receiver is addressed when

- it sent the activity (its own copy, a self-addressed act);
- it is named in ``to``, compared with
  :func:`~vultron.core.predicates.addressing.is_addressed_to`, so a trailing
  slash still names it; or
- ``to`` names a case's participants collection (``{case_id}/participants``,
  IE-11-002) and the receiver's store records it as an active participant of
  that case (CM-10-004): the roster alone is not membership.

``cc``, ``bto`` and ``bcc`` address no Vultron recipient and are never read:
no Vultron activity gives a ``cc`` recipient standing (HP-01-005, OX-08-001,
HP-09-001, ADR-0109).

:class:`ActivityAddressedToReceiverNode` is that check.
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
places it in every received tree, between the post-close boundary and the
sender guard, so intake has already archived the copy (CLP-10-018) and
nothing after the guard runs (CLP-10-010).  No tree writes its own copy of
the check (CS-22-001).  A tree opts out only by passing a registered
:class:`AddresseeExemption` that says why: :data:`ADDRESSEE_EXEMPTIONS` is
the whole list, and ``test/architecture/test_received_tree_addressee_guard.py``
pins which tree uses each one.
"""

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from py_trees.common import Status
from py_trees.ports import PortInformation
from pydantic import BaseModel, ConfigDict

from vultron.core.behaviors.helpers import DataLayerConditionWithPorts
from vultron.core.participants.recipients import is_case_content_recipient
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    is_addressed_to,
    participants_collection_case_id,
    same_actor_id,
)
from vultron.primitives import NonEmptyString

__all__ = [
    "ADDRESSEE_EXEMPTIONS",
    "ActivityAddressedToReceiverNode",
    "AddresseeExemption",
    "ENCLOSING_TREE_ADDRESSEE_CHECK",
    "MISROUTED_EMBARGO_INVITE",
    "OFFER_REPORT_STORED_FIRST",
    "addressed_to_receiver",
    "named_in_to",
    "unaddressed_copy_reason",
]


class AddresseeExemption(BaseModel):
    """One recorded decision that a received tree runs no addressee door guard.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the tree is correct without the door guard, and what
            stands in for it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString


OFFER_REPORT_STORED_FIRST: Final = AddresseeExemption(
    name="offer-report-stored-first",
    reason=(
        "A received Offer(VulnerabilityReport) keeps the report and the"
        " Offer whatever the receiver decides about them, so a receiver that"
        " opts out of case creation can still ACK or decide on the report"
        " (CM-15-001, CM-15-002).  Its tree stores them first, then checks"
        " the addressee with CheckOfferAddressedToReceiverNode, which reads"
        " the same addressed_to_receiver definition (HP-09-001, HP-01-005)."
    ),
)

ENCLOSING_TREE_ADDRESSEE_CHECK: Final = AddresseeExemption(
    name="enclosing-tree-addressee-check",
    reason=(
        "The tree is a subtree of a received tree that already runs the"
        " addressee door guard ahead of it (the close-case tree's close"
        " arm), so a second check would repeat the first."
    ),
)

MISROUTED_EMBARGO_INVITE: Final = AddresseeExemption(
    name="misrouted-embargo-invite",
    reason=(
        "An Invite(EmbargoEvent) whose to names no single invitee is a"
        " misrouting (EP-09-010): it names no addressee to check, and the"
        " receiver answers it with a ProcessingFault (MSM-05-001) instead."
    ),
)

#: Every registered exemption, by name.  The factory refuses any other.
ADDRESSEE_EXEMPTIONS: Final[Mapping[str, AddresseeExemption]] = (
    MappingProxyType(
        {
            exemption.name: exemption
            for exemption in (
                OFFER_REPORT_STORED_FIRST,
                ENCLOSING_TREE_ADDRESSEE_CHECK,
                MISROUTED_EMBARGO_INVITE,
            )
        }
    )
)


def _belongs_to_collection(
    dl: CasePersistence, receiving_actor_id: str, address: str
) -> bool:
    """True when *address* is a participants collection holding the receiver.

    The receiver's own store answers: the case must be one it holds, and the
    receiver must be an active participant of it
    (:func:`~vultron.core.participants.recipients.is_case_content_recipient`,
    CM-10-004), so an inert or removed participant listed on the roster is
    not a member.  Store errors propagate, so "could not tell" never admits.
    """
    case_id = participants_collection_case_id(address)
    if case_id is None:
        return False
    case = dl.read_case(case_id)
    if case is None:
        return False
    return is_case_content_recipient(case, dl, receiving_actor_id)


def named_in_to(
    dl: CasePersistence, receiving_actor_id: str, to: Sequence[str]
) -> bool:
    """True when *to* addresses the receiver, alone or by a collection.

    The ``to`` half of :func:`addressed_to_receiver`: the receiver is named
    in *to*, or *to* names a case participants collection the receiver's
    store records it in.  An ``Offer(Report)`` reads this half alone, because
    its case-creation eligibility comes from ``to`` only (HP-09-001): a
    sender's own copy proposes no case.

    Args:
        dl: The receiver's store, read for collection membership only.
        receiving_actor_id: The actor whose store received the copy.
        to: The activity's ``to`` recipients, as ids.
    """
    if is_addressed_to(receiving_actor_id, to):
        return True
    return any(
        _belongs_to_collection(dl, receiving_actor_id, address)
        for address in to
    )


def addressed_to_receiver(
    dl: CasePersistence,
    receiving_actor_id: str,
    *,
    sender_id: str | None,
    to: Sequence[str],
) -> bool:
    """True when an activity from *sender_id* to *to* addresses the receiver.

    The one definition of "addressed to the receiver" (HP-01-005,
    HP-01-012): the receiver sent it, or :func:`named_in_to` holds.  See the
    module docstring.

    Args:
        dl: The receiver's store, read for collection membership only.
        receiving_actor_id: The actor whose store received the copy.
        sender_id: The activity's ``actor``, if any.
        to: The activity's ``to`` recipients, as ids.
    """
    if sender_id and same_actor_id(receiving_actor_id, sender_id):
        return True
    return named_in_to(dl, receiving_actor_id, to)


def unaddressed_copy_reason(
    dl: CasePersistence,
    receiving_actor_id: str,
    event: object,
    *,
    label: str,
) -> str | None:
    """Why *event* is an unaddressed copy at *receiving_actor_id*, or ``None``.

    ``None`` when :func:`addressed_to_receiver` holds for the event's sender
    and its activity's ``to``.  An event without an activity names no
    recipient at all.

    Args:
        dl: The receiver's store, read for collection membership only.
        receiving_actor_id: The actor whose store received the copy.
        event: The received event on the blackboard.
        label: Names the tree in the reason, e.g. ``"AcceptEmbargoInviteBT"``.
    """
    sender_id = getattr(event, "actor_id", None)
    activity = getattr(event, "activity", None)
    to = list(getattr(activity, "to", None) or []) if activity else []
    if addressed_to_receiver(
        dl,
        receiving_actor_id,
        sender_id=sender_id if isinstance(sender_id, str) else None,
        to=to,
    ):
        return None
    return (
        f"'{receiving_actor_id}' is neither the sender nor a recipient of"
        f" {label} '{getattr(event, 'activity_id', None)}' (to={to}); an"
        " unaddressed copy is refused (HP-01-005)"
    )


class ActivityAddressedToReceiverNode(DataLayerConditionWithPorts):
    """Door guard: the activity is addressed to the executing actor.

    Returns:
        SUCCESS when :func:`addressed_to_receiver` holds: the executing actor
        sent the activity, is one of its ``to`` recipients, or belongs to a
        case participants collection its ``to`` names.

        FAILURE otherwise, with a reason naming the receiver, the activity
        and its ``to`` (HP-01-005), logged at WARNING.  An event with no
        activity names no recipient, so it is refused too.

    Reads the blackboard, and the store only to resolve a collection
    address; it never writes.

    Args:
        label: Names the tree in the refusal; the factory passes the tree's
            own name.
    """

    def __init__(self, label: str, name: str | None = None) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.label = label
        self._activity: object | None = None

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self._activity = self._try_get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        reason = unaddressed_copy_reason(
            self.datalayer, self.actor_id, self._activity, label=self.label
        )
        if reason is None:
            return Status.SUCCESS
        self.feedback_message = reason
        self.logger.warning(
            "%s: refused '%s' (actor '%s'): %s",
            self.label,
            getattr(self._activity, "activity_id", None),
            getattr(self._activity, "actor_id", None),
            reason,
        )
        return Status.FAILURE
