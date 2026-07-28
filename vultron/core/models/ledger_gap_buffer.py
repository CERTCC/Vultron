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
"""Actor-local in-memory buffer for out-of-order ``Announce(CaseLedgerEntry)``.

Because ``Announce(CaseLedgerEntry)`` activities are delivered over a
transport that provides **no ordering guarantee** (and Vultron may not be the
only protocol implementation on the wire), a participant replica can receive a
ledger entry before its hash-chain predecessor arrives.  Dropping such an entry
(as the bare reject-on-mismatch path does) makes convergence depend on a
reject → replay round-trip that may itself reorder — so under adversarial
delivery an entry can be permanently lost.

:class:`LedgerGapBuffer` holds those *forward-gap* entries and lets the receive
path drain them in hash-chain order once their predecessor lands, making
convergence **order-independent** (issue #1556, SYNC-10-004).

Design:

- **Keyed on ``prev_log_hash``** (the entry's upstream "tooth").  The successor
  of a just-persisted entry is exactly ``buffer[new_tail.entry_hash]`` — an
  O(1) lookup, so a cascade of *k* contiguous buffered entries drains in O(k).
- **Actor-local, per-case, in-memory** — mirrors
  :class:`~vultron.core.models.pending_assertion.PendingAssertionStore`.  It is
  **not** persisted and **not** a DataLayer entity: SYNC-13 defines presence of
  a ``CaseLedgerEntry`` in the DataLayer to mean "effects applied and entry
  committed", so a not-yet-appliable entry MUST live in a clearly separate,
  non-ledger holding area (SYNC-13-003).  Buffered entries are lost on restart;
  the catch-up gate (SYNC-10) re-syncs any gap after restart.
- **Size-bounded** — a broken or hostile peer could stream unbounded
  far-future entries, so the buffer caps its size and evicts the entry farthest
  ahead of the gap (highest ``log_index``) with a WARNING.  Recovery of an
  evicted entry is covered by the ``Reject(CaseLedgerEntry)`` that the receive
  path still sends when it buffers, so eviction never has to re-trigger
  recovery itself.

Spec: SYNC-10-004, SYNC-12-001, SYNC-13-003.
"""

from __future__ import annotations

import logging

from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry

logger = logging.getLogger(__name__)

#: Default maximum number of buffered forward-gap entries per (actor, case).
#: Sized generously relative to any realistic in-flight reorder window while
#: still bounding memory against a misbehaving peer.
DEFAULT_LEDGER_GAP_BUFFER_MAX: int = 256

#: Module-level per-actor registry.  Keyed by actor URI string.  Pure
#: in-memory — no DataLayer interaction (mirrors ``pending_assertion._STORES``).
_BUFFERS: dict[str, "LedgerGapBuffer"] = {}


class LedgerGapBuffer:
    """Actor-local, per-case store of out-of-order ledger entries.

    Entries are keyed by ``prev_log_hash`` within each ``case_id`` so that the
    successor of a newly persisted tail can be found in O(1).

    Args:
        max_entries: Maximum number of buffered entries per case before the
            farthest-ahead entry is evicted.  Defaults to
            :data:`DEFAULT_LEDGER_GAP_BUFFER_MAX`.  A non-positive value
            disables buffering entirely (every :meth:`buffer` call is dropped),
            which restores the legacy drop-on-mismatch behaviour.
    """

    def __init__(
        self, max_entries: int = DEFAULT_LEDGER_GAP_BUFFER_MAX
    ) -> None:
        self.max_entries = max_entries
        # case_id -> {prev_log_hash -> entry}
        self._by_case: dict[str, dict[str, VultronCaseLedgerEntry]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def buffer(self, entry: VultronCaseLedgerEntry) -> bool:
        """Hold *entry* until its hash-chain predecessor arrives.

        Keyed by ``entry.prev_log_hash``.  If an entry is already buffered
        under the same predecessor hash, the new one replaces it only when the
        content hash differs (a fork/rewrite under a misbehaving peer), logged
        at WARNING; an exact duplicate is a no-op.

        When the per-case buffer is full, the entry farthest ahead of the gap
        (highest ``log_index``) is evicted with a WARNING before the new entry
        is stored — unless the new entry is itself the farthest ahead, in which
        case it is dropped.

        Args:
            entry: The forward-gap :class:`VultronCaseLedgerEntry` to hold.

        Returns:
            ``True`` if the entry is now buffered; ``False`` if buffering is
            disabled or the entry was dropped by the size bound.
        """
        if self.max_entries <= 0:
            return False

        case_map = self._by_case.setdefault(entry.case_id, {})

        existing = case_map.get(entry.prev_log_hash)
        if existing is not None and existing.entry_hash == entry.entry_hash:
            return True  # exact duplicate — already held
        if existing is not None:
            logger.warning(
                "ledger_gap_buffer: replacing forked buffered entry for case "
                "%s prev_log_hash=%.16s… (old index=%d, new index=%d)",
                entry.case_id,
                entry.prev_log_hash,
                existing.log_index,
                entry.log_index,
            )

        if (
            existing is None
            and len(case_map) >= self.max_entries
            and not self._evict_farthest(case_map, entry)
        ):
            return False

        case_map[entry.prev_log_hash] = entry
        logger.debug(
            "ledger_gap_buffer: buffered out-of-order entry for case %s "
            "(index=%d, prev_log_hash=%.16s…); buffer depth=%d",
            entry.case_id,
            entry.log_index,
            entry.prev_log_hash,
            len(case_map),
        )
        return True

    def take_next(
        self, case_id: str, tail_hash: str
    ) -> VultronCaseLedgerEntry | None:
        """Pop and return the buffered successor of *tail_hash*, if any.

        The successor is the entry whose ``prev_log_hash == tail_hash`` — an
        O(1) dict lookup.  Returns ``None`` when no buffered entry extends the
        given tail.

        Args:
            case_id: URI of the case whose buffer to drain.
            tail_hash: ``entry_hash`` of the replica's current chain tail.
        """
        case_map = self._by_case.get(case_id)
        if not case_map:
            return None
        entry = case_map.pop(tail_hash, None)
        if entry is not None and not case_map:
            # Drop the now-empty per-case sub-dict to keep the buffer tidy.
            self._by_case.pop(case_id, None)
        return entry

    def depth(self, case_id: str) -> int:
        """Return the number of entries currently buffered for *case_id*."""
        return len(self._by_case.get(case_id, {}))

    def __len__(self) -> int:
        """Return the total number of buffered entries across all cases."""
        return sum(len(m) for m in self._by_case.values())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _evict_farthest(
        case_map: dict[str, VultronCaseLedgerEntry],
        incoming: VultronCaseLedgerEntry,
    ) -> bool:
        """Evict the buffered entry with the highest ``log_index``.

        Returns ``True`` if room was made for *incoming*; ``False`` when
        *incoming* is itself the farthest-ahead entry (so it is dropped rather
        than evicting a closer-to-gap entry that is more likely to drain soon).
        """
        farthest_key, farthest = max(
            case_map.items(), key=lambda kv: kv[1].log_index
        )
        if incoming.log_index >= farthest.log_index:
            logger.warning(
                "ledger_gap_buffer: buffer full for case %s (max=%d); "
                "dropping incoming far-future entry index=%d",
                incoming.case_id,
                len(case_map),
                incoming.log_index,
            )
            return False
        case_map.pop(farthest_key, None)
        logger.warning(
            "ledger_gap_buffer: buffer full for case %s (max=%d); evicted "
            "farthest-ahead entry index=%d to make room for index=%d",
            incoming.case_id,
            len(case_map) + 1,
            farthest.log_index,
            incoming.log_index,
        )
        return True


# ---------------------------------------------------------------------------
# Module-level per-actor registry (production convenience)
# ---------------------------------------------------------------------------


def get_ledger_gap_buffer(
    actor_id: str,
    max_entries: int = DEFAULT_LEDGER_GAP_BUFFER_MAX,
) -> LedgerGapBuffer:
    """Return (or lazily create) the per-actor :class:`LedgerGapBuffer`.

    The returned buffer is the *singleton* for *actor_id* in this process.
    This is pure in-memory state — no DataLayer interaction.

    In unit tests, prefer constructing a :class:`LedgerGapBuffer` directly and
    injecting it, then call :func:`_reset_buffers` in a teardown fixture to
    prevent cross-test leakage.

    Args:
        actor_id: URI of the actor whose buffer to retrieve / create.
        max_entries: Used only when creating a new buffer for this actor.
            Ignored when the buffer already exists.
    """
    if actor_id not in _BUFFERS:
        _BUFFERS[actor_id] = LedgerGapBuffer(max_entries=max_entries)
    return _BUFFERS[actor_id]


def _reset_buffers() -> None:
    """Clear the global per-actor buffer registry.

    **Test-only.**  Call from a teardown fixture to prevent cross-test leakage
    of buffered-entry state.
    """
    _BUFFERS.clear()


__all__ = [
    "DEFAULT_LEDGER_GAP_BUFFER_MAX",
    "LedgerGapBuffer",
    "get_ledger_gap_buffer",
    "_reset_buffers",
]
