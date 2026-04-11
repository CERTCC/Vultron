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
"""Trigger helpers for SYNC-2: commit a log entry and fan it out to peers.

Public entry point: :func:`commit_log_entry_trigger`.

Spec: SYNC-02-002, SYNC-02-003, SYNC-03-001.
"""

from __future__ import annotations

import logging
from typing import Any

from vultron.core.models.case_log import CaseLogEntry
from vultron.core.models.case_log_entry import VultronCaseLogEntry
from vultron.core.models.protocols import is_case_model
from vultron.core.ports.datalayer import DataLayer
from vultron.core.use_cases._helpers import case_addressees
from vultron.core.use_cases.received.sync import _reconstruct_tail_hash
from vultron.core.use_cases.triggers._helpers import add_activity_to_outbox
from vultron.wire.as2.vocab.activities.sync import AnnounceLogEntryActivity

logger = logging.getLogger(__name__)


def _to_persistable_entry(
    chain_entry: CaseLogEntry,
) -> VultronCaseLogEntry:
    """Convert a hash-chained :class:`CaseLogEntry` to a :class:`VultronCaseLogEntry`.

    Copies all fields so that the entry can be stored via the DataLayer.
    """
    return VultronCaseLogEntry(
        case_id=chain_entry.case_id,
        log_index=chain_entry.log_index,
        disposition=chain_entry.disposition,
        term=chain_entry.term,
        log_object_id=chain_entry.object_id,
        event_type=chain_entry.event_type,
        payload_snapshot=dict(chain_entry.payload_snapshot),
        prev_log_hash=chain_entry.prev_log_hash,
        entry_hash=chain_entry.entry_hash,
        reason_code=chain_entry.reason_code,
        reason_detail=chain_entry.reason_detail,
    )


def _fan_out_log_entry(
    case_id: str,
    entry: VultronCaseLogEntry,
    actor_id: str,
    dl: DataLayer,
) -> None:
    """Create one ``Announce(CaseLogEntry)`` per peer and queue for delivery.

    Reads the case from the DataLayer to get the participant list.
    Participants other than *actor_id* (the CaseActor) each receive their
    own outbox activity.

    Spec: SYNC-02-002.
    """
    case_obj = dl.read(case_id)
    if not is_case_model(case_obj):
        logger.warning(
            "sync fan-out: case '%s' not found or not a VulnerabilityCase — "
            "skipping fan-out for log entry '%s'",
            case_id,
            entry.id_,
        )
        return

    recipients = case_addressees(case_obj, excluding_actor_id=actor_id)
    if not recipients:
        logger.debug(
            "sync fan-out: no other participants for case '%s' — "
            "log entry '%s' not forwarded",
            case_id,
            entry.id_,
        )
        return

    for recipient_id in recipients:
        announce = AnnounceLogEntryActivity(
            actor=actor_id,
            object_=entry,
            to=[recipient_id],
        )
        dl.save(announce)
        add_activity_to_outbox(actor_id, announce.id_, dl)
        logger.info(
            "sync fan-out: queued Announce(CaseLogEntry) '%s' → '%s'",
            announce.id_,
            recipient_id,
        )


def commit_log_entry_trigger(
    case_id: str,
    object_id: str,
    event_type: str,
    actor_id: str,
    dl: DataLayer,
    payload_snapshot: dict[str, Any] | None = None,
    term: int | None = None,
    reason_code: str | None = None,
    reason_detail: str | None = None,
    disposition: str = "recorded",
) -> VultronCaseLogEntry:
    """Commit a new log entry to the local chain and fan it out to peers.

    Reconstructs the current chain tail from the DataLayer, appends the new
    entry via :class:`~vultron.core.models.case_log.CaseEventLog`, converts
    to a :class:`~vultron.core.models.case_log_entry.VultronCaseLogEntry`,
    persists it, and fans it out to all case participants via
    ``Announce(CaseLogEntry)`` activities.

    Args:
        case_id: URI of the parent :class:`VulnerabilityCase`.
        object_id: URI of the asserted activity or primary object.
        event_type: Short machine-readable event descriptor.
        actor_id: URI of the CaseActor performing the commit.
        dl: DataLayer instance for persistence and outbox access.
        payload_snapshot: Optional normalised payload snapshot.
        term: Optional Raft cluster term (single-node → ``None``).
        reason_code: Required when *disposition* is ``"rejected"``.
        reason_detail: Optional human-readable rejection detail.
        disposition: ``"recorded"`` (default) or ``"rejected"``.

    Returns:
        The newly created and persisted :class:`VultronCaseLogEntry`.

    Spec: SYNC-02-002, SYNC-02-003, SYNC-03-001.
    """
    tail_hash, tail_index = _reconstruct_tail_hash(case_id, dl)

    # Create the new entry directly using CaseLogEntry so the entry_hash is
    # auto-computed by the model_validator.  We do not use CaseEventLog.append()
    # here because that always starts a fresh log at index 0; we carry forward
    # the DataLayer state via tail_hash and tail_index instead.
    chain_entry = CaseLogEntry(
        case_id=case_id,
        log_index=tail_index + 1,
        object_id=object_id,
        event_type=event_type,
        disposition=disposition,  # type: ignore[arg-type]
        payload_snapshot=payload_snapshot or {},
        prev_log_hash=tail_hash,
        term=term,
        reason_code=reason_code,
        reason_detail=reason_detail,
    )

    entry = _to_persistable_entry(chain_entry)
    dl.save(entry)

    logger.info(
        "sync: committed log entry '%s' for case '%s' "
        "(log_index=%d, event_type=%s)",
        entry.id_,
        case_id,
        entry.log_index,
        event_type,
    )

    _fan_out_log_entry(case_id, entry, actor_id, dl)
    return entry
