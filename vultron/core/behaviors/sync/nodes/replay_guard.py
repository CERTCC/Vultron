#!/usr/bin/env python
#
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

"""Convergence guard for Reject-triggered ledger replay (SYNC-15-003).

A participant that cannot anchor its hash chain — typically a late joiner
missing the entries its replica needs — sends ``Reject(CaseLedgerEntry)`` for
every entry the CaseActor replays to it.  Because the reject handler responds
by replaying the missing suffix, this forms a self-sustaining amplification
loop: each Reject triggers a full-ledger replay, and each replayed entry
triggers another Reject.  Observed in CI as thousands of ``Announce`` activities
for a single case, starving the actor until unrelated DataLayer reads timed out.

The guard breaks the loop by tracking, per peer, the replication position of
the last replay actually sent.  A Reject that reports the *same* position as
the previous replay carries no new information, so replaying again cannot help
immediately and is rate-limited to at most one replay per
:data:`REPLAY_COOLDOWN_SECONDS`.  A Reject at an advanced position always
replays, so a peer that is making progress is never delayed.

The position is recorded (:func:`record_replay`) only after entries have really
been sent, separately from the decision to replay (:func:`should_replay`).  A
replay that sends nothing must not start a cooldown — see
:func:`record_replay`.

The cooldown is deliberately a rate limit rather than permanent suppression:
if a replayed entry is lost in transit, the peer's next Reject must eventually
be able to trigger a fresh replay, or the peer would stay permanently
un-synced.  Bounding the *rate* removes the storm while preserving eventual
convergence.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import cast

from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import CasePersistence

#: Minimum interval between replays sent to a peer that has not advanced its
#: replication position.  Long enough that a stuck peer cannot drive an event
#: storm, short enough that a genuinely dropped replay is retried promptly.
REPLAY_COOLDOWN_SECONDS: float = 30.0

#: Cooldown applied when the peer reports genesis (no entries at all).  Much
#: shorter than :data:`REPLAY_COOLDOWN_SECONDS` because a genesis peer is
#: mid-bootstrap (SYNC-15-002) and needs its history promptly, but still
#: non-zero so a peer that never anchors cannot drive an unbounded storm.
GENESIS_REPLAY_COOLDOWN_SECONDS: float = 2.0


def replay_from_hash(entries: list[CaseLedgerEntry], from_index: int) -> str:
    """Return the ``entry_hash`` a replay resumes from, or ``""`` for genesis.

    Args:
        entries: Case ledger entries sorted ascending by ``log_index``.
        from_index: Divergence index from ``FindDivergenceIndexNode``; ``-1``
            means the peer's acknowledged hash matched no known entry and the
            replay starts from the beginning.

    Returns:
        The ``entry_hash`` at *from_index*, or ``""`` when replaying from
        genesis or when *from_index* is not present in *entries*.
    """
    if from_index < 0:
        return ""
    for log_entry in entries:
        if log_entry.log_index == from_index:
            return log_entry.entry_hash
    return ""


def _read_state(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> VultronReplicationState | None:
    """Return the stored replication state for *peer_id*, or ``None``."""
    state_key = VultronReplicationState(case_id=case_id, peer_id=peer_id).id_
    existing = datalayer.read(state_key)
    if existing is None:
        return None
    return cast(VultronReplicationState, existing)


def should_replay(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    from_hash: str,
    log: logging.Logger | None = None,
    node_name: str = "SendMissingEntriesNode",
) -> bool:
    """Report whether a replay to *peer_id* should proceed.

    Read-only: the position is recorded by :func:`record_replay`, and only
    once entries have actually been sent.  Splitting the two matters — see
    that function's docstring.

    Args:
        datalayer: Persistence port holding the per-peer replication state.
        case_id: URI of the case being replicated.
        peer_id: URI of the peer that sent the Reject.
        from_hash: Replication position the replay would resume from, as
            returned by :func:`replay_from_hash`.
        log: Optional logger; a suppressed replay is logged at INFO so the
            storm-vs-stall distinction is visible in container logs.
        node_name: Name used as the log prefix.

    Returns:
        ``True`` when the replay should proceed — the peer's position has moved
        since the last replay we sent it, or the cooldown for an unchanged
        position has elapsed.  ``False`` when the position is unchanged and
        still within the cooldown, which is what breaks the amplification loop
        described in this module's docstring.

    Genesis (``from_hash == ""``) gets a much shorter cooldown
    (:data:`GENESIS_REPLAY_COOLDOWN_SECONDS`) rather than the full one.  A peer
    at genesis holds no entries at all, and convergence there is owned by
    ``AnnounceCaseOnGenesisRejectNode`` (SYNC-15-002), which seeds the
    VulnerabilityCase and then relies on the replay that follows to deliver the
    history.  Rate-limiting that replay as aggressively as a mid-chain stall
    would starve the bootstrap it exists to complete, leaving the peer with an
    empty replica — but leaving genesis wholly unbounded would re-admit the
    amplification loop, since a peer that cannot anchor its chain reports
    genesis on every Reject.  A short cooldown satisfies both: the bootstrap
    proceeds promptly while the storm stays bounded.

    Spec: SYNC-15-003.
    """
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    if state is None or state.last_replayed_at is None:
        return True
    if state.last_replayed_from_hash != from_hash:
        return True
    cooldown = (
        GENESIS_REPLAY_COOLDOWN_SECONDS
        if from_hash == ""
        else REPLAY_COOLDOWN_SECONDS
    )
    if _now_utc() - state.last_replayed_at >= timedelta(seconds=cooldown):
        return True
    if log is not None:
        log.info(
            "%s: peer '%s' re-Rejected at unchanged position %.16s… for case"
            " '%s'; rate-limiting duplicate replay (SYNC-15-003)",
            node_name,
            peer_id,
            from_hash or "genesis",
            case_id,
        )
    return False


def record_replay(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    from_hash: str,
) -> None:
    """Record that entries were replayed to *peer_id* from *from_hash*.

    Call this only after at least one entry has actually been sent.  A replay
    that sends nothing — the peer's acknowledged position is already the ledger
    tail — must not update the recorded position: doing so would start a
    cooldown against a position at which we have never delivered anything, so a
    later Reject at that same position, once the ledger has grown and a genuine
    suffix is missing, would be suppressed for no reason.  The peer would wait
    out the cooldown having received nothing, which is the stall this guard
    exists to prevent.

    Spec: SYNC-15-003.
    """
    now = _now_utc()
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    if state is None:
        datalayer.save(
            VultronReplicationState(
                case_id=case_id,
                peer_id=peer_id,
                last_replayed_from_hash=from_hash,
                last_replayed_at=now,
            )
        )
        return
    state.last_replayed_from_hash = from_hash
    state.last_replayed_at = now
    state.updated_at = now
    datalayer.save(state)
