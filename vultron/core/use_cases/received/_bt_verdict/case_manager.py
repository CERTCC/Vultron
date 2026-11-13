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

"""The held-case refusal a handler still applies before its tree runs.

:func:`unheld_case_refusal` reads the DataLayer before the run, which the
runner never does; #6412 moves it into the tree as a factory door and
deletes it.  The CASE_MANAGER refusals that used to live here are now the
trees' own: a tree declares the manager path alone and its path stage
refuses any other receiver, or states the replica's refusal with
:class:`~vultron.core.behaviors.case.nodes.received_path.ReplicaRefusalNode`
(HP-01-005, HP-01-039, #6394).
"""

import logging

from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.receiving_actor import resolve_receiving_actor_id

logger = logging.getLogger(__name__)


def unheld_case_refusal(
    dl: CasePersistence, request: VultronEvent, case_id: str, label: str
) -> HandlerResult | None:
    """The refusal owed to an act that names a case this store does not hold.

    The receiving actor is resolved first, as the runner would resolve it, so
    a delivery with no resolvable receiver stays a wiring fault that raises
    before any read, never a refusal of the sender (BT-17-009, ARCH-15-001).

    ``Join``, ``Ignore`` and ``Leave`` of a case and the ownership-transfer
    ``Offer`` name their case and carry no copy of it (ADR-0165): the
    receiver reads every detail from the case it holds, so a case it does not
    hold leaves it nothing to act on, and the act is ``REFUSED`` naming the
    activity and the case.  ``None`` when the store holds the case.
    """
    resolve_receiving_actor_id(dl, request.receiving_actor_id)
    if dl.read_case(case_id) is not None:
        return None
    logger.warning(
        "%s '%s' names case '%s', which this actor does not hold — REFUSED",
        label,
        request.activity_id,
        case_id,
    )
    return HandlerResult.refused(
        f"{label} '{request.activity_id}' names unknown case '{case_id}'"
    )
