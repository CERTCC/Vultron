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
"""
Factory functions for outbound Vultron case-log synchronization activities.

These are the sole public construction API for SYNC-2/SYNC-3 log
replication activities. Internal activity subclasses are imported here
and MUST NOT be imported by callers.

Spec: ``specs/activity-factories.yaml`` AF-01-001 through AF-04-003.
Spec: ``specs/case-event-log-synchronization.yaml`` SYNC-09-002,
SYNC-03-001, SYNC-03-002.
"""

import logging

from pydantic import ValidationError

from vultron.wire.as2.factories.errors import VultronActivityConstructionError
from vultron.wire.as2.vocab.activities.sync import (
    _AnnounceLogEntryActivity,
    _RejectLogEntryActivity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
    as_Reject,
)
from vultron.wire.as2.vocab.objects.case_log_entry import CaseLogEntry

logger = logging.getLogger(__name__)


def announce_log_entry_activity(
    entry: CaseLogEntry,
    **kwargs,
) -> as_Announce:
    """Build an Announce(CaseLogEntry) — fan-out replication to participants.

    Sent by the CaseActor to each participant actor after a new log
    entry has been committed to the case event log (SYNC-09-002).

    Args:
        entry: The ``CaseLogEntry`` being replicated.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Announce`` whose ``object_`` is the log entry.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _AnnounceLogEntryActivity(object_=entry, **kwargs)
    except ValidationError as exc:
        logger.warning(
            "announce_log_entry_activity: invalid arguments: %s", exc
        )
        raise VultronActivityConstructionError(
            "announce_log_entry_activity: invalid arguments"
        ) from exc


def reject_log_entry_activity(
    entry: CaseLogEntry,
    context: str | None = None,
    **kwargs,
) -> as_Reject:
    """Build a Reject(CaseLogEntry) — hash-chain mismatch report.

    Sent by a participant to the CaseActor when an incoming
    ``Announce(CaseLogEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash (SYNC-03-001).

    Args:
        entry: The ``CaseLogEntry`` that was rejected.
        context: The last accepted entry hash string, so the CaseActor
            can determine which entries need to be replayed.
        **kwargs: Optional AS2 fields forwarded to the constructor
            (e.g. ``actor``, ``to``).

    Returns:
        An ``as_Reject`` whose ``object_`` is the rejected log entry and
        ``context`` carries the last accepted hash.

    Raises:
        VultronActivityConstructionError: If Pydantic validation fails.
    """
    try:
        return _RejectLogEntryActivity(
            object_=entry, context=context, **kwargs
        )
    except ValidationError as exc:
        logger.warning("reject_log_entry_activity: invalid arguments: %s", exc)
        raise VultronActivityConstructionError(
            "reject_log_entry_activity: invalid arguments"
        ) from exc
