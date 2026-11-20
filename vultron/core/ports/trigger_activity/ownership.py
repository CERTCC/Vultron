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


"""TriggerOwnershipPort: the ownership part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Case ownership transfer: offer, answer and withdraw.
"""

from datetime import datetime
from typing import Protocol


class TriggerOwnershipPort(Protocol):
    """Case ownership transfer: offer, answer and withdraw."""

    def offer_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        attributed_to: str | None = None,
        end_time: datetime | None = None,
        id_: str | None = None,
        *,
        at: datetime,
        in_reply_to: str | None = None,
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership-transfer activity.

        Both Offers of a transfer have this shape (ADR-0199): the Case
        Owner's own, sent *to* the CASE_MANAGER (TRIG-11-001), and the one
        the CASE_MANAGER makes from it (CM-21-028), with *attributed_to* the
        owner and *in_reply_to* the Owner's Offer (CM-24-020).  *end_time*, when
        given, is the Offer's activity-level
        ``end_time``: the deadline to answer it (CM-21-016).  *id_*, when
        given, is the Offer's id, which the CASE_MANAGER derives from the
        Owner's (OX-06-002); an id the store already holds hands back the
        body sealed then.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(Offer(VulnerabilityCase))`` ownership-transfer activity.

        Returns ``(activity_id, activity_dict)`` (TRIG-11-002).
        """
        ...

    def reject_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(Offer(VulnerabilityCase))`` ownership-transfer activity.

        Returns ``(activity_id, activity_dict)`` (TRIG-11-005).
        """
        ...

    def withdraw_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist the owner's withdrawal of its own Offer.

        ``Undo(Offer(VulnerabilityCase))``: *offer_id* names the Offer this
        actor sent, which the CASE_MANAGER made its Offer from (CM-21-015,
        ADR-0199).

        Returns ``(activity_id, activity_dict)`` (TRIG-11-006).
        """
        ...
