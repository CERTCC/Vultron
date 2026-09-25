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

- The **actor default** is a duration from a published ``EmbargoPolicy`` — a
  standing proposal.  It is a *candidate*, alongside any sender proposal.
- The **protocol default** is the configured fallback applied when the
  candidate set is empty.  It is never a candidate (EP-04-006) and never a
  minimum on agreed terms (EP-04-007).

Embargo eligibility (EP-04-008) is not decided here: a case with P/X/A set
never reaches duration resolution.  See ``InitializeDefaultEmbargoNode``.
"""

from collections.abc import Iterable
from datetime import timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vultron.core.models.embargo_policy import EmbargoPolicy


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


def select_actor_default(
    policies: Iterable[EmbargoPolicy],
) -> timedelta | None:
    """Return the actor default from *policies*, or ``None`` when none exist.

    Selection is deterministic regardless of store iteration order
    (EP-04-010): the shortest ``preferred_duration`` wins, per
    ``em/principles.md``'s "shortest duration possible", and ties fall to the
    lowest policy id.
    """
    ordered = sorted(policies, key=lambda p: (p.preferred_duration, p.id_))
    if not ordered:
        return None
    return ordered[0].preferred_duration


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
    # min() keeps the first of equal durations, so a tie resolves to the
    # sender's terms — the same duration either way.
    duration, source = min(candidates, key=lambda c: c[0])
    return InitialEmbargoDuration(duration=duration, source=source)


__all__ = [
    "EmbargoDurationSource",
    "InitialEmbargoDuration",
    "resolve_initial_embargo_duration",
    "select_actor_default",
]
