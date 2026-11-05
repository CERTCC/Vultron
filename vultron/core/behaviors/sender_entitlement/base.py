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

"""The sender checks' shared refusal rule, and the base class most derive from.

:func:`refuse_by_placement` is a free function so that a check which is not a
:class:`SenderEntitlementConditionNode` subclass can take the same rule.

A check's FAILURE refuses the sender only where nothing above it may
still admit the sender (:func:`failure_is_the_refusal`, SL-03-002).
"""

import re
from typing import ClassVar

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case_id_scope import CaseIdScope
from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
)
from vultron.core.behaviors.node_logger import node_logger
from vultron.core.behaviors.sender_entitlement.declarations import (
    SenderEntitlementKind,
)

# ---------------------------------------------------------------------------
# Where a check sits in the composed guard: is its FAILURE the refusal?
# ---------------------------------------------------------------------------

#: The trailing ``— REFUSED (IDs)`` group a refusal reason ends with.
_REFUSAL_WORDING = re.compile(r"\s*—\s*REFUSED \([^)]*\)\s*$")


def failure_is_the_refusal(node: py_trees.behaviour.Behaviour) -> bool:
    """``True`` when *node*'s FAILURE refuses the sender for the whole tree.

    An any-of side composes its kinds into a Selector (HP-01-023), so a kind
    that does not match hands the sender to the next kind, which may admit
    it: that FAILURE picks a branch and refuses no one.  Only the check whose
    FAILURE every composite above it passes on — the lone check of a side, or
    the :class:`SenderHoldsNoneOfNode` an any-of side ends with — is the
    guard's answer, and the guard is one child of the received tree's root
    Sequence, so its FAILURE is the tree's ``REFUSED``.

    Read from the node's own placement at tick time rather than from a flag
    the composer sets, so it cannot disagree with the tree that is running.
    A node built with no parent (a unit test of the check alone) answers
    ``True``: nothing above it can admit the sender.
    """
    child: py_trees.behaviour.Behaviour = node
    parent = child.parent
    while parent is not None:
        if isinstance(parent, CaseIdScope):
            # Seeds the child's /case_id port and passes its status through
            # unchanged, so it changes nothing about what the FAILURE means.
            child, parent = parent, parent.parent
            continue
        if isinstance(parent, py_trees.decorators.Decorator):
            # A decorator is there to change what its child's status means
            # (an Inverter turns FAILURE into SUCCESS), so this FAILURE is
            # not the refusal.
            return False
        if (
            isinstance(parent, py_trees.composites.Selector)
            and parent.children
            and parent.children[-1] is not child
        ):
            return False
        child, parent = parent, parent.parent
    return True


def _without_refusal_wording(reason: str) -> str:
    """*reason* without its trailing ``— REFUSED (IDs)`` group.

    The DEBUG line of a check that admits nobody but refuses nobody either
    (:func:`failure_is_the_refusal` is ``False``) keeps the facts and drops
    that wording: ``REFUSED`` names a refusal, and a reader — and
    ``expect_no_sender_refusals`` in the demo tests — must be able to trust
    it (SL-03-003).
    """
    return _REFUSAL_WORDING.sub("", reason)


def refuse_by_placement(
    node: py_trees.behaviour.Behaviour, reason: str
) -> Status:
    """Record *reason* as *node*'s failure reason and fail at the right level.

    *reason* becomes ``feedback_message``, which is what
    ``BTBridge.get_failure_reason`` reports (BT-13-001), so it arrives
    already carrying its own ``— REFUSED (IDs)`` group.  The log level
    follows the tree: WARNING when this node's FAILURE is the guard's
    refusal, DEBUG when a later arm of an any-of side still gets to admit
    the sender (:func:`failure_is_the_refusal`).  A line a receiver that
    then admits the activity would emit is branch selection, not a refusal,
    so it belongs at DEBUG (SL-03-002), and it drops the ``REFUSED``
    wording with it (SL-03-003).

    A free function, not only a method of
    :class:`SenderEntitlementConditionNode`, because one check the factory
    composes into the same any-of sides is not a subclass of it:
    :class:`~vultron.core.behaviors.sender_entitlement.membership.SenderIsParticipantNode`
    reuses the participant lookup of ``FindParticipantByActorIdNode``.  One
    rule for the family beats a second copy of it (#5786).

    Writes through :func:`node_logger`, the per-class stdlib logger a helper
    logging on a node's behalf uses, so the line lands where the node's own
    ``self.logger`` lines land (SL-01-005).
    """
    logger = node_logger(node)
    node.feedback_message = reason
    if failure_is_the_refusal(node):
        logger.warning("%s: %s", node.name, reason)
    else:
        logger.debug(
            "%s: %s; a later arm of the any-of side may still admit it",
            node.name,
            _without_refusal_wording(reason),
        )
    return Status.FAILURE


# ---------------------------------------------------------------------------
# Base class: marks nodes as sender-entitlement checks for the ratchet
# ---------------------------------------------------------------------------


class SenderEntitlementConditionNode(DataLayerConditionWithPorts):
    """Base class for all sender-entitlement condition nodes.

    Subclasses of this class are the *only* permitted sender predicate nodes
    in the codebase; the architecture ratchet fails on any subclass defined
    outside this package (HP-01-007).
    Beside the marker it carries one shared behaviour:
    :meth:`_refuse_by_placement`, which records a refusal reason and logs it
    at the level the node's place in the composed guard makes right.

    Each concrete subclass names the one kind it is a guard of in
    :attr:`guards_kind` (HP-01-009).
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = None
    """The kind this node is a guard of; ``None`` for a node that checks no
    one kind (the empty side and the any-of refusal the factory composes)."""

    def _refuse_by_placement(self, reason: str) -> Status:
        """Record *reason* as this check's failure reason and fail.

        Every check reaches :func:`refuse_by_placement` through this method,
        which holds the rule for the family: one reason string, logged at
        the level the node's place in the running tree makes right.

        Named for the placement it reads, not ``_refuse``, because a
        subclass that composes its own citation wants a name of its own
        (``_refuse_citing``).  A base ``_refuse`` would be silently
        overridden on those branches, which neither mypy nor pyright
        reports, so routing them through this rule would look done and do
        nothing (#5786).
        """
        return refuse_by_placement(self, reason)
