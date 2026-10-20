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

"""Payload-snapshot extraction for :class:`CommitCaseLedgerEntryNode`.

A received entry records the received JSON verbatim: the evidence the parser
sealed (VM-08-002), carried onto the dispatched event at the parse edge
(CLP-07-011, ADR-0107).  Nothing here drops, re-dumps, inlines, patches or
merges a field, so a replica holds what the sender sent, byte for byte, and
an object it was sent by id alone is dereferenced, not filled in from this
receiver's store (CLP-07-006).
"""

from typing import Any

from vultron.core.models.events.base import VultronEvent
from vultron.errors import VultronWiringError


def _extract_payload_snapshot(activity: Any) -> dict[str, Any]:
    """The received body *activity* was extracted from, unchanged.

    Args:
        activity: The received event on the blackboard.

    Raises:
        VultronWiringError: When *activity* is not a received event, or carries
            no received evidence.  Either is a composition fault, not the
            sender's: a received tree runs on the event its delivery produced
            (ARCH-15-001, ADR-0095).
    """
    if not isinstance(activity, VultronEvent):
        raise VultronWiringError(
            f"{type(activity).__name__} is not a received event, so there is"
            " no received body to record as the ledger payload snapshot"
            " (ARCH-15-001)"
        )
    return activity.received_body()
