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

"""The process-wide per-actor registry of pending-assertion stores.

Pure in-memory state, keyed by actor URI (SYNC-11-002).
"""

from __future__ import annotations

import logging
from datetime import datetime

from vultron.core.models.pending_assertion.store import (
    DEFAULT_PENDING_ASSERTION_TIMEOUT,
    PendingAssertionStore,
)

logger = logging.getLogger(__name__)


#: Module-level per-actor store registry.  Keyed by actor URI string.
#: Pure in-memory — no DataLayer interaction.
_STORES: dict[str, PendingAssertionStore] = {}


def get_pending_assertion_store(
    actor_id: str,
    timeout_seconds: float = DEFAULT_PENDING_ASSERTION_TIMEOUT,
) -> PendingAssertionStore:
    """Return (or lazily create) the per-actor :class:`PendingAssertionStore`.

    The returned store is the *singleton* for *actor_id* in this process.
    This is pure in-memory state — no DataLayer interaction.

    In unit tests, prefer constructing a :class:`PendingAssertionStore`
    directly and injecting it, then call
    :func:`reset_pending_assertion_stores` in a teardown fixture to prevent
    cross-test leakage.

    Args:
        actor_id: URI of the actor whose store to retrieve / create.
        timeout_seconds: Used only when creating a new store for this
            actor.  Ignored when the store already exists.
    """
    if actor_id not in _STORES:
        _STORES[actor_id] = PendingAssertionStore(
            timeout_seconds=timeout_seconds
        )
    return _STORES[actor_id]


def record_pending_assertion(
    actor_id: str,
    case_id: str,
    semantic_type: str,
    activity_id: str,
    subject_id: str | None = None,
) -> None:
    """Record an assertion *actor_id* just sent to the CASE_MANAGER.

    The one entry point every trigger that asks the manager instead of
    writing shared state uses (SYNC-11-002, ASK-04-008): the note trigger,
    the add-object and add-report triggers, the five embargo triggers (all
    through ``SvcBTTriggerBase._record_asserted_activity``) and the received
    P/X/A cascade's teardown ask
    (``SendTerminateEmbargoActivityNode``).  The matching
    ``Announce(CaseLedgerEntry)`` clears it (SYNC-11-003).
    """
    get_pending_assertion_store(actor_id).add(
        case_id, semantic_type, activity_id, subject_id=subject_id
    )
    logger.info(
        "Actor '%s' asserted '%s' on case '%s' to the CASE_MANAGER;"
        " pending its canonical commit (activity_id=%s)",
        actor_id,
        semantic_type,
        case_id,
        activity_id,
    )


def suppressed_repeat_reason(
    actor_id: str,
    case_id: str,
    semantic_type: str,
    subject_id: str,
    *,
    at: datetime,
) -> str | None:
    """Why a repeat ask about *subject_id* is suppressed, or ``None``.

    The one check every asker makes before sending (SYNC-11-002): the embargo
    triggers' ``SvcEmbargoTriggerBase._suppressed_duplicate()`` and the
    cascade's ``TeardownAskPendingNode`` read the same store with the same
    key, so an ask from either path suppresses a repeat from the other.
    ``None`` means nothing is pending: never asked, cleared by the announced
    commit (SYNC-11-003), or timed out (SYNC-11-005) — judged against *at*,
    the instant of the act the asker is performing, so this check reads no
    clock of its own (#5591).
    """
    pending = get_pending_assertion_store(actor_id).pending_for_subject(
        case_id, semantic_type, subject_id, at=at
    )
    if pending is None:
        return None
    return (
        f"actor '{actor_id}' already asked the CASE_MANAGER for"
        f" '{semantic_type}' about '{subject_id}' on case '{case_id}'"
        f" (activity_id={pending.object_id}, pending since"
        f" {pending.emitted_at.isoformat()}) — duplicate suppressed, not"
        " re-emitted (SYNC-11-002)"
    )


def reset_pending_assertion_stores() -> None:
    """Clear the global per-actor store registry.

    Call from a test teardown fixture to prevent cross-test leakage of
    pending-assertion state, and between two scenario runs that share a
    process: the registry is keyed by actor URI and the demo cast is fixed,
    so without this the second run inherits the first run's pending
    assertions and suppresses asks the scenario makes (#5591).
    """
    _STORES.clear()
