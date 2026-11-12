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


"""TriggerProposalsPort: the proposals part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Case proposals: create, reject, accept, and the prepared Create.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from vultron.enums.roles import CVDRole


class TriggerProposalsPort(Protocol):
    """Case proposals: create, reject, accept, and the prepared Create."""

    def create_case_proposal(
        self,
        actor: str,
        report_id: str,
        case_actor_id: str,
        summary: str | None = None,
        to: list[str] | None = None,
        offer_id: str | None = None,
        offer_actor_id: str | None = None,
        proposer_case_roles: Sequence[CVDRole] = (),
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Create(CaseProposal)`` activity.

        Builds an ``as_CaseProposal`` from the ``VulnerabilityReport``
        identified by ``report_id``, addressed to the case-actor service at
        ``case_actor_id``, and persists ``Create(CaseProposal)`` to the
        DataLayer.

        ``offer_id`` and ``offer_actor_id`` carry the provenance of the report —
        which ``Offer(VulnerabilityReport)`` brought it and from whom
        (CP-01-007).  The CaseActor cannot recover them on its own; see
        ``as_CaseProposal.offer_id`` for why they have to travel on the wire.

        The Create's ``actor`` is ``actor``'s own full profile, read from this
        DataLayer with its ``embargo_policy``: the CASE_MANAGER reads the
        CASE_OWNER's actor default from that inline profile and nowhere else
        (CP-01-010).

        ``proposer_case_roles`` are the sender's own ``default_case_roles``,
        stated on the proposal so the CASE_MANAGER can seat the sender with
        them (CP-01-011, CP-01-013, ADR-0133).

        Per ``specs/case-proposal.yaml`` CP-04-001, CP-04-002.
        Returns ``(activity_id, activity_dict)``.

        Raises:
            ValueError: when the report, or ``actor``'s own profile, is not
                in this DataLayer.
        """
        ...

    def reject_case_proposal(
        self,
        actor: str,
        proposal: dict,
        to: list[str] | None = None,
        summary: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist a ``Reject(CaseProposal)`` activity.

        The case actor service sends this when it declines to open and manage a
        case for the proposal (CP-05-004).  *proposal* is the wire-serialised
        ``as_CaseProposal`` from the inbound ``Create``; it is embedded inline so
        the vendor has full context without reading anything from the case actor
        service's store (AKM-03-003).

        *summary* carries the refusal reason when the service has one to give,
        which is what the proposer surfaces (CP-06-004).  It is optional: a
        decline is never blocked on having an explanation.

        Per ``specs/case-proposal.yaml`` CP-05-002, CP-05-004.
        Returns ``(activity_id, activity_dict)``.
        """
        ...

    def accept_case_proposal(
        self,
        actor: str,
        proposal: dict,
        to: list[str],
        result: str | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist an ``Accept(CaseProposal)`` activity.

        The CASE_MANAGER sends this to acknowledge that it will open (or has
        already opened) a case for the proposal (CP-05-002).  *proposal* is the
        wire-serialised ``as_CaseProposal`` the inbound ``Create`` carried,
        embedded inline (AKM-03-003); *result* is the URI of the case the
        Accept ties to (CP-05-006).

        Returns ``(activity_id, activity_blob)``.
        """
        ...

    def emit_prepared_create_case(self, payload: dict) -> tuple[str, str]:
        """Persist a ``Create(VulnerabilityCase)`` the emitting node prepared.

        *payload* is the activity's AS2 rendering, under an id derived from
        the proposal, so a redelivered proposal names the same activity
        (CP-05-005).

        Returns ``(activity_id, activity_blob)``.
        """
        ...
