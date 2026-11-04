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

Case ownership transfer: propose, offer, answer and withdraw.
"""

from datetime import datetime
from typing import Protocol


class TriggerOwnershipPort(Protocol):
    """Case ownership transfer: propose, offer, answer and withdraw."""

    def propose_case_ownership_transfer(
        self,
        case_id: str,
        transferee_id: str,
        actor: str,
        content: str | None = None,
        to: list[str] | None = None,
        end_time: datetime | None = None,
    ) -> tuple[str, str]:
        """Create and persist the Case Owner's ownership-transfer proposal.

        ``Offer(Offer(VulnerabilityCase))`` with the case as its ``context``
        (ADR-0148): the inner Offer names the case, *transferee_id* as its
        ``target`` and, when given, *end_time* as its ``end_time``, the
        deadline to answer it (TRIG-11-007, CM-21-016).  The owner sends it
        to the CASE_MANAGER (*to*), which makes the Offer itself.

        Returns ``(activity_id, activity_dict)`` (TRIG-11-001).
        """
        ...

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
    ) -> tuple[str, str]:
        """Create and persist an ``Offer(VulnerabilityCase)`` ownership-transfer activity.

        The one Offer of a transfer, which the CASE_MANAGER makes from the
        owner's proposal (ADR-0148, CM-21-028), with *attributed_to* the
        owner.  *end_time*, when given, is the Offer's activity-level
        ``end_time``: the deadline to answer it (CM-21-016).  *id_*, when
        given, is the Offer's id, which the CASE_MANAGER derives from the
        proposal (OX-06-002); an id the store already holds hands back the
        body sealed then.

        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_ownership_transfer(
        self,
        offer_id: str,
        actor: str,
        to: list[str] | None = None,
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
    ) -> tuple[str, str]:
        """Create and persist the owner's withdrawal of its proposal.

        ``Undo(Offer(Offer(VulnerabilityCase)))``: *offer_id* names the
        proposal this actor sent, which the CASE_MANAGER made its Offer from
        (CM-21-015, ADR-0148).

        Returns ``(activity_id, activity_dict)`` (TRIG-11-006).
        """
        ...
