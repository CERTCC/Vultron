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

"""Recorded decisions that a received tree goes without the sender sequence.

A received tree whose activity takes no ``senderSequence`` (SYNC-21-001)
names one registered :class:`SenderSequenceExemption` instead of the stage
made of the :mod:`~vultron.core.behaviors.sync.nodes.sender_sequence`
nodes; the received-tree factory refuses an exemption missing from
:data:`SENDER_SEQUENCE_EXEMPTIONS`.
"""

from __future__ import annotations

from typing import Final

from pydantic import BaseModel, ConfigDict

from vultron.primitives import NonEmptyString

__all__ = [
    "LEDGER_REQUEST_TAKES_NO_NUMBER",
    "SENDER_SEQUENCE_EXEMPTIONS",
    "SenderSequenceExemption",
]


class SenderSequenceExemption(BaseModel):
    """One recorded decision that a received tree judges no sender sequence.

    Attributes:
        name: Short stable name of the decision.
        reason: Why the tree's activity takes no number.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: NonEmptyString
    reason: NonEmptyString


LEDGER_REQUEST_TAKES_NO_NUMBER: Final = SenderSequenceExemption(
    name="ledger-request-takes-no-number",
    reason=(
        "The activity is a Read(CaseLedgerEntry), a request about the ledger"
        " and not a case event (CLP-02-013), so its sender numbers it not"
        " (SYNC-21-001): a request for a missed entry must not wait behind"
        " the gap it reports."
    ),
)

#: Every decision that lets a received tree go without the stage.
SENDER_SEQUENCE_EXEMPTIONS: Final[dict[str, SenderSequenceExemption]] = {
    exemption.name: exemption
    for exemption in (LEDGER_REQUEST_TAKES_NO_NUMBER,)
}
