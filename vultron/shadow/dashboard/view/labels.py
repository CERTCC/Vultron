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


"""The words and icons every part of the page shares: a table row, each
case-state event's name, each report- and embargo-management state's badge,
and an actor's display name (DRPT-03-009).
"""

from __future__ import annotations

from collections.abc import Mapping

from vultron.core.states.cs_invariants import CSEvent
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.measure.ledger import UNNAMED_ACTOR, display_label

#: A row of a table the page shows, column name to cell: text, or a number
#: that sorts as one, such as a move's layer.
Row = dict[str, str | int]

#: Each case-state event's name, as the CS model pages spell it.
EVENT_LABELS: Mapping[CSEvent, str] = {
    CSEvent.V: "Vendor Awareness",
    CSEvent.F: "Fix Ready",
    CSEvent.D: "Fix Deployed",
    CSEvent.P: "Public Awareness",
    CSEvent.X: "Exploit Public",
    CSEvent.A: "Attacks Observed",
}


#: A report-management state as an icon and a word.
RM_BADGES: Mapping[RM, str] = {
    RM.START: "⚪ Start",
    RM.RECEIVED: "📥 Received",
    RM.INVALID: "🚫 Invalid",
    RM.VALID: "☑️ Valid",
    RM.DEFERRED: "⏸️ Deferred",
    RM.ACCEPTED: "▶️ Accepted",
    RM.CLOSED: "⏹️ Closed",
}

#: The case's embargo-management state as an icon and a word.
EM_BADGES: Mapping[EM, str] = {
    EM.NONE: "➖ No embargo",
    EM.PROPOSED: "📨 Embargo proposed",
    EM.ACTIVE: "🔒 Embargo active",
    EM.REVISE: "✏️ Revision proposed",
    EM.EXITED: "🔓 Embargo exited",
}


def actor_label(actor: str, names: Mapping[str, str]) -> str:
    """*actor* by its display name, never a bare URI or UUID (DRPT-03-009).

    An actor no payload names reads by the last segment of its URI, and one
    whose id is opaque, as an outside system's ``urn:uuid:`` id is, reads
    as :data:`~vultron.measure.ledger.UNNAMED_ACTOR`.
    """
    return display_label(actor, "Actor", names) or UNNAMED_ACTOR


__all__ = [
    "EM_BADGES",
    "EVENT_LABELS",
    "RM_BADGES",
    "Row",
    "actor_label",
]
