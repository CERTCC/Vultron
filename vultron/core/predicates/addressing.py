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

from collections.abc import Iterable


def _normalise_actor_id(actor_id: str) -> str:
    return actor_id.rstrip("/")


def same_actor_id(a: str, b: str) -> bool:
    """Return True when *a* and *b* identify the same actor.

    The two differ at most by a trailing slash.
    """
    return _normalise_actor_id(a) == _normalise_actor_id(b)


def is_addressed_to(actor_id: str, recipients: Iterable[str]) -> bool:
    """Return True when *actor_id* appears among *recipients*.

    Membership uses :func:`same_actor_id`, so a recipient written with a
    trailing slash still addresses *actor_id*.
    """
    target = _normalise_actor_id(actor_id)
    return any(_normalise_actor_id(r) == target for r in recipients)
