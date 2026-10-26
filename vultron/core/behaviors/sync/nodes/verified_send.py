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
"""The one place the CASE_MANAGER sends an ``Announce(CaseLedgerEntry)``.

Every send path (the fan-out of a new entry, the ``Reject`` and ``Read``
replays, the embargo backfill and the join-time backfill) queues an entry
through :func:`send_verified_log_entry`.  It recomputes the entry's hash with
:func:`~vultron.core.models.case_ledger.ledger_entry_hash_intact`, the same
predicate a receiver uses (SYNC-03-006), and raises
:class:`~vultron.errors.VultronUnverifiedLedgerEntryError` instead of queuing
an entry that states no hash or whose content does not reproduce it
(SYNC-03-009).  A broken entry in the CASE_MANAGER's own store is then found
where it starts, not after a replica refuses it.

No other code in ``vultron/core/`` calls ``send_announce_log_entry``
(``test/architecture/test_send_announce_log_entry_has_one_caller.py``), so no
send path can skip the check.
"""

from vultron.core.models.case_ledger import ledger_entry_hash_intact
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.errors import VultronUnverifiedLedgerEntryError


def send_verified_log_entry(
    sync_port: SyncActivityPort,
    entry: CaseLedgerEntry,
    *,
    actor_id: str,
    to: list[str],
) -> bool:
    """Queue ``Announce(entry)`` to *to* once *entry*'s hash verifies.

    Returns what ``SyncActivityPort.send_announce_log_entry`` returns:
    ``True`` when a row was queued, ``False`` when the same ``Announce`` was
    already pending and nothing was queued (SYNC-15-012).

    Raises:
        VultronUnverifiedLedgerEntryError: *entry* states no ``entry_hash``,
            or its content does not reproduce it.  Nothing is queued; the
            caller stops its send there and reports it at ERROR
            (SYNC-03-009).
    """
    if not ledger_entry_hash_intact(entry):
        raise VultronUnverifiedLedgerEntryError(
            case_id=entry.case_id,
            entry_id=entry.id_,
            log_index=entry.log_index,
            recipients=to,
        )
    return sync_port.send_announce_log_entry(
        entry=entry, actor_id=actor_id, to=to
    )
