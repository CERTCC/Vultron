#!/usr/bin/env python
"""Ingress storage for inbox activities.

Persists an inbound activity into the receiving actor's DataLayer before the
inbox pipeline dispatches it.  ``FastAPIIngressAdapter`` in
``inbox_orchestration`` is the caller.  The objects an activity carries
inline are not stored here: they are staged for routing only
(``inbox_staging``), and the handler writes any record they give rise to after
its guards (CLP-10-017, #3763).

These helpers live outside ``routers/`` on purpose: the router package imports
``inbox_orchestration`` (for ``run_inbox_pipeline``), so orchestration
importing back into the router package made a cycle that broke any import of
``inbox_orchestration`` that ran first (#3705).
"""

#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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

import logging

from vultron.adapters.driven.db_record import object_to_record
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import (
    VultronAlreadyExistsError,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity

# Same logger the helpers used under routers/actors/_inbox.py, so moving them
# does not move their records to a different handler.
logger = logging.getLogger("uvicorn.error")


def _store_inbox_activity(dl: DataLayer, activity: as_Activity) -> bool:
    """Store *activity*; return whether this call wrote it.

    ``False`` means a record under the same id was already held, so a later
    by-id read returns *that* record rather than this delivery.
    """
    try:
        dl.create(object_to_record(activity))
    except VultronAlreadyExistsError:
        logger.debug(
            "Activity %s already exists in shared DL; skipping re-store.",
            activity.id_,
        )
        return False
    return True
