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

"""Ledger entries the CASE_MANAGER cannot verify, for send-side hash tests.

Each helper returns a copy of an entry that ``ledger_entry_hash_intact()``
rejects (SYNC-03-006, SYNC-03-009): ``tampered`` keeps the stated hash but
changes the content it covers, and ``hashless`` states no hash at all.
"""

from collections.abc import Callable

import pytest

from vultron.core.models.case_ledger_entry import CaseLedgerEntry

BreakEntry = Callable[[CaseLedgerEntry], CaseLedgerEntry]


def tampered(entry: CaseLedgerEntry) -> CaseLedgerEntry:
    """Content no longer reproduces the stated hash."""
    return entry.model_copy(update={"payload_snapshot": {"tampered": True}})


def hashless(entry: CaseLedgerEntry) -> CaseLedgerEntry:
    """The entry states no hash, so there is nothing to check."""
    return entry.model_copy(update={"entry_hash": ""})


#: Parametrize a test over both ways an entry can fail the check.
broken_entries = pytest.mark.parametrize(
    "break_entry", [tampered, hashless], ids=["tampered", "hashless"]
)
