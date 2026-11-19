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

"""The one place a delegated activity's authorship comes from.

An activity the CASE_MANAGER emits on another actor's behalf carries the
CASE_MANAGER as ``actor`` (CM-24-001), the actor that asked for it as
``attributed_to`` (CM-24-002) and the request it carries out as
``in_reply_to`` (CM-24-012, ADR-0199).  Every path that does this — a trigger
use case or a received-side tree — gets all three from
:func:`delegated_authorship` (CM-24-005).  The module sits under
``behaviors/`` so BT nodes and use cases may both import it (CM-24-013,
BTND-04-003).

The caller supplies the identities and the request.  The *doing* actor is
the CASE_MANAGER executing the role-gated tree (or, for a trigger, the role
holder the use case resolved); the *requesting* actor is the trigger's
requester or the sender of the activity the received tree acts on, and the
*request* is that received activity.  An actor that asks for its own act
does it directly: neither ``attributed_to`` nor ``in_reply_to`` is set
(ADR-0199).  A distinct asker reaches the CASE_MANAGER only by a message
(ADR-0109), so a delegated act always has a request to name, and a caller
that names none is a programming error, refused here.  There is nothing to
look up and no fallback arm (CM-24-008).
"""

from typing import NamedTuple

from vultron.errors import VultronValidationError, VultronWiringError
from vultron.primitives import same_actor_id


class DelegatedAuthorship(NamedTuple):
    """Authorship of a delegated activity (CM-24-001, CM-24-002, CM-24-012).

    ``attributed_to`` and ``in_reply_to`` are both ``None`` when the asker is
    the doer, and both set otherwise.
    """

    actor: str
    attributed_to: str | None
    in_reply_to: str | None


def delegated_authorship(
    *,
    doing_actor_id: str,
    requesting_actor_id: str,
    request_id: str | None,
) -> DelegatedAuthorship:
    """Return ``actor`` = who does it, ``attributed_to`` = who asked, and
    ``in_reply_to`` = the request it carries out.

    When the asker is the doer (compared with
    :func:`~vultron.primitives.same_actor_id`), the act is the doer's own:
    ``attributed_to`` and ``in_reply_to`` are ``None`` and *request_id* is
    not read.

    Raises:
        VultronValidationError: If either identity is empty.
        VultronWiringError: If the asker differs from the doer and
            *request_id* is empty or ``None``: the caller was composed
            without the request it carries out, a fault ``BTBridge`` reports
            as internal, never as a refusal of the sender (ADR-0095).
    """
    for label, value in (
        ("doing_actor_id", doing_actor_id),
        ("requesting_actor_id", requesting_actor_id),
    ):
        if not value:
            raise VultronValidationError(
                f"delegated authorship needs a non-empty {label}"
            )
    if same_actor_id(doing_actor_id, requesting_actor_id):
        return DelegatedAuthorship(
            actor=doing_actor_id, attributed_to=None, in_reply_to=None
        )
    if not request_id:
        raise VultronWiringError(
            f"'{doing_actor_id}' acts for '{requesting_actor_id}' but names no"
            " request it carries out: a delegated act answers the request it"
            " received (CM-24-012, ADR-0199)"
        )
    return DelegatedAuthorship(
        actor=doing_actor_id,
        attributed_to=requesting_actor_id,
        in_reply_to=request_id,
    )


__all__ = ["DelegatedAuthorship", "delegated_authorship"]
