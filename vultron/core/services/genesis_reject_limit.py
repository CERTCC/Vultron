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
"""A participant's limit on genesis Rejects for a case it does not hold.

A participant waiting for a case sends the CASE_MANAGER one genesis Reject
per case per interval (SYNC-15-016), the CASE_MANAGER's replay ceiling
(SYNC-15-020), and asks again for the first early entry after it
(SYNC-15-017).  The time it last asked is a
:class:`~vultron.core.models.genesis_reject_record.GenesisRejectRecord` in its
own store (SYNC-15-021), deleted when it seeds the case (SYNC-15-023).

Spec: SYNC-15-016, SYNC-15-017, SYNC-15-020, SYNC-15-021, SYNC-15-023.
"""

from datetime import datetime

from vultron.core.models.genesis_reject_record import GenesisRejectRecord
from vultron.core.ports.case_persistence import CasePersistence

_RECORD_TYPE = "GenesisRejectRecord"


def last_genesis_reject_at(
    dl: CasePersistence, case_id: str
) -> datetime | None:
    """When this participant last sent a genesis Reject for *case_id*.

    ``None`` when it has sent none since it last seeded the case, or ever.
    """
    record = dl.read(GenesisRejectRecord.build_id(case_id))
    if isinstance(record, GenesisRejectRecord):
        return record.last_sent_at
    return None


def record_genesis_reject(
    dl: CasePersistence, case_id: str, sent_at: datetime
) -> None:
    """Record that a genesis Reject for *case_id* was queued at *sent_at*."""
    dl.save(GenesisRejectRecord(case_id=case_id, last_sent_at=sent_at))


def forget_genesis_rejects(dl: CasePersistence, case_id: str) -> None:
    """Delete the record for *case_id*, once the participant seeds it.

    A no-op when there is none.  A record left behind would make a later
    wait for the same case inherit an old time (SYNC-15-023).
    """
    dl.delete(_RECORD_TYPE, GenesisRejectRecord.build_id(case_id))


__all__ = [
    "forget_genesis_rejects",
    "last_genesis_reject_at",
    "record_genesis_reject",
]
