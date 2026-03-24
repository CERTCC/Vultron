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

"""Delivery queue driven adapter — stub.

Implements the ``ActivityEmitter`` port (``core/ports/emitter.py``) by
queuing outbound ActivityStreams activities for delivery to recipient actor
inboxes.

Responsibilities (future implementation):

- For local recipients (actors on the same server), write the activity
  directly to the recipient actor's inbox collection in the DataLayer
  (OX-04-001, OX-04-002).
- For remote recipients, enqueue an HTTP POST via
  ``adapters/driven/http_delivery.py`` (OX-05-001; PROD_ONLY).
- Ensure idempotency: delivering the same activity twice MUST NOT create
  duplicate inbox entries (OX-06-001).

This adapter is a stub.  The ``emit`` method logs a placeholder message and
returns without performing any delivery.  It exists to establish the port
contract and the module structure before OX-1.1 implements the body.

Port: ``vultron.core.ports.emitter.ActivityEmitter``
"""

import logging

from vultron.core.models.activity import VultronActivity
from vultron.core.ports.emitter import (  # noqa: F401 — port reference
    ActivityEmitter,
)

logger = logging.getLogger(__name__)


class DeliveryQueueAdapter:
    """Stub implementation of the ``ActivityEmitter`` driven port.

    OX-1.1 will replace the placeholder body with real local-delivery logic.
    """

    def emit(
        self,
        activity: VultronActivity,
        recipients: list[str],
    ) -> None:
        logger.debug(
            "DeliveryQueueAdapter.emit: activity=%s recipients=%s (not yet implemented)",
            getattr(activity, "as_id", None),
            recipients,
        )
