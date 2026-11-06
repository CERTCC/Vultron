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
outcome.  This module owns the two outcomes that change what is kept:

- **applied** or **skipped** -- :func:`archive_applied` moves the ``HELD``
  record intake wrote to ``ARCHIVED``: the sealed body it holds becomes the
  archive (CLP-10-017, CLP-10-073).  The body is not rewritten.
- **refused** -- the body is given up for a :func:`write_receipt_stub`:
  who sent it, which message, when it arrived, why it was refused, and the
  digest of the body (CLP-10-018).  A delivery a door refused before intake
  ran has no record yet, so its stub is written from the delivery's own
  sealed body.
- **deferred** -- the message is still waiting, so ``received_holding.py``
  keeps it; nothing here is called.
- an **internal error** -- not an outcome at all.  The record is left exactly
  as it is, ``HELD`` with its sealed body, so a resend or a re-run can run
  the act again from it (ADR-0151, ADR-0154).

Why the stub is written here and not by the handler: a refusal that dropped
the body inside the handling tree would take it from under the refusal notice
that embeds it (CLP-05-001).  The outcome stage runs after the tree, so the
notice reads the body and the stub replaces it.
"""

import logging

from vultron.core.models.received_activity_record import (
    HOLDING_STAGES,
    ReceivedActivityRecord,
    ReceivedStage,
)
from vultron.core.models.received_body import received_body_digest
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.services.received_activity import (
    held_received_record,
    sealed_body_of,
)
from vultron.errors import VultronWiringError

logger = logging.getLogger(__name__)


def archive_applied(dl: CasePersistence, activity_id: str) -> None:
    """Archive the ``HELD`` record of an applied or skipped *activity_id*.

    The record keeps the sealed body it holds and moves to ``ARCHIVED``, so
    the archive holds only applied messages and a resend of one is skipped
    at its seen-before door (CLP-10-073, ADR-0154).  Nothing is written for:

    - no record: the handler ran no intake (a tree-less use case), so there
      is nothing to archive;
    - a record already at its outcome (an archive, a receipt stub): a resend
      the seen-before door answered leaves the first outcome standing;
    - a record still owed a replay: the message is waiting, and reaches its
      own outcome when that replay runs (CLP-10-076).
    """
    record = held_received_record(dl, activity_id)
    if (
        record is None
        or record.stage not in HOLDING_STAGES
        or record.replay_owed
    ):
        logger.debug(
            "Received activity %s: nothing to archive (%s)",
            activity_id,
            "not held" if record is None else record.stage,
        )
        return
    dl.save(record.model_copy(update={"stage": ReceivedStage.ARCHIVED}))
    logger.debug("Received activity %s archived as applied", activity_id)


def write_receipt_stub(
    dl: CasePersistence,
    activity_id: str,
    *,
    sender_id: str,
    reason: str,
    received_body: str | None = None,
) -> ReceivedActivityRecord:
    """Replace what is held for *activity_id* with a receipt stub.

    The stub keeps the receipt and gives up the message: *sender_id*, the
    activity id, the time of receipt, *reason*, and the digest of the body
    (CLP-10-018, IE-10-002).  It is written under the same receiver-derived
    key, so the seen-before question is still one read of one row
    (DL-06-006).

    A delivery a door refused before intake ran has no record: its stub is
    written from *received_body*, the delivery's own sealed body, with the
    time of receipt taken now.

    Idempotent: a stub already written is returned as it stands, so the
    reason recorded is the first refusal's (CLP-10-077).  An archived record
    is returned unchanged too: the message was applied, and the seen-before
    door answers a resend of it before anything could refuse it.

    A record that still owes a replay is returned unchanged: the body is the
    replay's to route (IO-03-009), and the held message reaches its own
    outcome when that replay runs (CLP-10-076).  This is not a fault, so it
    is logged at INFO and nothing is raised.

    Returns the stub, or the record as it stands when nothing is written.

    Raises:
        VultronWiringError: When nothing is held for *activity_id* and no
            *received_body* is given, so there is no digest to record
            (VM-08-002).
    """
    record = held_received_record(dl, activity_id)
    if record is None:
        if received_body is None:
            raise VultronWiringError(
                f"refused activity '{activity_id}' is not held by this"
                " receiver and its delivery carries no sealed body, so there"
                " is no digest to record for its refusal (VM-08-002,"
                " CLP-10-018)"
            )
        return _save_stub(
            dl,
            ReceivedActivityRecord(
                activity_id=activity_id,
                stage=ReceivedStage.REFUSED,
                sender_id=sender_id,
                refusal_reason=reason,
                body_hash=received_body_digest(received_body),
            ),
        )
    if record.stage not in HOLDING_STAGES:
        logger.debug(
            "Received activity %s is already %s; its first outcome stands.",
            activity_id,
            record.stage,
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
    return _save_stub(
        dl,
        ReceivedActivityRecord(
            activity_id=record.activity_id,
            stage=ReceivedStage.REFUSED,
            sender_id=sender_id,
            refusal_reason=reason,
            body_hash=received_body_digest(sealed_body_of(record)),
            received_at=record.received_at,
        ),
    )


def _save_stub(
    dl: CasePersistence, stub: ReceivedActivityRecord
) -> ReceivedActivityRecord:
    """Write *stub* and log the refusal it records (CLP-10-018)."""
    dl.save(stub)
    logger.info(
        "Refused activity '%s' from '%s': the received body is given up for"
        " a receipt stub (CLP-10-018). Reason: %s",
        stub.activity_id,
        stub.sender_id,
        stub.refusal_reason,
    )
    return stub


__all__ = ["archive_applied", "write_receipt_stub"]
