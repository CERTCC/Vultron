"""Factory functions for fault and refusal activities.

Provides :func:`create_processing_fault_activity` for building the
``Create(ProcessingFault)`` NACK message (ADR-0080, ASK-07-001), and
:func:`refusal_notice_activity` for the CASE_MANAGER's refusal notice, the
``Reject`` of an assertion a precondition guard refused (CLP-05-001,
ADR-0141).
"""

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
from typing import Any

from pydantic import ValidationError

from vultron.wire.as2.errors import VultronParseError
from vultron.wire.as2.factories._inline import require_inline
from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.activities.fault import _RefusalNoticeActivity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.processing_fault import as_ProcessingFault

logger = logging.getLogger(__name__)


def create_processing_fault_activity(
    actor: str,
    fault: as_ProcessingFault,
    to: list[str] | None = None,
    id_: str | None = None,
) -> as_Create:
    """Build a ``Create(ProcessingFault)`` NACK activity.

    Args:
        actor: URI of the receiving actor emitting the fault.
        fault: The ``as_ProcessingFault`` object describing the failure.
        to: Recipient URI list; SHOULD contain the original sender's URI.
        id_: Activity id to use instead of a freshly minted one, so a caller
            can derive it from the failed activity (ID-04-004).

    Returns:
        An ``as_Create`` activity wrapping the ``as_ProcessingFault``.

    Raises:
        VultronActivityConstructionError: If *fault* is not an inline
            ``as_ProcessingFault`` (AKM-02-004).
    """
    fault = require_inline(
        fault, as_ProcessingFault, factory="create_processing_fault_activity"
    )
    id_kwargs: dict[str, Any] = {} if id_ is None else {"id_": id_}
    return as_Create(actor=actor, object_=fault, to=to, **id_kwargs)


def refusal_notice_activity(
    refused: dict[str, Any],
    reason: str,
    **kwargs,
) -> as_Reject:
    """Build the CASE_MANAGER's refusal notice: a ``Reject`` of *refused*.

    The refused activity is carried inline, ``inReplyTo`` names its id and
    ``summary`` carries the refusing guard's reason (CLP-05-001).  The
    CASE_MANAGER is the notice's ``actor``; pass it, the asserting
    participant as the sole ``to`` recipient, and the derived ``id_``.

    Args:
        refused: The refused activity's received body, as the receiver
            archived it.  It is parsed, and embedded verbatim
            (``as_Activity.inlined_as_received``).
        reason: Why the precondition guard refused it.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``, ``id_``, ``context``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the refused activity.

    Raises:
        VultronActivityConstructionError: If *refused* is not an activity
            the vocabulary parses, or Pydantic validation fails.
    """
    try:
        activity = parse_activity(refused)
        return _RefusalNoticeActivity(
            # Embedded as the asserter sent it, every key included (DL-06-004).
            object_=activity.inlined_as_received(),
            in_reply_to=activity.id_,
            summary=reason,
            **kwargs,
        )
    except (ValidationError, VultronParseError) as exc:
        logger.warning("refusal_notice_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "refusal_notice_activity: invalid arguments"
        ) from exc
