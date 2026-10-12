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

"""The one "case is fully closed" condition (CM-23-013, ADR-0085).

A case is fully closed once its ledger holds the ``case_fully_closed`` entry
the CASE_MANAGER commits on the Case Owner's ``Leave(VulnerabilityCase)``
(CM-23-002 step 3).  That entry is the owner-close write boundary: after it,
no inbound activity for the case is recorded (CM-23-013).

Every check of that boundary uses :func:`ledger_records_full_closure`, so the
BT guard, the demo invariants, and the tests cannot disagree about what
"closed" means (CS-22-001).
"""

from collections.abc import Iterable
from typing import Protocol

CASE_FULLY_CLOSED_EVENT_TYPE = "case_fully_closed"
"""``event_type`` of the ledger entry that marks the write boundary."""


class _HasEventType(Protocol):
    @property
    def event_type(self) -> str: ...


def ledger_records_full_closure(entries: Iterable[_HasEventType]) -> bool:
    """True when *entries* include the ``case_fully_closed`` entry.

    Pure: the caller supplies the case's ledger entries (from a store, or
    from an exported ledger).  Order does not matter, because the boundary
    is a fact once committed.
    """
    return any(e.event_type == CASE_FULLY_CLOSED_EVENT_TYPE for e in entries)


__all__ = ["CASE_FULLY_CLOSED_EVENT_TYPE", "ledger_records_full_closure"]
