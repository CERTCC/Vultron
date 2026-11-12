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
"""Factories for case proposals: the Offer and its Accept and Reject.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
"""

from datetime import datetime

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.factories._construct import build_activity
from vultron.wire.as2.factories._inline import require_inline
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.actors import as_Actor
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal


def create_case_proposal_activity(
    actor: CoreActor | as_Actor,
    proposal: as_CaseProposal,
    to: list[str],
    *,
    at: datetime,
    **kwargs,
) -> as_Create:
    """Build a ``Create(CaseProposal)`` sent by the report receiver.

    The report receiver sends this to the case-actor service to initiate the
    case initialization protocol (CP-04-001).  The ``as_CaseProposal``
    is embedded inline so the case-actor service has full context without
    an additional round-trip, and so is the sender's own actor profile: it
    carries the embargo policy that is the CASE_OWNER's actor default, and
    the CASE_MANAGER reads that default from nowhere else (CP-01-010).

    Args:
        actor: The sending actor's full profile, with its ``embargo_policy``
            when it has published one.  Its ``id`` must be the proposal's
            ``attributed_to``.
        proposal: The ``as_CaseProposal`` being created (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the case-actor service URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Create`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails,
            *proposal* is not an inline ``as_CaseProposal`` (AKM-02-004),
            or *actor* is not the proposal's ``attributed_to``.
    """
    proposal = require_inline(
        proposal, as_CaseProposal, factory="create_case_proposal_activity"
    )
    if actor.id_ != proposal.attributed_to:
        raise VultronActivityConstructionError(
            f"create_case_proposal_activity: actor {actor.id_!r} is not the"
            f" proposal's attributed_to {proposal.attributed_to!r}"
            " (CP-01-010)"
        )
    return build_activity(
        "create_case_proposal_activity",
        as_Create,
        at,
        lambda: {"actor": actor, "object_": proposal, "to": to, **kwargs},
    )


def accept_case_proposal_activity(
    actor_id: str,
    proposal: as_CaseProposal,
    to: list[str],
    *,
    at: datetime,
    **kwargs,
) -> as_Accept:
    """Build an ``Accept(CaseProposal)`` sent by the case-actor service.

    The case-actor service sends this to acknowledge that it will create a
    ``as_VulnerabilityCase`` from the report receiver's proposal.  A separate
    ``Create(VulnerabilityCase)`` follows (CP-05-003).

    Args:
        actor_id: URI of the case-actor service that is accepting the proposal.
        proposal: The ``as_CaseProposal`` being accepted (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the report receiver URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Accept`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "accept_case_proposal_activity",
        as_Accept,
        at,
        lambda: {"actor": actor_id, "object_": proposal, "to": to, **kwargs},
    )


def reject_case_proposal_activity(
    actor_id: str,
    proposal: as_CaseProposal,
    to: list[str],
    *,
    at: datetime,
    **kwargs,
) -> as_Reject:
    """Build a ``Reject(CaseProposal)`` sent by the case-actor service.

    The case-actor service sends this when it declines the report receiver's proposal
    (CP-05-004).  The ``as_CaseProposal`` is embedded inline so the report receiver
    has full proposal context without an additional round-trip (CP-05-009).

    Args:
        actor_id: URI of the case-actor service that is rejecting the proposal.
        proposal: The ``as_CaseProposal`` being rejected (embedded inline as
            ``object_``).
        to: List of recipient URIs (typically the report receiver URI).
        **kwargs: Optional AS2 fields forwarded to the constructor.

    Returns:
        An ``as_Reject`` whose ``object_`` is the ``as_CaseProposal``.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    return build_activity(
        "reject_case_proposal_activity",
        as_Reject,
        at,
        lambda: {"actor": actor_id, "object_": proposal, "to": to, **kwargs},
    )
