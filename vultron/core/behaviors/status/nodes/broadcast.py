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

"""Case-manager lookup helper used by the status lifecycle nodes.

The raw peer re-broadcast step (step 3 of DEMOMA-07-003) was removed in
DEMOMA-07-005; ``Announce(CaseLedgerEntry)`` fan-out in
``_commit_log_cascade_bt`` already propagates status updates to all
participants.

:func:`_find_case_manager_id` remains here because
:mod:`vultron.core.behaviors.status.nodes.lifecycle` uses it to resolve
the Case Manager actor ID for auto-close fan-out.
"""

import logging
from typing import TYPE_CHECKING, Any

from vultron.core.states.roles import CVDRole

if TYPE_CHECKING:
    from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


def _find_case_manager_id(dl: "CasePersistence", case: Any) -> str | None:
    """Return the attributed_to actor ID for the CASE_MANAGER participant."""
    for p_id in case.actor_participant_index.values():
        p = dl.read(p_id)
        if p is None:
            continue
        roles = getattr(p, "case_roles", [])
        if CVDRole.CASE_MANAGER in roles:
            attr = getattr(p, "attributed_to", None)
            if attr:
                return str(attr)
    return None
