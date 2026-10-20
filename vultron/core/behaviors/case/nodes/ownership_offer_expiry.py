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

"""The CASE_MANAGER's lazy expiry of an ownership-transfer Offer (CM-21-017).

Provides:

- :func:`ownership_offer_expiry_snapshot` — the expiry entry's
  ``payloadSnapshot``, a CASE_MANAGER-authored ``Expire(Offer)``.
- :class:`OfferParty` and :class:`ExpiryPrompt` — the reply that prompts the
  check, and which party to the Offer must have sent it.
- :class:`ExpireOverdueOwnershipOfferNode` — finds the case's open
  ownership-transfer Offer and, when its ``end_time`` has passed, commits the
  expiry entry and broadcasts it.

The node is a clock decision (CLP-10-025): the ownership-transfer received
trees (``ownership_transfer_tree``) pass it to
:func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`
as ``clock_decisions``, so it runs after the door guards (the post-close
boundary and the sender guard) and before the open-Offer guards, behind the
factory's CASE_MANAGER gate (BT-17-001).  Only the CASE_MANAGER evaluates
expiry, and a replica learns it from the entry, never by reading the clock
(CM-21-017).  When the Offer has passed its ``end_time``, the expiry entry
closes it before the received activity is judged (CM-21-014), and is
ledgered whether that activity is then admitted (a new Offer) or refused (a
late reply, CM-21-016).  The entry changes no replica state of its own; it
closes the Offer because every "is it open?" reader includes its
``semantic_type`` (``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE,
)
from vultron.core.models.rsvp_deadline import EXPIRE_SNAPSHOT_TYPE
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    open_ownership_offer,
    recorded_ownership_offer,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.predicates.addressing import same_actor_id
from vultron.errors import VultronBTInternalError, VultronNotFoundError


class OfferParty(Enum):
    """The party to an ownership-transfer Offer whose reply is checked."""

    TRANSFEREE = "transferee"
    """Answers the Offer: Accept or Reject (CM-21-011)."""

    OFFERER = "offerer"
    """Withdraws the Offer: Undo (CM-21-015)."""


@dataclass(frozen=True)
class ExpiryPrompt:
    """The reply that prompts the CASE_MANAGER to check the Offer's deadline.

    The expiry is ledgered only for a reply to the open Offer from its party,
    so a sender with no standing never makes the CASE_MANAGER write
    (HP-01-006).  The reply's own guard still refuses it afterwards.

    Attributes:
        sender_id: The reply's sender.
        offer_id: The Offer the reply names: the recorded Offer or the
            forward of it (CM-21-005); ``None`` when it names none.
        party: Which party to the Offer the sender must be.
    """

    sender_id: str
    offer_id: str | None
    party: OfferParty


def ownership_offer_expiry_snapshot(
    *,
    case_id: str,
    offer_id: str,
    manager_id: str,
    end_time: datetime,
    published: datetime,
) -> dict[str, Any]:
    """The expiry entry's snapshot: the CASE_MANAGER's ``Expire(Offer)``.

    Attributed to the CASE_MANAGER, whose decision it is: nobody sent
    anything, the deadline passed by its clock (CLP-07-013).  *published* is
    that clock's reading, so the CASE_MANAGER's claimed times stay in one
    stream (CLP-15-003).  The Offer is named by id with the deadline it
    passed and the case it was for, every nested object inline (CLP-07-006).

    The type is the synthetic ``Expire`` the embargo Invite expiry also
    uses (CM-28-009); its object type tells the two apart.
    """
    return {
        "type": EXPIRE_SNAPSHOT_TYPE,
        "actor": manager_id,
        "context": case_id,
        "published": published.isoformat(),
        "object": {
            "type": "Offer",
            "id": offer_id,
            wire_key("end_time"): end_time.isoformat(),
            "object": {"type": "VulnerabilityCase", "id": case_id},
        },
    }


class ExpireOverdueOwnershipOfferNode(DataLayerActionWithPorts):
    """Ledger the expiry of the case's open ownership-transfer Offer, if due.

    Reads the case's open Offer from the ledger
    (:func:`~vultron.core.participants.ownership_offer.open_ownership_offer`,
    CM-21-014).  When its ``end_time`` is at or before *now*, it commits one
    ``offer_case_ownership_transfer_expired`` entry and broadcasts
    ``Announce(CaseLedgerEntry)`` to the case's participants (CM-21-017).
    That entry closes the Offer, so the activity the CASE_MANAGER processes
    next reads it as closed: a late Accept or Reject is refused (CM-21-016),
    and a new Offer is admitted.

    With a *prompt* (an Accept, Reject or Undo), the expiry is ledgered only
    when the reply names the open Offer and comes from the party
    :class:`ExpiryPrompt` names: the sender's standing is established before
    the CASE_MANAGER writes anything (HP-01-006), as the embargo Invite
    expiry checks the invitee first.  A new Offer prompts with no *prompt*:
    the tree's sender guard has already refused a sender that is not the Case
    Owner (CM-21-019).

    It decides from the CASE_MANAGER's clock (*now*) and the case's ledger
    only; the prompting activity names which Offer and which party, never
    when the deadline passed, so its claimed ``published`` time decides
    nothing (CLP-10-025).

    SUCCESS when there is nothing to expire (no open Offer, no deadline, one
    not yet passed, or a reply that does not prompt it) and when the expiry
    is committed.  The commit runs as
    a nested tree, as the owner-close settle step's does, because which Offer
    expires is known only when the node runs.  A commit the nested tree
    refuses is FAILURE with its reason; an internal error is raised
    (ADR-0095).

    Sits only in a received tree's clock-decision stage, behind the
    CASE_MANAGER gate the factory places around it (BT-17-001).

    Attributes:
        expired_offer_id: The Offer the last run expired, or ``None``.
    """

    def __init__(
        self,
        case_id: str,
        now: datetime | None = None,
        prompt: ExpiryPrompt | None = None,
        name: str | None = None,
    ) -> None:
        """Create the decision.

        Args:
            case_id: The case whose open ownership-transfer Offer is checked.
            now: The instant the Offer's ``end_time`` is compared against;
                the handler passes the one its open-Offer guard uses.
                ``None`` reads the CASE_MANAGER's clock when the node runs.
            prompt: The Accept, Reject or Undo that prompts the check, so the
                expiry is ledgered only for a reply to the open Offer from
                its party (HP-01-006); ``None`` for a new Offer, whose sender
                guard has already checked it is the Case Owner (CM-21-019).
            name: The node's name; defaults to the class name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._now = now
        self._prompt = prompt
        self.expired_offer_id: str | None = None

    def update(self) -> Status:
        self.expired_offer_id = None
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        now = self._now or now_utc()
        offer = open_ownership_offer(self.datalayer, self._case_id)
        if offer is None or not offer.is_past_deadline(now):
            self.feedback_message = (
                f"no open ownership-transfer Offer past its deadline on case"
                f" '{self._case_id}'"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        if (why := self._not_prompted_by_party(offer)) is not None:
            self.feedback_message = (
                f"ownership-transfer Offer '{offer.offer_id}' on case"
                f" '{self._case_id}' is past its end_time, but {why}; its"
                " expiry is not ledgered for this reply (HP-01-006)"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return self._commit_expiry(offer, now)

    def _not_prompted_by_party(
        self, offer: RecordedOwnershipOffer
    ) -> str | None:
        """Why the prompting reply does not entitle an expiry, or ``None``.

        ``None`` with no prompt (a new Offer), or when the reply names *offer*
        and its sender is the prompt's party to it.
        """
        prompt = self._prompt
        if prompt is None:
            return None
        assert self.datalayer is not None and self.actor_id is not None
        if prompt.offer_id is None:
            return "the reply names no Offer"
        try:
            named = recorded_ownership_offer(
                self.datalayer, self._case_id, prompt.offer_id, self.actor_id
            )
        except VultronNotFoundError:
            return f"the reply names Offer '{prompt.offer_id}', never recorded"
        if named.offer_id != offer.offer_id:
            return f"the reply names another Offer, '{named.offer_id}'"
        party_id = (
            offer.transferee_id
            if prompt.party is OfferParty.TRANSFEREE
            else offer.offerer_id(self.actor_id)
        )
        if party_id is None or not same_actor_id(prompt.sender_id, party_id):
            return (
                f"its sender '{prompt.sender_id}' is not its"
                f" {prompt.party.value} '{party_id}'"
            )
        return None

    def _commit_expiry(
        self, offer: RecordedOwnershipOffer, now: datetime
    ) -> Status:
        assert self.actor_id is not None and offer.end_time is not None
        tree = create_commit_log_entry_tree(
            case_id=self._case_id,
            object_id=offer.offer_id,
            semantic_type=OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_SEMANTIC_TYPE,
            payload_snapshot=ownership_offer_expiry_snapshot(
                case_id=self._case_id,
                offer_id=offer.offer_id,
                manager_id=self.actor_id,
                end_time=offer.end_time,
                published=now,
            ),
        )
        result = BTBridge(
            datalayer=cast(CaseOutboxPersistence, self.datalayer)
        ).execute_with_setup(tree=tree, actor_id=self.actor_id)
        if result.internal_error:
            raise VultronBTInternalError(
                f"{self.name}: expiry commit for ownership-transfer Offer"
                f" '{offer.offer_id}' on case '{self._case_id}' failed:"
                f" {result.feedback_message}"
            )
        if result.status != Status.SUCCESS:
            self.feedback_message = (
                f"could not ledger the expiry of ownership-transfer Offer"
                f" '{offer.offer_id}' on case '{self._case_id}':"
                f" {result.feedback_message}"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        self.expired_offer_id = offer.offer_id
        self.feedback_message = (
            f"ownership-transfer Offer '{offer.offer_id}' to"
            f" '{offer.transferee_id}' on case '{self._case_id}' passed its"
            f" end_time {offer.end_time.isoformat()} unanswered; expiry"
            " ledgered and broadcast (CM-21-017)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.SUCCESS


__all__ = [
    "ExpireOverdueOwnershipOfferNode",
    "ExpiryPrompt",
    "OfferParty",
    "ownership_offer_expiry_snapshot",
]
