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

"""Resolve the embargo duration a case is created with (EP-04, ADR-0096).

Two kinds of default exist and are kept apart here (EP-04-010):

- The **actor default** is the duration of the embargo policy the case
  owner's profile carries (EP-01-001) — a standing proposal.  It is a *candidate*, alongside any sender proposal.
- The **protocol default** is the configured fallback applied when the
  candidate set is empty.  It is never a candidate (EP-04-006) and never a
  minimum on agreed terms (EP-04-007).

Embargo eligibility (EP-04-008) is not decided here: a case with P/X/A set
never reaches duration resolution.  See ``InitializeDefaultEmbargoNode``.
"""

from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vultron.core.models.actor import CoreActor
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.embargo_ordering import earliest_ending
from vultron.errors import VultronNotFoundError


class EmbargoDurationSource(StrEnum):
    """Where a resolved initial embargo duration came from."""

    SENDER_PROPOSAL = "sender_proposal"
    ACTOR_DEFAULT = "actor_default"
    PROTOCOL_DEFAULT = "protocol_default"


class InitialEmbargoDuration(BaseModel):
    """A resolved initial embargo duration and the source it came from."""

    model_config = ConfigDict(frozen=True)

    duration: timedelta
    source: EmbargoDurationSource


def actor_default_duration(profile: CoreActor) -> timedelta | None:
    """Return *profile*'s actor default duration, or ``None`` (EP-04-010).

    The actor default is the ``preferred_duration`` of the embargo policy the
    profile carries inline (EP-01-001).  A profile with no policy has no actor
    default: ``None`` means "this actor published nothing", never the protocol
    default, which the caller supplies separately (EP-04-006).

    On the proposal path the profile is the one the proposer sent inline on
    ``Create(CaseProposal)`` and nothing else (CP-01-010); on the demo seeder's
    path it is the owner's own stored record (:func:`stored_actor_profile`).
    """
    policy = profile.embargo_policy
    if policy is None:
        return None
    return policy.preferred_duration


def stored_actor_profile(store: CasePersistence, actor_id: str) -> CoreActor:
    """Return *actor_id*'s own actor record from *store*.

    Raises:
        VultronNotFoundError: when *store* holds no actor record for
            *actor_id* — an actor default is read from a profile, so there is
            nothing to read it from.
    """
    record = store.read(actor_id)
    if not isinstance(record, CoreActor):
        raise VultronNotFoundError("Actor", actor_id)
    return record


def resolve_initial_embargo_duration(
    *,
    sender_proposal: timedelta | None,
    actor_default: timedelta | None,
    protocol_default: timedelta,
) -> InitialEmbargoDuration:
    """Resolve the duration an embargo-eligible case is created with.

    The sender proposal and the actor default are the candidates; the shorter
    becomes active (EP-04-003).  The protocol default applies only when there
    is no candidate at all (EP-04-005, EP-04-006), and a candidate shorter
    than it is honored as stated (EP-04-007).
    """
    candidates = [
        (duration, source)
        for duration, source in (
            (sender_proposal, EmbargoDurationSource.SENDER_PROPOSAL),
            (actor_default, EmbargoDurationSource.ACTOR_DEFAULT),
        )
        if duration is not None
    ]
    if not candidates:
        return InitialEmbargoDuration(
            duration=protocol_default,
            source=EmbargoDurationSource.PROTOCOL_DEFAULT,
        )
    # A tie keeps the first candidate, so it resolves to the sender's terms —
    # the same duration either way.  One comparator with EP-08 (#3470).
    duration, source = earliest_ending(candidates, end=lambda c: c[0])
    return InitialEmbargoDuration(duration=duration, source=source)


__all__ = [
    "EmbargoDurationSource",
    "InitialEmbargoDuration",
    "actor_default_duration",
    "resolve_initial_embargo_duration",
    "stored_actor_profile",
]
