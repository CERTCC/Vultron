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

"""Parse-edge refusals for the ``Create(CaseProposal)`` envelope (CP-01-010).

The CASE_MANAGER reads the CASE_OWNER's actor default only from the actor
profile the proposer sends inline as the Create's ``actor``: it cannot read
the proposer's store (PCR-01-003) and must not fetch the profile.  So the
envelope's shape is checked where it arrives, and a proposal that cannot
supply that profile is refused naming the fault rather than created under a
default nobody stated (ADR-0032: validate at the edge).

The third CP-01-010 fault, a profile carrying another actor's
``embargoPolicy``, is refused by ``CoreActor`` itself when the parser
validates the inline profile (EP-01-001), so it needs no check here.
"""

from vultron.core.models.actor import CoreActor
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal


def _describe_actor(actor: object) -> str:
    """Name why ``actor`` is not an inline actor profile, for the refusal."""
    if isinstance(actor, str):
        return f"the actor is a reference ({actor!r})"
    href = getattr(actor, "href", None)
    if href is not None:
        return f"the actor is a Link reference ({href!r})"
    if type(actor) is CoreActor:
        return (
            f"the inline actor {actor.id_!r} has no actor type"
            " (Person, Organization, Service, Application or Group)"
        )
    kind = getattr(actor, "type_", None) or type(actor).__name__
    return (
        f"the actor {getattr(actor, 'id_', None)!r} has type {kind!r},"
        " not an actor profile"
    )


def refuse_malformed_case_proposal_envelope(activity: as_Activity) -> None:
    """Refuse a ``Create(CaseProposal)`` whose ``actor`` is not its proposer.

    Any other activity passes through untouched.

    Raises:
        VultronParseValidationError: when the ``actor`` is a reference, an
            inline object that is not an actor, or an untyped actor rather
            than an inline actor profile, or when the inline profile's ``id``
            differs from the proposal's ``attributedTo`` (CP-01-010).
    """
    if not isinstance(activity, as_Create):
        return
    proposal = activity.object_
    if not isinstance(proposal, as_CaseProposal):
        return
    actor = activity.actor
    if not isinstance(actor, CoreActor) or type(actor) is CoreActor:
        raise VultronParseValidationError(
            f"Create(CaseProposal) {activity.id_!r}: {_describe_actor(actor)};"
            " the proposer's full actor profile must be inline, because it"
            " carries the CASE_OWNER's embargo policy (CP-01-010)"
        )
    if actor.id_ != proposal.attributed_to:
        raise VultronParseValidationError(
            f"Create(CaseProposal) {activity.id_!r}: the inline actor profile"
            f" {actor.id_!r} differs from the proposal's attributedTo"
            f" {proposal.attributed_to!r}; the profile must be the"
            " proposer's own (CP-01-010)"
        )


__all__ = ["refuse_malformed_case_proposal_envelope"]
