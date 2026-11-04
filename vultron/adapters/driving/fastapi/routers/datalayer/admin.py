#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""Node-level datalayer operations, ``/admin/datalayer``."""

from fastapi import APIRouter, Depends

from vultron.adapters.driving.fastapi.deps import (
    get_hosted_actor_dls,
)
from vultron.core.ports.datalayer import DataLayer

#: Node-level operations that legitimately span every hosted actor.  These are
#: operator actions on the process (like a restart), not one actor reading
#: another's data through the protocol.
admin_router = APIRouter(prefix="/admin/datalayer", tags=["datalayer"])


@admin_router.delete(
    "/reset/",
    description=(
        "Resets this node by clearing the store of every actor it hosts."
    ),
    operation_id="datalayer_reset",
)
def reset_datalayer(
    actor_dls: dict[str, DataLayer] = Depends(get_hosted_actor_dls),
) -> dict:
    """Clear every hosted actor's store.

    A node-level operation: there is no single store to clear under ADR-0073,
    and demo scenarios reset a whole container between runs.  Kept off the
    actor-scoped router so that it cannot be mistaken for one actor reaching
    into another's data.

    Resetting does not *provision*.  An earlier ``init`` flag seeded the wire
    vocabulary's example actors here, which per-actor storage made unworkable in
    two independent ways: this loop iterates the actors the node already hosts,
    so on a clean node it has nothing to iterate and the seed silently never ran;
    and those example actors are named under ``https://vultron.example/users/…``,
    which is not ``{base_url}actors/{slug}`` and so can never be addressed on this
    node (ADR-0073#url-segment-computed-not-looked-up).  Provisioning an actor is ``POST /actors/``, and
    callers that need a populated node call it — see
    ``vultron.demo.utils.seed_exchange_actors``.

    The stores arrive via :func:`get_hosted_actor_dls` rather than a loop over
    ``get_datalayer``, so an app that supplied its own stores (a TestClient with
    per-actor in-memory overrides) is reset for real instead of having the
    process-global on-disk stores cleared behind it.
    """
    counts: dict[str, dict[str, int]] = {}
    for actor_id, actor_dl in actor_dls.items():
        actor_dl.clear_all()
        counts[actor_id] = actor_dl.count_all()

    return {
        "status": "datalayer reset successfully",
        "actors": len(counts),
        "n_items": counts,
    }
