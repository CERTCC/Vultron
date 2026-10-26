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
"""Pause and backfill a peer's ledger stream under the embargo gate.

The CM-10-004 content gate cannot redact a hash-chained ledger for one
recipient, and skipping a single entry does not work either: the replica
Rejects to request the gap (SYNC-14-002) and replay would send it. So the
gate *pauses* the whole stream for a withheld participant, replay included
(CM-10-005), and records in that peer's ``VultronReplicationState`` the first
``log_index`` it withheld (``embargo_paused_from_index``).

When the gate admits the participant — it accepts the active embargo, or the
embargo ends — every entry from that index on is sent in log order through the
same suffix send the replay uses (:func:`send_ledger_suffix`), and the pause is
cleared (CM-10-006). Admission is caught at two points:

- **at fan-out** — the send node backfills an admitted peer before sending it
  the new entry, which covers a state change that precedes its own commit:
  ``terminate_embargo_bt`` (the terminate trigger and the CS.P/X/A and threat
  cascades) ends the embargo, then ``EmitCaseStatusUpdateNode`` commits the
  new case status;
- **after an admitting effect** — ``BackfillAdmittedParticipantsNode`` runs
  behind the received Accept, Remove or ``Add(EmbargoEvent)`` effect, because
  a received activity is committed (and fanned out) *before* its effect admits
  anyone (CLP-10-006).

Who is withheld is the shared selection's answer
(:mod:`vultron.core.participants.recipients`, CM-10-007): a peer that is not an
active participant gets no case content, and only a joined peer that is not
active — the active embargo withholds it, or it was removed (CM-31-001) — has
its stream paused (``inactive_joined_participants``).

Helpers here raise on a broken invariant and never return ``None`` in place of
a failure (BT-HELPER-01).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import NamedTuple

from vultron.core.behaviors.sync.nodes.replay_guard import _read_state
from vultron.core.behaviors.sync.nodes.verified_send import (
    send_verified_log_entry,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.replication_state import VultronReplicationState
from vultron.core.participants.recipients import (
    case_content_recipients,
    closed_participant_ledger_cutoff,
    inactive_joined_participants,
    is_case_content_recipient,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort

# Re-exported: replay, post-close and the pending-request reader import it here.
from vultron.core.sync_helpers import sorted_case_ledger_entries
from vultron.errors import VultronError, VultronUnverifiedLedgerEntryError

logger = logging.getLogger(__name__)


class LedgerSuffixSend(NamedTuple):
    """What :func:`send_ledger_suffix` queued.

    ``sent`` rows were queued and ``already_pending`` rows the port declined
    because it already held them for the peer (SYNC-15-012).  ``held_back``
    is the error for the entry the send stopped at because its hash did not
    verify, or ``None`` when every entry in range was checked and offered to
    the port (SYNC-03-009).
    """

    sent: int
    already_pending: int
    held_back: VultronUnverifiedLedgerEntryError | None = None


def send_ledger_suffix(
    sync_port: SyncActivityPort,
    entries: Iterable[CaseLedgerEntry],
    *,
    after_index: int,
    actor_id: str,
    peer_id: str,
    through_index: int | None = None,
) -> LedgerSuffixSend:
    """Send each entry with ``after_index < log_index <= through_index`` to *peer_id*.

    *entries* MUST be sorted ascending by ``log_index``; they go out in that
    order. ``through_index=None`` sends through the ledger tail.

    The sync port declines to queue a row it already holds for this peer and
    says so (SYNC-15-012), so the result separates the two.

    Each entry goes through :func:`send_verified_log_entry`.  The send stops
    at the first entry whose hash does not verify: that entry and every
    later one stay unsent, the hold-back is logged at ERROR, and the result
    carries it in ``held_back`` so the calling node returns ``FAILURE``
    (SYNC-03-009, BT-14-001).  A replica could hold an entry after the
    broken one only as a forward gap (SYNC-14-001).
    """
    sent = 0
    skipped = 0
    for log_entry in entries:
        if log_entry.log_index <= after_index:
            continue
        if through_index is not None and log_entry.log_index > through_index:
            break
        try:
            queued = send_verified_log_entry(
                sync_port,
                log_entry,
                actor_id=actor_id,
                to=[peer_id],
            )
        except VultronUnverifiedLedgerEntryError as exc:
            logger.error(  # noqa: TRY400 -- the hold-back is the report, no trace
                "ledger send to '%s' stopped after %d entries: %s",
                peer_id,
                sent,
                exc,
            )
            return LedgerSuffixSend(sent, skipped, held_back=exc)
        if queued:
            sent += 1
        else:
            skipped += 1
    return LedgerSuffixSend(sent, skipped)


def embargo_paused_from_index(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> int | None:
    """Return the first ``log_index`` withheld from *peer_id*, or ``None``."""
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    if state is None:
        return None
    return state.embargo_paused_from_index


def record_embargo_pause(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    from_index: int,
) -> None:
    """Record that the gate withheld entries from *peer_id* starting at *from_index*.

    A pause already on record keeps the earlier index: the backfill must start
    with the *first* entry withheld (CM-10-006), not the latest.
    """
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    if state is None:
        datalayer.save(
            VultronReplicationState(
                case_id=case_id,
                peer_id=peer_id,
                embargo_paused_from_index=from_index,
            )
        )
        logger.info(
            "embargo gate: paused ledger stream to '%s' for case '%s' from"
            " log_index=%d (CM-10-005)",
            peer_id,
            case_id,
            from_index,
        )
        return
    current = state.embargo_paused_from_index
    if current is not None and current <= from_index:
        return
    state.embargo_paused_from_index = from_index
    datalayer.save(state)
    logger.info(
        "embargo gate: paused ledger stream to '%s' for case '%s' from"
        " log_index=%d (CM-10-005)",
        peer_id,
        case_id,
        from_index,
    )


def clear_embargo_pause(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> None:
    """Clear *peer_id*'s pause once everything withheld from it has been sent."""
    state = _read_state(datalayer, case_id=case_id, peer_id=peer_id)
    if state is None or state.embargo_paused_from_index is None:
        return
    state.embargo_paused_from_index = None
    datalayer.save(state)


def _require_case(
    datalayer: CasePersistence, case_id: str, peer_id: str
) -> VulnerabilityCase:
    case = datalayer.read(case_id)
    if not isinstance(case, VulnerabilityCase):
        raise VultronError(
            f"embargo gate: case '{case_id}' not found; cannot decide whether"
            f" '{peer_id}' may receive its content"
        )
    return case


def peer_is_withheld(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> bool:
    """Report whether *peer_id* is denied *case_id*'s content (CM-10-004).

    True for any peer that is not an active participant
    (:func:`is_case_content_recipient`), whatever the reason.

    Raises:
        VultronError: *case_id* does not resolve to a case in *datalayer*. A
            send that is about to answer for this case's content cannot decide
            the gate without it.
    """
    case = _require_case(datalayer, case_id, peer_id)
    return not is_case_content_recipient(case, datalayer, peer_id)


def closed_peer_cutoff(
    datalayer: CasePersistence,
    *,
    case_id: str,
    peer_id: str,
    entries: Iterable[CaseLedgerEntry],
) -> int | None:
    """Return the last ``log_index`` a closed *peer_id* may be sent (CM-23-004).

    ``None`` when *peer_id* is not at RM ``CLOSED``.  Otherwise the index of
    the last entry in *entries* that records its own closure, ``-1`` when
    none does (:func:`~vultron.core.participants.recipients
    .closed_participant_ledger_cutoff`).

    Raises:
        VultronError: *case_id* does not resolve to a case in *datalayer*.
    """
    case = _require_case(datalayer, case_id, peer_id)
    return closed_participant_ledger_cutoff(case, datalayer, peer_id, entries)


def peer_is_inactive_joined(
    datalayer: CasePersistence, *, case_id: str, peer_id: str
) -> bool:
    """Report whether *peer_id* is a joined peer that is not active (CM-10-005).

    Such a peer's stream is paused, to be backfilled on admission
    (CM-10-006).  A removed joined peer is paused the same way
    (``inactive_joined_participants``); a peer that has not joined is not.

    Raises:
        VultronError: *case_id* does not resolve to a case in *datalayer*.
    """
    case = _require_case(datalayer, case_id, peer_id)
    return peer_id in inactive_joined_participants(case, datalayer)


def backfill_admitted_peers(
    datalayer: CasePersistence,
    case: VulnerabilityCase,
    *,
    sync_port: SyncActivityPort,
    actor_id: str,
    through_index: int | None = None,
) -> list[str]:
    """Backfill every paused peer the gate now admits, then clear its pause.

    For each active participant of *case* (other than *actor_id*) whose
    stream is paused, send every canonical entry from the first one withheld
    through *through_index* (``None``: the ledger tail) in log order, through
    :func:`send_ledger_suffix` — the replay's own send (CM-10-006).

    Args:
        datalayer: The CASE_MANAGER's store, which holds the canonical ledger
            and the per-peer replication state.
        case: The case being replicated.
        sync_port: The port that queues ``Announce(CaseLedgerEntry)``.
        actor_id: The executing CASE_MANAGER, which sends the entries.
        through_index: Last ``log_index`` to backfill. The fan-out passes the
            index just before the entry it is about to send, so the backfill
            arrives in order *before* it.

    Returns:
        The peers backfilled, in index order.

    Raises:
        VultronUnverifiedLedgerEntryError: a peer's backfill stopped at an
            entry whose hash does not verify (SYNC-03-009).  The entries
            before it were queued and the hold-back logged at ERROR by
            :func:`send_ledger_suffix`; that peer keeps its pause, and no
            later peer is backfilled.
        VultronError: *case* cannot be resolved to decide the gate.
    """
    # Admission is decided over the whole case, never from a caller's
    # withheld list: a fan-out collector filters (e.g. RM.CLOSED peers)
    # before it gates, so its withheld list would read a filtered-out peer
    # as admitted.
    entries: list[CaseLedgerEntry] | None = None
    backfilled: list[str] = []
    for peer_id in case_content_recipients(
        case, datalayer, excluding={actor_id}
    ):
        paused_from = embargo_paused_from_index(
            datalayer, case_id=case.id_, peer_id=peer_id
        )
        if paused_from is None:
            continue
        if entries is None:
            entries = sorted_case_ledger_entries(datalayer, case.id_)
        sent, skipped, held_back = send_ledger_suffix(
            sync_port,
            entries,
            after_index=paused_from - 1,
            through_index=through_index,
            actor_id=actor_id,
            peer_id=peer_id,
        )
        if held_back is not None:
            # SYNC-03-009: the pause stays, since the peer still lacks the
            # held-back entry and everything after it.
            raise held_back
        clear_embargo_pause(datalayer, case_id=case.id_, peer_id=peer_id)
        backfilled.append(peer_id)
        logger.info(
            "embargo gate: admitted '%s' to case '%s'; backfilled %d entries"
            " from log_index=%d (%d already pending in outbox — SYNC-15-012)"
            " (CM-10-006)",
            peer_id,
            case.id_,
            sent,
            paused_from,
            skipped,
        )
    return backfilled
