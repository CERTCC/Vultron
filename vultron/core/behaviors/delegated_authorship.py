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

"""The one place a delegated activity's ``actor`` and ``attributed_to`` come from.

An activity the CASE_MANAGER emits on another participant's behalf carries the
CASE_MANAGER as ``actor`` (CM-24-001) and the participant who asked for it as
``attributed_to`` (CM-24-002).  Every path that does this — a trigger use case
or a received-side tree — gets the pair from :func:`delegated_authorship`
(CM-24-005).  The module sits under ``behaviors/`` so BT nodes and use cases
may both import it (BTND-04-003).

The caller supplies both identities.  The *doing* actor is the CASE_MANAGER
executing the role-gated tree (or, for a trigger, the role holder the use case
resolved); the *requesting* actor is the trigger's requester or the sender of
the activity the received tree acts on.  There is nothing to look up here and
no fallback arm: a case always has a CASE_MANAGER (CM-24-006), so a caller that
cannot name one fails before it reaches this helper.
"""

from typing import NamedTuple

from vultron.errors import VultronValidationError


class DelegatedAuthorship(NamedTuple):
    """Authorship of a delegated activity (CM-24-001, CM-24-002)."""

    actor: str
    attributed_to: str


def delegated_authorship(
    *, doing_actor_id: str, requesting_actor_id: str
) -> DelegatedAuthorship:
    """Return ``actor`` = who does what was asked, ``attributed_to`` = who asked.

    Raises:
        VultronValidationError: If either identity is empty.
    """
    for label, value in (
        ("doing_actor_id", doing_actor_id),
        ("requesting_actor_id", requesting_actor_id),
    ):
        if not value:
            raise VultronValidationError(
                f"delegated authorship needs a non-empty {label}"
            )
    return DelegatedAuthorship(
        actor=doing_actor_id, attributed_to=requesting_actor_id
    )


__all__ = ["DelegatedAuthorship", "delegated_authorship"]
