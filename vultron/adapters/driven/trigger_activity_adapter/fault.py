"""ProcessingFault trigger activity construction for TriggerActivityAdapter."""

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

import logging

from vultron.core.ports.case_persistence import CaseOutboxPersistence
from vultron.wire.as2.factories.fault import create_processing_fault_activity
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

logger = logging.getLogger(__name__)


class _FaultMixin:
    """Trigger activity methods for ProcessingFault NACK messages."""

    _dl: CaseOutboxPersistence

    def emit_processing_fault(
        self,
        actor: str,
        failed_activity_id: str,
        failure_class: str,
        to: list[str],
        case_id: str | None = None,
    ) -> str:
        """Create and persist a ``Create(ProcessingFault)`` NACK activity.

        Sent by the receiving actor to the authenticated sender when a
        status assertion cannot be processed (ASK-07-001, ADR-0080).

        Args:
            actor: URI of the receiving actor emitting the fault.
            failed_activity_id: URI of the activity that could not be processed.
            failure_class: URI identifying the failure class (ASK-07-005).
            to: Recipient list; SHOULD contain the original sender's URI.
            case_id: Optional case context URI (not included in the fault per
                ASK-07-006, but available for logging).

        Returns:
            The activity ID.
        """
        fault = as_ProcessingFault(
            failure_class=failure_class,
            in_reply_to=failed_activity_id,
        )
        activity = create_processing_fault_activity(
            actor=actor,
            fault=fault,
            to=to,
        )
        self._dl.create(activity)
        self._dl.outbox_append(activity.id_)
        logger.debug(
            "Emitted Create(ProcessingFault) activity=%s"
            " actor=%s failed_activity=%s failure_class=%s to=%s",
            activity.id_,
            actor,
            failed_activity_id,
            failure_class,
            to,
        )
        return activity.id_
