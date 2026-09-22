#!/usr/bin/env python
"""
Wire-layer alias for CaseLedgerEntry.

Per ADR-0099 detail 3: the core class is the canonical form.
The as_-prefixed name is retained for backward compatibility.

Re-exports :class:`VultronCaseLedgerEntry` and
:data:`VultronCaseLedgerEntryRef` from the core domain module so that
callers importing from this wire module continue to work unchanged.
"""

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

from vultron.core.models.case_ledger_entry import (
    CaseLedgerEntry,
    VultronCaseLedgerEntry,
    VultronCaseLedgerEntryRef,
)
from vultron.wire.as2.vocab.base.registry import WIRE_TYPE_MAP

# Backward-compatibility alias (ADR-0099 detail 3)
as_CaseLedgerEntry = CaseLedgerEntry

# Register core class in WIRE_TYPE_MAP so the parser admits it inline
WIRE_TYPE_MAP["CaseLedgerEntry"] = CaseLedgerEntry

__all__ = [
    "as_CaseLedgerEntry",
    "VultronCaseLedgerEntry",
    "VultronCaseLedgerEntryRef",
]
