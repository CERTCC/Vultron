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
"""Delivery-failure bookkeeping: attempt budgets and the dead letter.

A failed row is counted against its per-pass and total attempt budgets
(OX-13-001) and moved to the dead letter once exhausted, or at once when its
sealed body cannot be delivered at all (OX-13-002, OX-13-013).
"""

import logging

from vultron.adapters.driven.http_delivery import (
    DeliveryError,
)
from vultron.adapters.driving.fastapi.outbox_lanes import (
    RowOutcome,
)
from vultron.adapters.outbox_dead_letter import OutboxRetryStore
from vultron.adapters.outbox_sealed_body import (
    read_sealed_body_dict,
)
from vultron.core.ports.datalayer import DataLayer
from vultron.errors import (
    VultronOutboxObjectIntegrityError,
    VultronOutboxToFieldMissingError,
)

logger = logging.getLogger(__name__)


#: Maximum cumulative delivery attempts across all drain passes before an
#: activity is moved to the dead-letter store (OX-13-002).  Chosen as
#: (MAX_PER_PASS_ATTEMPTS + 1) × ~3 drain passes — survives transient failures
#: without running indefinitely.  See ADR-0066.
MAX_TOTAL_ATTEMPTS: int = 12


#: Maximum in-pass delivery attempts before a row is stalled for this pass
#: (OX-13-006, OX-13-010, OX-13-011).  A fourth failure stalls the row;
#: the row is deferred to the next drain pass without losing the item.
#: Keeping this below MAX_TOTAL_ATTEMPTS / ~3 drain passes guarantees the
#: total budget is not exhausted in a single pass.  See ADR-0066.
MAX_PER_PASS_ATTEMPTS: int = 3


#: Refusals raised by checking the sealed body itself (OX-08-003, OX-07-001).
#: The body never changes once sealed (VM-08-003), so a retry is refused the
#: same way: the row is dead-lettered on its first failure (OX-13-013).
UNDELIVERABLE_BODY_ERRORS: tuple[type[Exception], ...] = (
    VultronOutboxToFieldMissingError,
    VultronOutboxObjectIntegrityError,
)


def _resolve_ledger_entry_id(activity_id: str, dl: DataLayer) -> str | None:
    """Return the CaseLedgerEntry ID if *activity_id* is an Announce(CaseLedgerEntry).

    Reads the sealed body and extracts ``object.id`` when the inline object's
    type is ``"CaseLedgerEntry"``.  Returns ``None`` for all other activity
    types so non-ledger activities dead-letter unchanged (OX-14-001).

    The CaseLedgerEntry is always committed before its
    ``Announce(CaseLedgerEntry)`` fan-out is queued (SYNC-09-002), so the entry is always
    present when this function runs.
    """
    try:
        body = read_sealed_body_dict(dl, activity_id)
    except Exception:  # noqa: BLE001  # ruff-baseline #3326
        return None
    if body is None:
        return None
    obj = body.get("object")
    if not isinstance(obj, dict) or obj.get("type") != "CaseLedgerEntry":
        return None
    entry_id = obj.get("id")
    return entry_id if isinstance(entry_id, str) else None


def _bookkeep_failure(
    actor_id: str,
    activity_id: str,
    dl: DataLayer,
    retry: OutboxRetryStore,
    err_counts: dict[str, int],
    e: Exception,
) -> RowOutcome | None:
    """Record one failed attempt; return the row's outcome or ``None`` to retry."""
    failed_recipients: list[str] = (
        list(e.failed_recipients) if isinstance(e, DeliveryError) else []
    )
    total = retry.get_outbox_attempt_count(activity_id) + 1
    if isinstance(e, UNDELIVERABLE_BODY_ERRORS):
        logger.error(
            "Outbox item '%s' for actor '%s' refused: %s Moved to dead letter"
            " without retrying (OX-13-013).",
            activity_id,
            actor_id,
            e,
        )
        _dead_letter(
            activity_id,
            dl,
            retry,
            total,
            failed_recipients,
            reason="undeliverable_body",
        )
        return RowOutcome.DEAD_LETTERED
    if total >= MAX_TOTAL_ATTEMPTS:
        logger.error(
            "Activity '%s' exhausted %d delivery attempts for actor"
            " '%s'; moved to dead letter (OX-13-002)."
            " Failed recipients: %s",
            activity_id,
            total,
            actor_id,
            failed_recipients,
        )
        _dead_letter(
            activity_id,
            dl,
            retry,
            total,
            failed_recipients,
            reason="max_attempts_exhausted",
        )
        return RowOutcome.DEAD_LETTERED
    retry.set_outbox_attempt_count(activity_id, total)
    logger.error(
        "Error processing outbox item '%s' (attempt %d): %s",
        activity_id,
        total,
        e,
    )
    per_err = err_counts[activity_id] = err_counts.get(activity_id, 0) + 1
    if per_err > MAX_PER_PASS_ATTEMPTS:
        logger.error(
            "Too many errors for outbox item '%s',"
            " skipping for this pass (OX-13-006).",
            activity_id,
        )
        return RowOutcome.STALLED
    return None


def _dead_letter(
    activity_id: str,
    dl: DataLayer,
    retry: OutboxRetryStore,
    total: int,
    failed_recipients: list[str],
    reason: str,
) -> None:
    """Move the activity to the dead-letter store; it is never re-queued.

    Reached when the attempt budget is exhausted (``max_attempts_exhausted``,
    OX-13-002) or on the first refusal of a sealed body no retry can change
    (``undeliverable_body``, OX-13-013).
    """
    # Resolve the ledger entry being replicated, if any (OX-14-001).
    ledger_entry_id = _resolve_ledger_entry_id(activity_id, dl)
    retry.dead_letter_append(
        activity_id,
        reason=reason,
        total_attempts=total,
        failed_recipients=failed_recipients,
        ledger_entry_id=ledger_entry_id,
    )
    retry.clear_outbox_attempt_count(activity_id)
