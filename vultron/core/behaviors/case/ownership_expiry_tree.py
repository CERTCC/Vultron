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

"""The CASE_MANAGER's lazy expiry of an ownership-transfer Offer (CM-21-017).

:func:`create_ownership_offer_expiry_tree` is a standalone CASE_MANAGER tree,
not a received-activity tree, like the embargo Invite expiry tree
(:mod:`vultron.core.behaviors.embargo.expiry_tree`).  The CASE_MANAGER runs
it just before it processes an Accept, Reject or Undo of an
ownership-transfer Offer, or a new Offer for the case; there is no
scheduler.  When the case's open Offer has passed its ``end_time``, it
commits the expiry entry and broadcasts it, so the received tree that runs
next reads the Offer as closed (CM-21-014)::

    ExpireOverdueOwnershipOfferBT (CASE_MANAGER-gated)
    └─ ExpireOverdueOwnershipOffer (Selector)
       ├─ Inverter(CaseOpenToExternalWrites)   # closed case: change nothing
       └─ ExpireOverdueOwnershipOfferNode      # commit + broadcast if due

The expiry is the CASE_MANAGER's own decision from its clock, so it is
committed as its own entry, before the activity it is processing changes
anything (CLP-07-013).  It is not part of the received tree: that tree
commits nothing before its guards (CLP-10-010).

An Accept, Reject or Undo prompts the expiry only when it names the open
Offer and comes from its party (the transferee, or the offerer), so a sender
with no standing never makes the CASE_MANAGER write (HP-01-006).

A store that is not the case's CASE_MANAGER runs nothing: a replica learns
an expiry from the entry and never computes one (CM-21-017, BT-17-001).
The entry changes no replica state of its own; it closes the Offer because
every "is it open?" reader includes its ``event_type``
(``OFFER_CASE_OWNERSHIP_TRANSFER_REPLY_TYPES``).
"""

from datetime import datetime

import py_trees

from vultron.core.behaviors.case.nodes.ownership_offer_expiry import (
    ExpireOverdueOwnershipOfferNode,
    ExpiryPrompt,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    create_case_manager_gated_tree,
)


def create_ownership_offer_expiry_tree(
    case_id: str, now: datetime, prompt: ExpiryPrompt | None = None
) -> py_trees.behaviour.Behaviour:
    """Build the CASE_MANAGER-gated lazy expiry of the case's open Offer.

    Args:
        case_id: The case whose open ownership-transfer Offer is checked.
        now: The instant the Offer's ``end_time`` is compared against; the
            caller passes the same one to the received tree it runs next.
        prompt: The Accept, Reject or Undo that prompts the check, so the
            expiry is ledgered only for a reply to the open Offer from its
            party (HP-01-006); ``None`` for a new Offer, whose handler has
            already checked its sender is the Case Owner (CM-21-019).

    Returns:
        A tree that succeeds when nothing was due or the expiry was committed,
        and when the executing actor is not the case's CASE_MANAGER.  After
        ``case_fully_closed`` it changes nothing (CM-23-013).
    """
    return create_case_manager_gated_tree(
        name="ExpireOverdueOwnershipOfferBT",
        case_id=case_id,
        body_name="ExpireOverdueOwnershipOffer",
        case_may_be_absent=True,
        children=[
            py_trees.composites.Selector(
                name="ExpireOverdueOwnershipOfferIfCaseOpen",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="CaseFullyClosed",
                        child=CaseOpenToExternalWritesNode(case_id=case_id),
                    ),
                    ExpireOverdueOwnershipOfferNode(
                        case_id=case_id, now=now, prompt=prompt
                    ),
                ],
            )
        ],
    )


__all__ = ["create_ownership_offer_expiry_tree"]
