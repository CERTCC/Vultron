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
and is suppressed.  A Reject at an advanced position replays normally, so a
peer that is making progress is never wedged.
"""

from __future__ import annotations

from typing import cast

from vultron.core.models._helpers import _now_utc
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.ports.case_persistence import CasePersistence


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


def claim_replay_position(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    from_hash: str,
) -> bool:
    """Record a replay to *peer_id* and report whether it should proceed.

    Args:
        datalayer: Persistence port holding the per-peer replication state.
        case_id: URI of the case being replicated.
        peer_id: URI of the peer that sent the Reject.
        from_hash: Replication position the replay would resume from, as
            returned by :func:`replay_from_hash`.

    Returns:
        ``True`` when the peer's position has moved since the last replay we
        sent it (replay should proceed), ``False`` when the position is
        unchanged and the replay must be suppressed to avoid the amplification
        loop described in this module's docstring.

    Spec: SYNC-15-003.
    """
    state_key = VultronReplicationState(case_id=case_id, peer_id=peer_id).id_
    existing = datalayer.read(state_key)
    if existing is None:
        datalayer.save(
            VultronReplicationState(
                case_id=case_id,
                peer_id=peer_id,
                last_replayed_from_hash=from_hash,
            )
        )
        return True

    state = cast(VultronReplicationState, existing)
    if state.last_replayed_from_hash == from_hash:
        return False

    state.last_replayed_from_hash = from_hash
    state.updated_at = _now_utc()
    datalayer.save(state)
    return True
