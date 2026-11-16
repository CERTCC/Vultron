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
from datetime import datetime
from typing import Any

from vultron.adapters.outbox_sealed_body import requeue_if_sealed
from vultron.core.models.activity_ids import derived_activity_id
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.errors import (
    VultronActivityConstructionError,
    VultronAlreadyExistsError,
)
from vultron.wire.as2.factories.fault import (
    create_processing_fault_activity,
    refusal_notice_activity,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

from ._base import _create_and_seal, _seal

logger = logging.getLogger(__name__)


class _FaultMixin:
    """Trigger activity methods for ProcessingFault NACKs and refusal notices."""

    _dl: CaseOutboxPersistence

    def emit_processing_fault(
        self,
        actor: str,
        failed_activity_id: str,
        failure_class: str,
        to: list[str],
        case_id: str | None = None,
        *,
        at: datetime,
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

        The activity id is derived from the failed activity and failure
        class, so a redelivery of the same failed activity emits nothing new
        and returns the id of the fault its first delivery sent (ID-04-004).
        The store, seal and queue append are one transaction.  A sealed fault
        that is no longer pending may have been delivered; the queue cannot
        say so.  It is queued again under the same id and body, which the
        receiver deduplicates, so a redelivery never loses the NACK
        (ID-04-005).

        Returns:
            The activity ID.
        """
        fault_id = derived_activity_id(
            "processing-fault", actor, failed_activity_id, failure_class
        )
        if requeue_if_sealed(self._dl, fault_id):
            logger.info(
                "ProcessingFault %s for failed activity %s was already"
                " emitted; not building it again",
                fault_id,
                failed_activity_id,
            )
            return fault_id
        fault = as_ProcessingFault(
            failure_class=failure_class,
            in_reply_to=failed_activity_id,
            published=at,
            updated=at,
        )
        activity = create_processing_fault_activity(
            actor=actor,
            fault=fault,
            to=to,
            id_=fault_id,
            at=at,
        )
        # One transaction: sealing signs the body (SIG-01-001), and a body
        # that cannot be signed fails again on every retry, so it must leave
        # no stored, unsealed fault behind.
        with self._dl.transaction():
            try:
                self._dl.create(activity)
            except VultronAlreadyExistsError:
                # Stored by an earlier build under the derived id; seal and
                # queue it as it stands.
                logger.info(
                    "ProcessingFault %s is already stored; sealing and"
                    " queueing it (ID-04-005)",
                    fault_id,
                )
            activity_id, _body = _seal(self._dl, activity)
            self._dl.outbox_append(activity_id)
        logger.debug(
            "Emitted Create(ProcessingFault) activity=%s"
            " actor=%s failed_activity=%s failure_class=%s to=%s",
            activity.id_,
            actor,
            failed_activity_id,
            failure_class,
            to,
        )
        return activity_id

    def refusal_notice(
        self,
        case_id: str | None,
        actor: str,
        refused_activity: dict[str, Any],
        asserter: str,
        reason: str,
        expected_sender_sequence: int | None = None,
        *,
        at: datetime,
    ) -> tuple[str, str]:
        """Create and persist the CASE_MANAGER's refusal notice (CLP-05-001).

        A ``Refuse`` of the refused activity, carried inline, threaded to it
        by ``inReplyTo``, addressed to *asserter* alone, with *reason* in
        ``summary`` and the case, when given, in ``context``.  The id is
        derived from the CASE_MANAGER and the refused activity, so a retry
        rebuilds the notice under the same id and the outbox queues it once
        (ID-04-004, OX-06-002).  A refusal of the activity's
        ``senderSequence`` names *expected_sender_sequence*, the number the
        CASE_MANAGER expects next, as ``expectedSenderSequence``
        (SYNC-21-015).

        Raises:
            VultronActivityConstructionError: *refused_activity* has no id or
                does not parse as an activity.
        """
        refused_id = refused_activity.get("id")
        if not isinstance(refused_id, str) or not refused_id:
            raise VultronActivityConstructionError(
                "refusal_notice: the refused activity has no id"
            )
        context: dict[str, Any] = (
            {} if case_id is None else {"context": case_id}
        )
        if expected_sender_sequence is not None:
            context["expected_sender_sequence"] = expected_sender_sequence
        activity = refusal_notice_activity(
            refused_activity,
            reason,
            actor=actor,
            to=[asserter],
            id_=derived_activity_id("refusal-notice", actor, refused_id),
            **context,
            at=at,
        )
        return _create_and_seal(self._dl, activity, "refusal_notice")
