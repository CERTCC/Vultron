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
- :class:`ExpireOverdueOwnershipOfferNode` — finds the case's open
  ownership-transfer Offer and, when its ``end_time`` has passed, commits the
  expiry entry and broadcasts it.

The node runs only behind the CASE_MANAGER gate
(:func:`~vultron.core.behaviors.case.ownership_expiry_tree.create_ownership_offer_expiry_tree`,
BT-17-001): only the CASE_MANAGER evaluates expiry, and a replica learns it
from the entry, never by reading the clock (CM-21-017).
"""

from datetime import datetime
from typing import Any, cast

from py_trees.common import Status

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.helpers import DataLayerActionWithPorts
from vultron.core.behaviors.sync.commit_tree import (
    create_commit_log_entry_tree,
)
from vultron.core.models.protocol_pair import (
    OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE,
)
from vultron.core.models.rsvp_deadline import INVITE_EXPIRED_SNAPSHOT_TYPE
from vultron.core.models.wire_keys import wire_key
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    open_ownership_offer,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import VultronBTInternalError


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
        "type": INVITE_EXPIRED_SNAPSHOT_TYPE,
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

    SUCCESS when there is nothing to expire (no open Offer, no deadline, or
    one not yet passed) and when the expiry is committed.  The commit runs as
    a nested tree, as the owner-close settle step's does, because which Offer
    expires is known only when the node runs.  A commit the nested tree
    refuses is FAILURE with its reason; an internal error is raised
    (ADR-0095).

    Sits only behind the CASE_MANAGER gate (BT-17-001).

    Attributes:
        expired_offer_id: The Offer the last run expired, or ``None``.
    """

    def __init__(
        self, case_id: str, now: datetime, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._now = now
        self.expired_offer_id: str | None = None

    def update(self) -> Status:
        self.expired_offer_id = None
        if (f := self._require_datalayer_and_actor()) is not None:
            return f
        assert self.datalayer is not None and self.actor_id is not None
        offer = open_ownership_offer(self.datalayer, self._case_id)
        if offer is None or not offer.is_past_deadline(self._now):
            self.feedback_message = (
                f"no open ownership-transfer Offer past its deadline on case"
                f" '{self._case_id}'"
            )
            self.logger.debug("%s: %s", self.name, self.feedback_message)
            return Status.SUCCESS
        return self._commit_expiry(offer)

    def _commit_expiry(self, offer: RecordedOwnershipOffer) -> Status:
        assert self.actor_id is not None and offer.end_time is not None
        tree = create_commit_log_entry_tree(
            case_id=self._case_id,
            object_id=offer.offer_id,
            event_type=OFFER_CASE_OWNERSHIP_TRANSFER_EXPIRED_EVENT_TYPE,
            payload_snapshot=ownership_offer_expiry_snapshot(
                case_id=self._case_id,
                offer_id=offer.offer_id,
                manager_id=self.actor_id,
                end_time=offer.end_time,
                published=self._now,
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
    "ownership_offer_expiry_snapshot",
]
