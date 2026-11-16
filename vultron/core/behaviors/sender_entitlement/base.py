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

"""The base class every sender check derives from.

A check's FAILURE records a reason worded as a refusal, but only the
received runner knows whether that FAILURE is the delivery's verdict, so a
check logs its facts at DEBUG and the runner logs the one ``REFUSED`` line
(SL-03-002, SL-03-003).
"""

from typing import ClassVar

from py_trees.common import Status

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.node_logger import fail_with_reason
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)

# ---------------------------------------------------------------------------
# Base class: marks nodes as sender-entitlement checks for the ratchet
# ---------------------------------------------------------------------------


class SenderEntitlementConditionNode(DataLayerConditionWithPorts):
    """Base class for all sender-entitlement condition nodes.

    Subclasses of this class are the *only* permitted sender predicate nodes
    in the codebase; the architecture ratchet fails on any subclass defined
    outside this package (HP-01-007).
    Beside the marker it carries one shared behaviour:
    :meth:`_fail_with_reason`, which records a refusal reason and logs its
    facts at DEBUG.

    Each concrete subclass names the one kind it is a guard of in
    :attr:`guards_kind` (HP-01-009).
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = None
    """The kind this node is a guard of; ``None`` for a node that checks no
    one kind (the empty side and the any-of refusal the factory composes)."""

    def _fail_with_reason(self, reason: str) -> Status:
        """Record *reason* as this check's failure reason and fail.

        Every check fails through this method, so the family has one rule:
        the reason, with its ``REFUSED (IDs)`` group, is what the handler
        reports, and the check's own line is DEBUG without the group
        (:func:`~vultron.core.behaviors.node_logger.fail_with_reason`).

        Not named ``_refuse``: a subclass that composes its own citation
        wants a name of its own (``_refuse_citing``), and a base ``_refuse``
        would be silently overridden on those branches, which neither mypy
        nor pyright reports (#5786).
        """
        return fail_with_reason(self, reason)
