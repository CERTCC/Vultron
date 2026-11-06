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

"""Verdicts owed when a door guard of a received tree turned the run away.

The addressee check (HP-01-005), the seen-before door (ADR-0154), the path
door stage (ADR-0153), the post-close boundary (CM-23-013), the closed-sender
door (CM-23-018) and the incomplete-activity guard; each keeps its guard's own
reason (CLP-10-010).  The seen-before door is the one whose answer may be
``SKIPPED``: a resend of a message already applied, or still waiting.
"""

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.bridge import BTExecutionResult
from vultron.core.behaviors.case.nodes.addressee import (
    ActivityAddressedToReceiverNode,
)
from vultron.core.behaviors.case.nodes.incomplete_activity import (
    ActivityIncompleteNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPathNode,
)
from vultron.core.behaviors.case.nodes.seen_before import (
    ActivityNotSeenBeforeNode,
    SeenBefore,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
)
from vultron.core.behaviors.helpers import WIRING_UNAVAILABLE_MESSAGES
from vultron.core.behaviors.sender_guard import closed_sender_turned_away
from vultron.core.models.use_case_result import (
    HandlerResult,
)
from vultron.core.use_cases.received._bt_verdict.tree_lookup import (
    _HasRoot,
    _root,
    find_node,
)
from vultron.errors import VultronBTInternalError, VultronWiringError


def path_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal owed when the path door stage turned this receiver away.

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.received_path.ReceivedPathNode`
    refused: the receiver is on a path this message type declares no branch
    for, so the message was never its to act on (HP-01-005).  The reason is
    the stage's own, composed in one place for every message type
    (HP-01-039); :func:`door_refusal` asks this after the addressee check
    and the seen-before door, in the stage order the factory places them in
    (CLP-10-010).
    """
    return guard_refusal(tree, ReceivedPathNode)


def closed_sender_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    result: BTExecutionResult,
    *,
    closes: bool,
    label: str,
) -> HandlerResult | None:
    """The verdict owed a sender the tree's closed-sender door turned away.

    The door (``closed_sender`` on the receive-tree factory) stops the tree
    when the case already records the sender's closure, with nothing
    committed or sent (CM-23-018):

    - an act that would close it again (*closes*: a ``Leave``, a ``Reject``
      of a stub or full-case Invite) changes nothing, so it is ``SKIPPED``,
      whatever its activity id (ID-05-003);
    - any other act is ``REFUSED``: the sender may act on nothing further.

    ``None`` when the run did not end at the door.  The handler asks this
    before any other reading of the run's failure.

    A door that found the closure but whose run failed on an internal error
    (the Case Owner check of a ``case_owner_completes`` door crashing, say)
    raises: a crash is never read as a repeat or a refusal (ARCH-15-001).

    Raises:
        VultronWiringError: *tree* was not built by
            :func:`~vultron.core.behaviors.case.receive_activity_tree.create_receive_activity_tree`.
        VultronBTInternalError: The door found the closure, but the run
            failed on an internal error.
    """
    root = _root(tree)
    if not isinstance(root, ReceivedActivityTree):
        raise VultronWiringError(
            f"closed_sender_verdict: '{root.name}' is not a"
            " received-activity tree, so it has no closed-sender door"
            " (CM-23-018)"
        )
    closed = closed_sender_turned_away(root)
    if closed is None:
        return None
    if result.internal_error:
        raise VultronBTInternalError(f"{label}: {result.feedback_message}")
    if closes:
        return HandlerResult.skipped(
            f"{label}: {closed} — a repeat of a closing act,"
            " nothing to apply (ID-05-003)"
        )
    return HandlerResult.refused(
        f"{label}: {closed} — it may act on nothing further"
    )


def guard_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
    node_type: type[py_trees.behaviour.Behaviour],
) -> HandlerResult | None:
    """``REFUSED`` with the guard's own reason when a *node_type* guard failed.

    ``None`` when no such guard ran and failed.  For a guard whose message
    is the whole refusal, so the reason carries no tree label:
    :class:`~vultron.core.behaviors.case.nodes.incomplete_activity.ActivityIncompleteNode`
    and the announce tree's trusted-sender guard.  A guard that never ran (a
    leadership skip, or the post-close guard refused first) is ``None``, so
    the handler falls through to :func:`verdict_from_bt`.  So does a guard
    that failed because it was composed without a dependency (a
    ``WIRING_UNAVAILABLE_MESSAGES`` reason): that is our fault, not the
    sender's, and :func:`verdict_from_bt` raises it (ADR-0095).
    """
    node = find_node(tree, node_type)
    if node is None or node.status != Status.FAILURE:
        return None
    if node.feedback_message in WIRING_UNAVAILABLE_MESSAGES:
        return None
    return HandlerResult.refused(
        node.feedback_message or f"{node.name} refused the activity"
    )


def addressee_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal of a copy not addressed to this receiver (HP-01-005).

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.addressee.ActivityAddressedToReceiverNode`
    door guard refused; the reason is the guard's own, naming the receiver,
    the activity and its ``to``.
    """
    return guard_refusal(tree, ActivityAddressedToReceiverNode)


def incomplete_activity_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal of an activity its handler's tree could not be built for.

    See :func:`guard_refusal` and
    :func:`~vultron.core.behaviors.case.intake_only_received_tree.create_incomplete_activity_received_tree`.
    """
    return guard_refusal(tree, ActivityIncompleteNode)


def seen_before_verdict(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The answer to a resend the seen-before door ended the run on.

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.seen_before.ActivityNotSeenBeforeNode`
    found the activity already answered (ADR-0154):

    - a receipt stub: ``REFUSED`` again, with the reason the stub recorded,
      so a refusal is whole and final for that activity;
    - an archive: ``SKIPPED``, because the message was applied;
    - a record still owed a replay: ``SKIPPED``, because the held message is
      answered when its replay reaches its own outcome.

    Nothing ran after the door, so no refusal notice is sent again.
    """
    node = find_node(tree, ActivityNotSeenBeforeNode)
    if node is None or node.status != Status.FAILURE or node.seen is None:
        return None
    if node.seen is SeenBefore.REFUSED:
        return HandlerResult.refused(
            node.refusal_reason or node.feedback_message
        )
    return HandlerResult.skipped(node.feedback_message)


def post_close_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The refusal owed when the post-close guard dropped the activity.

    ``None`` unless the tree's
    :class:`~vultron.core.behaviors.case.nodes.post_close.CaseOpenToExternalWritesNode`
    refused: this actor is the case's CASE_MANAGER and the case is fully
    closed, so the tree recorded nothing (CM-23-013).  The verdict is
    ``REFUSED`` whatever the handler would otherwise read from the failure;
    :func:`door_refusal` asks this first.
    """
    for node in _root(tree).iterate():
        if (
            isinstance(node, CaseOpenToExternalWritesNode)
            and node.status == Status.FAILURE
        ):
            return HandlerResult.refused(
                node.feedback_message or "case is fully closed (CM-23-013)"
            )
    return None


def door_refusal(
    tree: py_trees.behaviour.Behaviour | _HasRoot,
) -> HandlerResult | None:
    """The verdict owed when a door guard every received tree carries ended it.

    The addressee check (:func:`addressee_refusal`, HP-01-005), the
    seen-before door (:func:`seen_before_verdict`, ADR-0154), the path stage
    (:func:`path_refusal`, ADR-0153), then the post-close boundary
    (:func:`post_close_refusal`, CM-23-013); each keeps its guard's own
    reason, and they are asked in the order the factory places them
    (CLP-10-010).  ``None`` when none ended the run.  Only one door can have
    failed, because the first that fails ends the run, so the order decides
    nothing but is kept to read as the tree does.  The seen-before door's
    answer may be ``SKIPPED``, a resend of a message already applied or still
    waiting; every other door's is ``REFUSED``.  The factory places the
    addressee check and the post-close boundary in every received tree
    unless it declares an exemption, the seen-before door in every received
    tree, and the path stage in every tree that declared its paths, so
    :func:`verdict_from_bt` and :func:`applied_or_raise` ask this first, and
    a handler that maps a tree's failure itself asks it too.
    """
    if (refusal := addressee_refusal(tree)) is not None:
        return refusal
    if (verdict := seen_before_verdict(tree)) is not None:
        return verdict
    if (refusal := path_refusal(tree)) is not None:
        return refusal
    return post_close_refusal(tree)
