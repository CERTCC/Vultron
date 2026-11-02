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
duplicate re-emits for the same ``(case_id, semantic_type, object_id)`` triple
are suppressed.

This is **not** persisted and **not** a DataLayer entity.  The store is
intentionally ephemeral: entries are lost on actor restart (the catch-up
gate in #791 replays any unconfirmed log entries after restart).

**A lookup reads no clock; its caller supplies the instant.**  Every lookup
(:meth:`PendingAssertionStore.is_suppressed`,
:meth:`~PendingAssertionStore.pending_for_subject`,
:meth:`~PendingAssertionStore.clear_activity`) takes the instant it judges an
entry's age against, and applies the SYNC-11-005 timeout mark itself against
that instant.  Under the demo recording clock every clock read costs a 10 ms
tick, so a lookup that read the clock itself moved every later timestamp and
hash in the recording when it raced another thread (#5591).  The instant comes
from the act the caller is already performing — one read per act, taken
whether or not the lookup then suppresses anything — so the lookup's verdict
cannot move the clock and thread interleaving cannot move the verdict.

:meth:`~PendingAssertionStore.expire_timed_out` is the explicit sweep, and the
one method here that reads the clock; nothing depends on it for the timeout to
fire, because every lookup evaluates expiry.

Spec: SYNC-11-001 through SYNC-11-005.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from vultron.core.models._helpers import now_utc
from vultron.core.models.protocol_pair import ProtocolPair
from vultron.primitives import require_non_empty

logger = logging.getLogger(__name__)

#: Default suppression window in seconds.
DEFAULT_PENDING_ASSERTION_TIMEOUT: float = 180.0

#: Module-level per-actor store registry.  Keyed by actor URI string.
#: Pure in-memory — no DataLayer interaction.
_STORES: dict[str, PendingAssertionStore] = {}


#: ``result_out`` key a trigger tree's ask arm writes the queued activity id
#: to, for the trigger base to record as a pending assertion (SYNC-11-002).
ASSERTED_ACTIVITY_KEY = "asserted_activity_id"


@dataclass
class PendingAssertion:
    """A single tracked outbound assertion awaiting canonical confirmation.

    Attributes:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        semantic_type: The assertion's semantic type (matches
            ``CaseLedgerEntry.semantic_type``).
        object_id: Full URI of the asserted activity or primary object
            (matches ``CaseLedgerEntry.log_object_id``).
        emitted_at: UTC timestamp when the assertion was emitted.
        status: Lifecycle state — ``"pending"``, ``"cleared"``,
            or ``"timed_out"``.
        subject_id: What the assertion is *about*, when a repeat of it would
            carry a new activity id — the proposal an embargo answer names,
            the embargo a teardown ends, the terms a proposal offers.  A
            duplicate trigger is recognised by this, not by ``object_id``
            (SYNC-11-002).  ``None`` when the activity id is the subject.
    """

    case_id: str
    semantic_type: str
    object_id: str
    emitted_at: datetime = field(default_factory=now_utc)
    status: Literal["pending", "cleared", "timed_out"] = "pending"
    subject_id: str | None = None

    def __post_init__(self) -> None:
        # CS-08-001 for a stdlib dataclass: both ids are references.
        require_non_empty(self.case_id, "case_id")
        require_non_empty(self.object_id, "object_id")
        if self.subject_id is not None:
            require_non_empty(self.subject_id, "subject_id")


class PendingAssertionStore:
    """Actor-local in-memory store for outbound assertion tracking.

    Suppresses duplicate near-term re-emits while waiting for the canonical
    ``CaseLedgerEntry`` round-trip.  An entry suppresses while its status is
    ``"pending"``; exceeding ``timeout_seconds`` moves it to ``"timed_out"``.

    Cleared when a matching canonical ``Announce(CaseLedgerEntry)`` arrives at
    the actor.  Timed-out entries are marked ``"timed_out"`` and no longer
    suppress future decisions.

    **A lookup judges expiry against an instant its caller supplies** (#5591,
    see the module docstring).  :meth:`add` uses the instant it stamped on the
    new entry, :meth:`expire_timed_out` reads the clock, and every lookup
    takes an ``at`` argument; each applies the mark to whatever the instant
    shows is overdue.  No method here reads the clock except that sweep.

    Setting ``timeout_seconds=0`` disables suppression entirely.

    The store is keyed by :class:`~vultron.core.models.protocol_pair.ProtocolPair`
    (replacing the raw ``(case_id, semantic_type, object_id)`` tuple from earlier
    versions).  The three-argument helpers (``add``, ``is_suppressed``,
    ``clear``) remain for backward compatibility and construct a ``ProtocolPair``
    internally.

    Args:
        timeout_seconds: Suppression window in seconds.  Defaults to
            :data:`DEFAULT_PENDING_ASSERTION_TIMEOUT` (180 s).  Zero
            disables suppression.
    """

    def __init__(
        self, timeout_seconds: float = DEFAULT_PENDING_ASSERTION_TIMEOUT
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self._store: dict[ProtocolPair, PendingAssertion] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _key(case_id: str, semantic_type: str, object_id: str) -> ProtocolPair:
        return ProtocolPair(
            case_id=case_id,
            request_semantic_type=semantic_type,
            object_id=object_id,
        )

    def _overdue(self, entry: PendingAssertion, at: datetime) -> bool:
        """Whether *entry* is pending and *at* has reached its deadline.

        A pure predicate: it reads no clock, and leaves *entry* alone.  Zero
        ``timeout_seconds`` disables suppression, so it disables expiry with
        it — there is nothing to time out.

        The instant is named *at*, not *now*, because it frequently is not
        now: on the write path it is the stamp the new entry carries, and on
        a lookup it is the instant of the act the caller is performing.  That
        is already the name ``core/models`` uses for a supplied instant
        (``embargo_termination.has_reached_end_time``).  It also keeps the
        replica copy-only ratchet honest: that walk forbids the bare name
        ``now`` as a proxy for a clock read (CM-23-044, "MUST NOT ... read a
        clock") and follows a model method by name alone, so it over-follows
        on purpose (``test/architecture/_replica_slots.py``) and cannot tell
        a clock read from an injected instant.  The name is right on its own
        terms; the ratchet only agrees.
        """
        if self.timeout_seconds == 0 or entry.status != "pending":
            return False
        return (at - entry.emitted_at).total_seconds() >= self.timeout_seconds

    def _mark_overdue(self, at: datetime) -> int:
        """Mark every entry *at* shows is overdue ``"timed_out"`` (SYNC-11-005).

        The one path that applies the mark.  Every write, every lookup and
        the sweep call it with the instant they hold, so the timeout fires on
        whichever of them comes first and none of them reads the clock to do
        it (#5591).  The mark is sticky — :meth:`_overdue` answers ``False``
        for an entry that is no longer ``"pending"`` — so a later call with an
        earlier instant cannot put an expired entry back.

        Returns:
            How many entries this call moved to ``"timed_out"``.
        """
        overdue = [
            entry
            for entry in list(self._store.values())
            if self._overdue(entry, at)
        ]
        for entry in overdue:
            entry.status = "timed_out"
            logger.error(
                "pending_assertions: entry timed out after %.0fs "
                "case_id=%s semantic_type=%s object_id=%.32s…",
                (at - entry.emitted_at).total_seconds(),
                entry.case_id,
                entry.semantic_type,
                entry.object_id,
            )
        return len(overdue)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        case_id: str,
        semantic_type: str,
        object_id: str,
        subject_id: str | None = None,
    ) -> None:
        """Record a just-emitted assertion as *pending*.

        Overwrites any previous entry for the same triple so that a
        successful re-commit after a timeout resets the clock.

        The instant stamped on the new entry is also the instant every other
        entry's deadline is judged against, so a write marks what it finds
        overdue, as a lookup and the sweep do (#5591).

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            semantic_type: The assertion's semantic type.
            object_id: Full URI of the asserted activity or primary object.
            subject_id: What the assertion is about, when a repeat would
                carry a new activity id (see :class:`PendingAssertion`).
        """
        key = self._key(case_id, semantic_type, object_id)
        entry = PendingAssertion(
            case_id=case_id,
            semantic_type=semantic_type,
            object_id=object_id,
            subject_id=subject_id,
        )
        # Marked before the new entry joins the store, so an instant an
        # earlier caller supplied cannot time out the entry this write
        # created.
        self._mark_overdue(entry.emitted_at)
        self._store[key] = entry
        logger.debug(
            "pending_assertions: added entry "
            "case_id=%s semantic_type=%s object_id=%.32s…",
            case_id,
            semantic_type,
            object_id,
        )

    def is_suppressed(
        self,
        case_id: str,
        semantic_type: str,
        object_id: str,
        *,
        at: datetime,
    ) -> bool:
        """Return ``True`` iff a pending entry exists and has not aged out.

        Zero ``timeout_seconds`` disables suppression (always returns
        ``False``).  Already-cleared or timed-out entries never suppress, and
        an entry *at* shows is overdue is marked ``"timed_out"`` here and does
        not suppress (SYNC-11-005).

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            semantic_type: The assertion's semantic type.
            object_id: Full URI of the asserted activity or primary object.
            at: The instant to judge the entry's age against, from the act
                the caller is performing.  The lookup reads no clock of its
                own (#5591).
        """
        if self.timeout_seconds == 0:
            return False
        self._mark_overdue(at)
        key = self._key(case_id, semantic_type, object_id)
        entry = self._store.get(key)
        return entry is not None and entry.status == "pending"

    def pending_for_subject(
        self,
        case_id: str,
        semantic_type: str,
        subject_id: str,
        *,
        at: datetime,
    ) -> PendingAssertion | None:
        """Return the pending, unexpired assertion about *subject_id*, if any.

        The duplicate check for an assertion whose repeat would carry a new
        activity id (SYNC-11-002): the same embargo answer, teardown or terms
        asked for again inside the window.  Honours the timeout exactly as
        :meth:`is_suppressed` does — zero disables suppression, an entry *at*
        shows is overdue is marked ``"timed_out"`` and no longer matches, and
        the lookup reads no clock of its own (#5591).
        """
        if self.timeout_seconds == 0:
            return None
        self._mark_overdue(at)
        for entry in list(self._store.values()):
            if (
                entry.case_id == case_id
                and entry.semantic_type == semantic_type
                and entry.subject_id == subject_id
                and entry.status == "pending"
            ):
                return entry
        return None

    def clear(self, case_id: str, semantic_type: str, object_id: str) -> None:
        """Mark a pending entry as *cleared* on canonical confirmation.

        A no-op when no matching entry exists or when the entry is already
        cleared / timed out.

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            semantic_type: The assertion's semantic type.
            object_id: Full URI of the asserted activity / primary object.
        """
        key = self._key(case_id, semantic_type, object_id)
        entry = self._store.get(key)
        if entry is None or entry.status != "pending":
            return
        entry.status = "cleared"
        logger.debug(
            "pending_assertions: cleared entry "
            "case_id=%s semantic_type=%s object_id=%.32s…",
            case_id,
            semantic_type,
            object_id,
        )

    def clear_activity(
        self, case_id: str, activity_id: str, *, at: datetime
    ) -> list[PendingAssertion]:
        """Clear every pending entry for the asserted activity *activity_id*.

        The CASE_MANAGER's refusal notice names the refused activity, not the
        semantic type it would have been ledgered under, so this matches on the
        case and the activity alone (CLP-06-006, CLP-05-001).

        Args:
            case_id: URI of the parent :class:`VulnerabilityCase`.
            activity_id: The refused activity's id.

        An entry *at* shows is overdue is marked ``timed_out`` here and is not
        cleared: it was no longer pending.  Selecting the entries reads no
        clock of its own, as every lookup here does (#5591).

        Returns:
            The entries this call cleared; empty when none was pending.
        """
        self._mark_overdue(at)
        cleared = [
            entry
            for entry in list(self._store.values())
            if entry.case_id == case_id
            and entry.object_id == activity_id
            and entry.status == "pending"
        ]
        for entry in cleared:
            self.clear(entry.case_id, entry.semantic_type, entry.object_id)
        return cleared

    def expire_timed_out(self) -> int:
        """Sweep the store and expire all overdue pending entries.

        The one method here that reads the clock, for a caller that holds no
        instant of its own — an operator forcing a sweep, or the reap trigger
        of ASK-05-002 (#2887).  Nothing depends on it for the timeout to
        fire: every lookup judges expiry against the instant its caller
        supplies (#5591).

        Returns:
            Number of entries transitioned to ``"timed_out"`` this sweep.
        """
        return self._mark_overdue(now_utc())

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


__all__ = [
    "ASSERTED_ACTIVITY_KEY",
    "DEFAULT_PENDING_ASSERTION_TIMEOUT",
    "PendingAssertion",
    "PendingAssertionStore",
    "ProtocolPair",
    "get_pending_assertion_store",
    "record_pending_assertion",
    "reset_pending_assertion_stores",
]
