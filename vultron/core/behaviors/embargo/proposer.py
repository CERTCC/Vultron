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
"""Who proposed an embargo, read from the case's ledger (EP-09-002, CM-24).

The proposer of an embargo is named by the first
``invite_to_embargo_on_case`` entry that carries it: a proposal a participant
sent names it as ``actor``, and an Invite the CASE_MANAGER relayed on a
proposer's behalf names it in ``attributedTo`` (CM-24-002).  A relayed Invite
of the embargo, to a joiner (EP-09-011) or to a late accepter (EMB-17-003),
names the same proposer in ``attributedTo``.
"""

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.wire_keys import wire_key
from vultron.core.predicates.addressing import snapshot_actor_id

_INVITE_SEMANTIC_TYPE = MessageSemantics.INVITE_TO_EMBARGO_ON_CASE.value


def _carried_embargo_id(value: object) -> str | None:
    """The id of the ``EmbargoEvent`` an Invite's ``object`` names."""
    if isinstance(value, dict):
        value = value.get("id")
    return value if isinstance(value, str) and value else None


def embargo_proposer_id(
    entries: list[CaseLedgerEntry], embargo_id: str
) -> str | None:
    """The proposer of *embargo_id*, from the first Invite entry carrying it.

    *entries* is the case's ledger, oldest first.  ``attributedTo`` when the
    entry names one, else ``actor``, both in the case's canonical spelling
    (OID-01-006).  ``None`` when no committed Invite carries the embargo: the
    CASE_MANAGER made it without a proposal, as it makes the protocol
    default at case creation (EP-04-002).
    """
    for entry in entries:
        if entry.semantic_type != _INVITE_SEMANTIC_TYPE:
            continue
        snapshot = entry.payload_snapshot
        if _carried_embargo_id(snapshot.get("object")) != embargo_id:
            continue
        return snapshot_actor_id(
            snapshot.get(wire_key("attributed_to"))
        ) or snapshot_actor_id(snapshot.get("actor"))
    return None


__all__ = ["embargo_proposer_id"]
