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

"""Tree factories for ownership-transfer received activities (ADR-0148).

Provides:

- :func:`create_propose_ownership_transfer_tree` — BT for
  ``OfferCaseOwnershipTransferReceivedUseCase``, one tree for the one wire
  shape (ADR-0199).  At the CASE_MANAGER the Offer is the Case Owner's
  proposal: admitted only from the owner and only while no Offer for the
  case is open (CM-21-014, CM-21-019), ledgered, and made into the
  CASE_MANAGER's own ``Offer(VulnerabilityCase)`` through
  ``MakeOwnershipTransferOfferNode`` in ``manager_effects`` (CM-21-005,
  CM-21-028, BT-17-008).  At the transferee it is that Offer, which intake
  records for it to answer, taken from the case's CASE_MANAGER alone.
- :func:`create_accept_ownership_transfer_tree` — BT for
  ``AcceptCaseOwnershipTransferReceivedUseCase``.
- :func:`create_reject_ownership_transfer_tree` — BT for
  ``RejectCaseOwnershipTransferReceivedUseCase``: the Accept's tree with no
  effects, so the declined Offer is ledgered and closed (CM-21-012).
- :func:`create_undo_ownership_transfer_tree` — BT for
  ``UndoCaseOwnershipTransferReceivedUseCase``: the owner's withdrawal of
  its own Offer, ledgered like the Reject so it closes the Offer made from
  it (CM-21-015).

The Owner's Offer and the three replies judge the case's Offer against its own
``end_time`` and the act's instant (ADR-0176), at the CASE_MANAGER only: an
Offer past its deadline is closed, with no entry recording the expiry, so a
late reply is refused and a new Owner's Offer is admitted (CM-21-014, CM-21-016,
CM-21-017, ADR-0152).

The factories live in submodules grouped by concern (CS-18-005):

- ``proposal``: the Case Owner's Offer and the CASE_MANAGER's Offer.
- ``replies``: the transferee's ``Accept`` or ``Reject`` of the Offer and the
  owner's ``Undo`` of its own Offer.
"""

from vultron.core.behaviors.case.ownership_transfer_tree.proposal import (
    create_propose_ownership_transfer_tree,
    proposal_sender_context,
)
from vultron.core.behaviors.case.ownership_transfer_tree.replies import (
    create_accept_ownership_transfer_tree,
    create_reject_ownership_transfer_tree,
    create_undo_ownership_transfer_tree,
)

__all__ = [
    "create_accept_ownership_transfer_tree",
    "create_propose_ownership_transfer_tree",
    "create_reject_ownership_transfer_tree",
    "create_undo_ownership_transfer_tree",
    "proposal_sender_context",
]
