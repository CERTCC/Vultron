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

"""Whose replica a received message is applied to (BT-17-005, BT-17-009).

Lives in ``core/services`` so the received-tree runner in ``core/behaviors``
and the use cases share one answer (BTND-04-003).
"""

from vultron.core.ports.case_persistence import CasePersistence
from vultron.errors import VultronValidationError


def resolve_receiving_actor_id(
    dl: CasePersistence, receiving_actor_id: str | None
) -> str:
    """Return the actor whose replica a received message is being applied to.

    Received-side use cases need an executing actor identity to run their BT
    under (BT-17-005).  ``receiving_actor_id`` is set by the inbox adapter and
    is authoritative when present.  When it is absent — CLI dispatch, replay,
    tests — the answer is *the actor whose store we were handed*: under
    ADR-0073 a DataLayer is always some specific actor's own, and a received-
    side use case is by construction invoked with the receiving actor's store
    (CM-01-001).

    This replaces an ``or "unknown"`` fabrication that predated per-actor
    storage.  A synthetic identity used to be merely a mislabelled log line
    over a shared pool; now ``actor_id`` *selects the store*, so inventing one
    silently routes every read and write into an empty scratch store and the
    work is lost without an error (ARCH-15-001).

    Raises:
        VultronValidationError: If neither source yields an identity, since
            there is then no defensible answer to "whose replica is this?".
    """
    if receiving_actor_id:
        return receiving_actor_id
    own_actor_id = getattr(dl, "actor_id", None)
    if isinstance(own_actor_id, str) and own_actor_id:
        return own_actor_id
    raise VultronValidationError(
        "cannot resolve the receiving actor: the request carries no"
        " receiving_actor_id and the DataLayer reports no actor of its own,"
        " so there is no store this message could be applied to (CM-01-001)"
    )
