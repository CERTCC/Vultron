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

"""Pure predicates over actor identifiers and activity addressing.

The inbox adapter canonicalises ``receiving_actor_id`` to the actor's full
URI, but the ids a sender writes into ``to``/``cc`` arrive as written.  Exact
string comparison therefore fails for an Offer that *was* delivered to this
actor whenever the sender spelled the id with a trailing slash (HP-09-001,
#2667).

Normalisation deliberately stops at the trailing slash.  A bare slug such as
``vendor`` names an actor under *some* authority, not necessarily this one, so
matching it against a full URI would accept mail addressed to another host's
``vendor``.

Import constraints
------------------
This module MUST NOT import from ``vultron.core.behaviors``,
``vultron.core.use_cases``, or ``vultron.core.services``.
"""

from collections.abc import Iterable, Mapping

# Defined in ``vultron.primitives`` so the wire extractor and the received
# event model can use them too (ARCH-22-001, OID-01-007); re-exported here,
# where core's addressing predicates have always been imported from.
from vultron.primitives import normalise_actor_id, same_actor_id

__all__ = [
    "distinct_recipients",
    "is_addressed_to",
    "normalise_actor_id",
    "participant_id_for_actor",
    "same_actor_id",
]


def participant_id_for_actor(
    actor_participant_index: Mapping[str, str], actor_id: str
) -> str | None:
    """Return the participant id *actor_participant_index* holds for *actor_id*.

    The keys are compared with :func:`same_actor_id`, so a key written with a
    trailing slash still names *actor_id*.  ``None`` means the actor has no
    participant in the index, as ``dict.get`` would say.
    """
    return next(
        (
            participant_id
            for key, participant_id in actor_participant_index.items()
            if same_actor_id(key, actor_id)
        ),
        None,
    )


def is_addressed_to(actor_id: str, recipients: Iterable[str]) -> bool:
    """Return True when *actor_id* appears among *recipients*.

    Membership uses :func:`same_actor_id`, so a recipient written with a
    trailing slash still addresses *actor_id*.
    """
    target = normalise_actor_id(actor_id)
    return any(normalise_actor_id(r) == target for r in recipients)


def distinct_recipients(recipients: Iterable[str | None]) -> list[str]:
    """Return the actors *recipients* names, once each, in order.

    Ids are normalised with :func:`normalise_actor_id`, so two spellings that
    differ only by a trailing slash count once; ``None`` and empty ids are
    dropped.  The invitee of an ``Invite(EmbargoEvent)`` is its sole ``to``
    recipient (EP-09-010): it has one exactly when this returns one id.
    """
    return list(dict.fromkeys(normalise_actor_id(r) for r in recipients if r))
