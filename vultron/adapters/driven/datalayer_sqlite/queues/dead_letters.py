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

"""The outbox and inbox dead-letter stores (OX-13-003, IE-06-004).

An item that exhausts its attempt budget is moved here, in its owning
actor's store.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from vultron.adapters.outbox_dead_letter import (
    InboxDeadLetterEntry,
    OutboxDeadLetterEntry,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle broken for typing only
    # ``datalayer`` imports this module to build its own methods, so the name
    # can only be a forward reference here.  It was ``Any``, which said nothing
    # about the ``_engine`` attribute every function below reaches for
    # (CS-11-001 forbids an unjustified ``Any``).
    from ..datalayer import SqliteDataLayer


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dead-letter store (OX-13-002, OX-13-004)
# ---------------------------------------------------------------------------


def dead_letter_append(
    dl: "SqliteDataLayer",
    activity_id: str,
    reason: str,
    total_attempts: int,
    failed_recipients: list[str],
    ledger_entry_id: str | None = None,
    *,
    recorded_at: datetime,
) -> None:
    """Write an exhausted outbox activity to this actor's dead-letter store.

    Constructs an :class:`OutboxDeadLetterEntry` and persists it via
    ``dl.save()`` so that operators can inspect it without log access
    (OX-13-002).

    ``entry.actor_id`` is taken from ``dl.actor_id`` rather than from a
    parameter.  The entry describes *this* actor's failed delivery attempt, and
    under ADR-0073 the store already fixes whose outbox that was — so there is
    no second identity to pass and none to get wrong.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity that exhausted its delivery budget.
        reason: Short machine-readable reason code.
        total_attempts: Total cumulative attempt count at exhaustion.
        failed_recipients: Actor IDs that could not be reached.
        ledger_entry_id: ID of the ``CaseLedgerEntry`` the activity was
            replicating, or ``None`` for non-ledger activities (OX-14-001).
        recorded_at: When the store recorded it, from its bookkeeping clock
            (ADR-0176).
    """
    actor = dl.actor_id
    entry = OutboxDeadLetterEntry(
        activity_id=activity_id,
        actor_id=actor,
        reason=reason,
        total_attempts=total_attempts,
        failed_recipients=list(failed_recipients),
        ledger_entry_id=ledger_entry_id,
        recorded_at=recorded_at,
    )
    dl.save(entry)
    logger.debug(
        "dead_letter_append: stored OutboxDeadLetterEntry for activity '%s'"
        " (actor '%s', attempts=%d)",
        activity_id,
        actor,
        total_attempts,
    )


def dead_letter_list(
    dl: "SqliteDataLayer",
) -> list[OutboxDeadLetterEntry]:
    """Return this actor's dead-letter entries (OX-13-004).

    Reconstructs :class:`OutboxDeadLetterEntry` objects from the raw dicts
    stored in ``vultron_objects``.  Only this actor's entries are visible: a
    node-wide operator view must fan out over
    :func:`~vultron.adapters.driven.actor_hosts.hosted_actor_ids` and call this
    per actor.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of :class:`OutboxDeadLetterEntry` objects in no guaranteed order.
    """
    raw = dl.by_type("OutboxDeadLetterEntry")
    entries: list[OutboxDeadLetterEntry] = []
    for data in raw.values():
        try:
            entries.append(OutboxDeadLetterEntry.model_validate(data))
        except Exception:  # noqa: BLE001  # ruff-baseline #3326
            logger.warning(
                "dead_letter_list: could not reconstruct OutboxDeadLetterEntry"
                " from stored data: %r",
                data,
            )
    return entries


# ---------------------------------------------------------------------------
# Inbox dead-letter store (IE-06-008)
# ---------------------------------------------------------------------------


def inbox_dead_letter_append(
    dl: "SqliteDataLayer",
    activity_id: str,
    reason: str,
    total_attempts: int,
    last_error: str = "",
    *,
    recorded_at: datetime,
) -> None:
    """Write an exhausted inbox activity to this actor's dead-letter store.

    Constructs an :class:`InboxDeadLetterEntry` and persists it via
    ``dl.save()`` so that operators can inspect it without log access
    (IE-06-004).  ``entry.actor_id`` is taken from ``dl.actor_id``.

    Args:
        dl: The SqliteDataLayer instance.
        activity_id: ID of the activity that exhausted its retry budget.
        reason: Short machine-readable reason code.
        total_attempts: Total cumulative attempt count at exhaustion.
        last_error: String representation of the last exception raised.
        recorded_at: When the store recorded it, from its bookkeeping clock
            (ADR-0176).
    """
    actor = dl.actor_id
    entry = InboxDeadLetterEntry(
        activity_id=activity_id,
        actor_id=actor,
        reason=reason,
        total_attempts=total_attempts,
        last_error=last_error,
        recorded_at=recorded_at,
    )
    dl.save(entry)
    logger.debug(
        "inbox_dead_letter_append: stored InboxDeadLetterEntry for activity '%s'"
        " (actor '%s', attempts=%d)",
        activity_id,
        actor,
        total_attempts,
    )


def inbox_dead_letter_list(
    dl: "SqliteDataLayer",
) -> list[InboxDeadLetterEntry]:
    """Return this actor's inbox dead-letter entries (IE-06-008).

    Reconstructs :class:`InboxDeadLetterEntry` objects from the raw dicts
    stored in ``vultron_objects``.

    Args:
        dl: The SqliteDataLayer instance.

    Returns:
        List of :class:`InboxDeadLetterEntry` objects in no guaranteed order.
    """
    raw = dl.by_type("InboxDeadLetterEntry")
    entries: list[InboxDeadLetterEntry] = []
    for data in raw.values():
        try:
            entries.append(InboxDeadLetterEntry.model_validate(data))
        except Exception:  # noqa: BLE001  # ruff-baseline #3326
            logger.warning(
                "inbox_dead_letter_list: could not reconstruct"
                " InboxDeadLetterEntry from stored data: %r",
                data,
            )
    return entries
