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
"""Read the ``CaseLedgerEntry`` a ledger activity carries.

One helper for every behavior-tree area that reads the carried entry: the
SYNC replication nodes and the sender-entitlement checks (CS-22-001).
"""

from __future__ import annotations

from typing import Any

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.errors import VultronError


def require_log_entry(activity: Any, node_name: str) -> CaseLedgerEntry:
    """Return the ``CaseLedgerEntry`` from *activity*, or raise.

    Checks ``activity.log_entry`` first, then ``activity.object_``.
    Raises :class:`~vultron.errors.VultronError`, naming *node_name*, when
    neither carries a
    :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`.
    """
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        return entry
    raise VultronError(
        f"{node_name}: activity did not carry a CaseLedgerEntry"
    )
