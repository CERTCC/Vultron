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
"""Case copies that name a ledger tail, as a CASE_MANAGER sends them.

A full-case announcement carries the sender's ledger tail (SYNC-16-005), and
a replica that already holds the case judges the copy by it (SYNC-16-006).
These helpers give a test case the tail its sender would have filled in.
"""

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import ledger_tail_position

#: Stands in for a genesis hash on a test case with no owner to derive one.
PLACEHOLDER_GENESIS_HASH = "0" * 64


def copy_at_genesis(case: VulnerabilityCase) -> VulnerabilityCase:
    """*case* as a copy taken before its ledger has any entry."""
    return case.with_ledger_tail(
        LedgerPosition(
            log_index=EMPTY_LEDGER_LOG_INDEX,
            entry_hash=case.genesis_hash or PLACEHOLDER_GENESIS_HASH,
        )
    )


def copy_from(
    case: VulnerabilityCase, dl: CasePersistence
) -> VulnerabilityCase:
    """*case* as a copy naming the tail of *dl*'s ledger for it.

    A store that does not hold the case yet gets a copy taken before any
    entry, the copy a first seed takes (PCR-02-003).
    """
    if dl.read_case(case.id_) is None:
        return copy_at_genesis(case)
    return case.with_ledger_tail(ledger_tail_position(case.id_, dl))
