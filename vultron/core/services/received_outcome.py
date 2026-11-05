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

"""A received message's final outcome stage (ADR-0154, CLP-10-018).

A received message rests in one record while it is judged
(``received_holding.py`` owns the waiting), and leaves it only on its final
outcome.  This module owns the one outcome that changes what is kept:

- **applied** or **skipped** -- the record keeps the sealed body it already
  holds, and that is the archive (CLP-10-017).  Nothing here is called: the
  final stage is the one intake wrote.
- **refused** -- the body is given up for a :func:`write_receipt_stub`:
  who sent it, which message, when it arrived, why it was refused, and the
  digest of the body (CLP-10-018).
- **deferred** -- the message is still waiting, so ``received_holding.py``
  keeps it; nothing here is called.
- an **internal error** -- not an outcome at all.  The record is left exactly
  as it is, with its sealed body, so a resend or a re-run can run the act
  again from it (ADR-0151, ADR-0154).

Why the stub is written here and not by the handler: a refusal that dropped
the body inside the handling tree would take it from under the refusal notice
that embeds it (CLP-05-001).  The outcome stage runs after the tree, so the
notice reads the body and the stub replaces it.
"""

import logging

from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import held_received_record
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


def write_receipt_stub(
    dl: CasePersistence,
    activity_id: str,
    *,
    sender_id: str,
    reason: str,
) -> ReceivedActivityRecord:
    """Replace what is held for *activity_id* with a receipt stub.

    The stub keeps the receipt and gives up the message: *sender_id*, the
    activity id, the time of receipt the record already carries, *reason*,
    and the digest of the body (CLP-10-018, IE-10-002).  It is written under
    the same receiver-derived key, so the seen-before question is still one
    read of one row (DL-06-006).

    Idempotent: a stub already written is returned as it stands, so the
    reason recorded is the first refusal's (CLP-10-077).  That holds for a
    record that is still a stub when this is called.  Until the seen-before
    door runs ahead of intake, a resend of a refused message is archived over
    its stub first and judged again, so its own refusal writes a fresh stub
    with its own reason; #5045's third part answers that resend from the stub
    instead.

    A record that still owes a replay is returned unchanged: the body is the
    replay's to route (IO-03-009), and the held message reaches its own
    outcome when that replay runs (CLP-10-076).  This is not a fault, so it
    is logged at INFO and nothing is raised.

    Returns the stub, or the record as it stands when nothing is written.

    Raises:
        VultronWiringError: When nothing is held for *activity_id*, so there
            is no receipt to reduce, or when a body-bearing record holds no
            body, which the record's own invariant already refuses at the
            write.
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        raise VultronWiringError(
            f"refused activity '{activity_id}' is not held by this receiver,"
            " so there is no receipt to record: the outcome stage runs after"
            " intake, which holds every delivery (CLP-10-017, ADR-0154)"
        )
    if record.is_receipt_stub:
        logger.debug(
            "Received activity %s already has a receipt stub; the first"
            " refusal's reason stands.",
            activity_id,
        )
        return record
    if record.replay_owed:
        logger.info(
            "Refused delivery of activity '%s' leaves its held body: a replay"
            " is still owed from it, and that replay reaches its own outcome"
            " (IO-03-009, CLP-10-076).",
            activity_id,
        )
        return record
    body = record.received_body
    if body is None:
        raise VultronWiringError(
            f"received activity '{activity_id}' is {record.stage} with no"
            " body, so there is no digest to record for its refusal"
            " (VM-08-002)"
        )
    stub = ReceivedActivityRecord(
        activity_id=record.activity_id,
        stage=ReceivedStage.REFUSED,
        sender_id=sender_id,
        refusal_reason=reason,
        body_hash=received_body_digest(body),
        received_at=record.received_at,
    )
    dl.save(stub)
    logger.info(
        "Refused activity '%s' from '%s': the received body is given up for"
        " a receipt stub (CLP-10-018). Reason: %s",
        activity_id,
        sender_id,
        reason,
    )
    return stub


__all__ = ["write_receipt_stub"]
