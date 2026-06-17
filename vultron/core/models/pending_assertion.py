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
"""Actor-local in-memory pending-assertion store.

:class:`PendingAssertionStore` tracks outbound log-entry assertions that
have been emitted but not yet confirmed by a canonical
``Announce(CaseLedgerEntry)`` or ``Reject(CaseLedgerEntry)`` round-trip.
While an entry is *pending* and within the configurable timeout window,
duplicate re-emits for the same ``(case_id, event_type, object_id)`` triple
are suppressed.

This is **not** persisted and **not** a DataLayer entity.  The store is
intentionally ephemeral: entries are lost on actor restart (the catch-up
gate in #791 replays any unconfirmed log entries after restart).

Spec: SYNC-11-001 through SYNC-11-005.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

#: Default suppression window in seconds.
DEFAULT_PENDING_ASSERTION_TIMEOUT: float = 180.0

#: Module-level per-actor store registry.  Keyed by actor URI string.
#: Pure in-memory — no DataLayer interaction.
_STORES: dict[str, "PendingAssertionStore"] = {}


@dataclass
class PendingAssertion:
    """A single tracked outbound assertion awaiting canonical confirmation.

    Attributes:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        event_type: Machine-readable event descriptor (matches
            ``CaseLedgerEntry.event_type``).
        object_id: Full URI of the asserted activity or primary object
            (matches ``CaseLedgerEntry.log_object_id``).
        emitted_at: UTC timestamp when the assertion was emitted.
        status: Lifecycle state — ``"pending"``, ``"cleared"``,
            or ``"timed_out"``.
    """

    case_id: str
    event_type: str
    object_id: str
    emitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: Literal["pending", "cleared", "timed_out"] = "pending"


class PendingAssertionStore:
    """Actor-local in-memory store for outbound assertion tracking.

    Suppresses duplicate near-term re-emits while waiting for the canonical
    ``CaseLedgerEntry`` round-trip.  An entry is suppressed if its status is
    ``"pending"`` and it has not exceeded ``timeout_seconds``.

    Cleared when a matching ``Announce(CaseLedgerEntry)`` (disposition
    ``"recorded"`` or ``"rejected"``) arrives at the actor.  Timed-out entries
    are marked ``"timed_out"`` and no longer suppress future decisions.

    Setting ``timeout_seconds=0`` disables suppression entirely.

    Args:
        timeout_seconds: Suppression window in seconds.  Defaults to
            :data:`DEFAULT_PENDING_ASSERTION_TIMEOUT` (180 s).  Zero
            disables suppression.
    """

    def __init__(
        self, timeout_seconds: float = DEFAULT_PENDING_ASSERTION_TIMEOUT
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._store: dict[tuple[str, str, str], PendingAssertion] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(
        case_id: str, event_type: str, object_id: str
    ) -> tuple[str, str, str]:
        return (case_id, event_type, object_id)

    def _check_expired(self, entry: PendingAssertion) -> bool:
        """Return True and mark ``timed_out`` when the entry has expired.

        Only acts on ``"pending"`` entries; ``"cleared"`` and already
        ``"timed_out"`` entries are left unchanged.
        """
        if entry.status != "pending":
            return False
        now = datetime.now(timezone.utc)
        age = (now - entry.emitted_at).total_seconds()
        if age >= self.timeout_seconds:
            entry.status = "timed_out"
            logger.error(
                "pending_assertions: entry timed out after %.0fs "
                "case_id=%s event_type=%s object_id=%.32s…",
                age,
                entry.case_id,
                entry.event_type,
                entry.object_id,
            )
            return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, case_id: str, event_type: str, object_id: str) -> None:
        """Record a just-emitted assertion as *pending*.

        Overwrites any previous entry for the same triple so that a
        successful re-commit after a timeout resets the clock.

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            event_type: Machine-readable event descriptor.
            object_id: Full URI of the asserted activity or primary object.
        """
        key = self._key(case_id, event_type, object_id)
        self._store[key] = PendingAssertion(
            case_id=case_id,
            event_type=event_type,
            object_id=object_id,
        )
        logger.debug(
            "pending_assertions: added entry "
            "case_id=%s event_type=%s object_id=%.32s…",
            case_id,
            event_type,
            object_id,
        )

    def is_suppressed(
        self, case_id: str, event_type: str, object_id: str
    ) -> bool:
        """Return ``True`` iff a pending, unexpired entry exists.

        Zero ``timeout_seconds`` disables suppression (always returns
        ``False``).  Already-cleared or timed-out entries never suppress.

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            event_type: Machine-readable event descriptor.
            object_id: Full URI of the asserted activity or primary object.
        """
        if self.timeout_seconds == 0:
            return False
        key = self._key(case_id, event_type, object_id)
        entry = self._store.get(key)
        if entry is None:
            return False
        if self._check_expired(entry):
            return False
        return entry.status == "pending"

    def clear(self, case_id: str, event_type: str, object_id: str) -> None:
        """Mark a pending entry as *cleared* on canonical confirmation.

        A no-op when no matching entry exists or when the entry is already
        cleared / timed out.

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            event_type: Machine-readable event descriptor.
            object_id: Full URI of the asserted activity / primary object.
        """
        key = self._key(case_id, event_type, object_id)
        entry = self._store.get(key)
        if entry is None or entry.status != "pending":
            return
        entry.status = "cleared"
        logger.debug(
            "pending_assertions: cleared entry "
            "case_id=%s event_type=%s object_id=%.32s…",
            case_id,
            event_type,
            object_id,
        )

    def expire_timed_out(self) -> int:
        """Sweep the store and expire all overdue pending entries.

        Returns:
            Number of entries transitioned to ``"timed_out"`` this sweep.
        """
        count = sum(
            1 for e in list(self._store.values()) if self._check_expired(e)
        )
        return count

    def __len__(self) -> int:
        """Return the total number of tracked entries (all statuses)."""
        return len(self._store)


# ---------------------------------------------------------------------------
# Module-level per-actor registry (production convenience)
# ---------------------------------------------------------------------------


def get_pending_assertion_store(
    actor_id: str,
    timeout_seconds: float = DEFAULT_PENDING_ASSERTION_TIMEOUT,
) -> PendingAssertionStore:
    """Return (or lazily create) the per-actor :class:`PendingAssertionStore`.

    The returned store is the *singleton* for *actor_id* in this process.
    This is pure in-memory state — no DataLayer interaction.

    In unit tests, prefer constructing a :class:`PendingAssertionStore`
    directly and injecting it, then call :func:`_reset_stores` in a
    teardown fixture to prevent cross-test leakage.

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


def _reset_stores() -> None:
    """Clear the global per-actor store registry.

    **Test-only.**  Call from a teardown fixture to prevent cross-test
    leakage of pending-assertion state.
    """
    _STORES.clear()


__all__ = [
    "DEFAULT_PENDING_ASSERTION_TIMEOUT",
    "PendingAssertion",
    "PendingAssertionStore",
    "get_pending_assertion_store",
    "_reset_stores",
]
