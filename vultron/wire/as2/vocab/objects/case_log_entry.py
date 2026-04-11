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
"""Wire-layer vocabulary registration for :class:`VultronCaseLogEntry`.

The canonical class definition lives in
:mod:`vultron.core.models.case_log_entry`.  This module re-exports it and
registers it in the wire-layer vocabulary under ``"CaseLogEntry"`` so that
DataLayer round-trips (``dl.save`` / ``dl.read``) reconstruct the object
correctly.

``AnnounceLogEntryActivity.object_`` uses :data:`VultronCaseLogEntryRef` as
its type annotation.  Pydantic v2 accepts a :class:`VultronCaseLogEntry`
instance (a core domain object) in the union because it is the first and most
specific member.

Spec: SYNC-01-002, SYNC-02-003, SYNC-03-001 through SYNC-03-003.
"""

from vultron.core.models.case_log_entry import (  # noqa: F401
    VultronCaseLogEntry,
    VultronCaseLogEntryRef,
)
from vultron.wire.as2.vocab.base.registry import VOCABULARY

# Manual vocabulary registration: the class extends core.VultronObject (not
# as_Base), so __init_subclass__ does not auto-register it.  The DataLayer
# uses record.type_ == "CaseLogEntry" as the lookup key.
VOCABULARY["CaseLogEntry"] = VultronCaseLogEntry

__all__ = ["VultronCaseLogEntry", "VultronCaseLogEntryRef"]
