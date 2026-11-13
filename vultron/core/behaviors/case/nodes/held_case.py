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
"""The acts that name their case and carry none of it (AKM-03-004, ADR-0165).

``Join``, ``Ignore`` and ``Leave`` of a case and the owner's
ownership-transfer proposal, ``Offer(Offer(VulnerabilityCase))``, name their
case by reference: the receiver reads every detail from the case it holds.
A case it does not hold leaves it nothing to act on, so the act is refused,
naming the activity and the case (AKM-03-006).

A tree declares that its message is one of these acts with
``create_receive_activity_tree(held_case=...)``.  The refusal is the path
stage's: a receiver that holds no replica of the case is on the no-case path,
which none of these types declares, and the stage composes the reason from
the path, the declaration and the act (HP-01-035, HP-01-039,
:func:`~vultron.core.behaviors.case.nodes.received_path.undeclared_path_reason`).
No use case reads its store to ask first.
"""

from enum import Enum

__all__ = ["CaseNamedByReference"]


class CaseNamedByReference(Enum):
    """The acts that name their case and carry none of it (AKM-03-004).

    Each member's value is how the act is named in the refusal.
    """

    JOIN = "Join"
    IGNORE = "Ignore"
    LEAVE = "Leave"
    OWNERSHIP_TRANSFER_PROPOSAL = "Offer(Offer)"
