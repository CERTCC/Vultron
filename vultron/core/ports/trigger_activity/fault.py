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


"""TriggerFaultPort: the fault part of
:class:`~vultron.core.ports.trigger_activity.TriggerActivityPort`.

Processing faults (NACK) and the CASE_MANAGER's refusal notices.
"""

from datetime import datetime
from typing import Any, Protocol


class TriggerFaultPort(Protocol):
    """Processing faults (NACK) and the CASE_MANAGER's refusal notices."""

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
        status assertion could not be processed (ASK-07-001, ADR-0080).

        Args:
            actor: URI of the receiving actor emitting the fault.
            failed_activity_id: URI of the failed activity (ASK-07-004).
            failure_class: URI identifying the failure class (ASK-07-005).
            to: Recipient list; SHOULD contain the original sender's URI.
            case_id: Optional case context URI for logging.

        Returns:
            The activity ID.
        """
        ...

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
        """Create and persist the CASE_MANAGER's refusal notice.

        The ``Reject`` a precondition guard's refusal owes the asserting
        participant (CLP-02-005, CLP-05-001, ADR-0141): ``refused_activity``
        is the refused activity in its AS2 JSON form, as recorded when
        received, carried inline; ``inReplyTo`` names its id; ``asserter``
        is the sole ``to`` recipient; ``reason`` is the refusing guard's
        reason, carried in ``summary``; ``case_id``, when given, is the
        notice's ``context``.  ``actor`` is the CASE_MANAGER.  The id is
        derived from the CASE_MANAGER and the refused activity, so one
        refused activity is answered by one notice (ID-04-004).
        ``expected_sender_sequence``, given for a refusal of the activity's
        ``senderSequence``, is the number the CASE_MANAGER expects next from
        the asserter, carried as ``expectedSenderSequence`` (SYNC-21-015).
        Returns ``(activity_id, activity_blob)``.
        """
        ...
