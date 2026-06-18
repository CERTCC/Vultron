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

"""Factory for the peer broadcast BT subtree used by all protocol-visible fan-out paths.

In a federated CVD protocol, when a Case Manager receives a state update
(participant status, embargo proposal, etc.) it must forward that update to
every other participant so their local views remain consistent.  This
fan-out is *protocol-visible*: if the Case Manager fails to notify a peer,
that peer's state silently diverges — a correctness risk that is hard to
detect or recover from after the fact.

:func:`peer_broadcast_bt` provides the canonical subtree for that fan-out.
It handles the four steps every broadcast path shares:

1. Resolve which actor is acting as Case Manager for this case.
2. Compute the eligible recipient set (all participants except the original
   sender, the current executing actor, and the Case Manager itself).
3. Construct the domain-specific outbound AS2 activity via a caller-supplied
   ``activity_builder`` closure.
4. Enqueue the activity to the Case Manager's outbox for delivery.

Any failure in steps 1–4 propagates as BT ``FAILURE`` so the caller's BT
can react (retry, escalate, or halt further processing).  An empty recipient
list is treated as a successful no-op — the broadcast simply isn't needed
when no eligible peers exist.

Usage example::

    from vultron.core.behaviors.broadcast import peer_broadcast_bt

    def _build_activity(factory, case_manager_id, recipient_ids):
        return factory.announce_something(
            actor=case_manager_id,
            to=recipient_ids,
        )

    tree = peer_broadcast_bt(
        case_id=case_id,
        sender_actor_id=sender_actor_id,
        activity_builder=_build_activity,
    )
    result = bridge.execute_with_setup(tree=tree, actor_id=actor_id)

Per ``specs/behavior-tree-integration.yaml`` BT-14-001 and BT-14-002.
"""

import logging
from typing import TYPE_CHECKING, Callable

import py_trees

from vultron.core.behaviors.broadcast.nodes import (
    BroadcastQueueToOutboxNode,
    CreateBroadcastActivityNode,
    FilterPeerRecipientsNode,
    FindCaseManagerNode,
)

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort

logger = logging.getLogger(__name__)


def peer_broadcast_bt(
    *,
    case_id: str | None,
    sender_actor_id: str,
    activity_builder: Callable[["TriggerActivityPort", str, list[str]], str],
    name: str | None = None,
) -> py_trees.behaviour.Behaviour:
    """Assemble the four-step peer broadcast subtree for a single fan-out event.

    The returned tree encodes the protocol requirement that every state change
    accepted by a Case Manager must be forwarded to all other participants
    (BT-14-002).  The caller supplies an ``activity_builder`` closure that
    knows how to construct the domain-specific AS2 activity; this factory
    handles the surrounding infrastructure: finding the Case Manager, filtering
    the recipient set, creating the activity, and queuing it for outbox
    delivery.

    The tree returns ``FAILURE`` whenever the Case Manager cannot be resolved,
    the activity cannot be constructed, or the outbox enqueue fails — giving
    the caller's BT full control over error handling (BT-14-001).  When no
    eligible recipients remain after filtering, the tree returns ``SUCCESS``
    without calling the factory; this is a legitimate no-op, not an error.

    Blackboard keys shared across all four nodes:

    - ``broadcast_case_manager_id``: Case Manager actor ID
    - ``broadcast_peer_recipient_ids``: filtered peer actor ID list
    - ``broadcast_activity_id``: created activity ID (``None`` when no-op)

    The caller must execute the tree via
    :meth:`~vultron.core.behaviors.bridge.BTBridge.execute_with_setup` so
    that ``datalayer``, ``actor_id``, and (when broadcasting)
    ``trigger_activity_factory`` are present on the blackboard.

    Args:
        case_id: ID of the
            :class:`~vultron.wire.as2.vocab.objects.vulnerability_case.VulnerabilityCase`
            whose CASE_MANAGER should originate the broadcast.
        sender_actor_id: Actor ID of the entity whose update is being
            forwarded; excluded from the recipient set so the originating
            actor does not receive its own update.
        activity_builder: ``(factory, case_manager_id, recipient_ids) ->
            activity_id`` — called by
            :class:`~vultron.core.behaviors.broadcast.nodes.CreateBroadcastActivityNode`
            with the resolved factory instance, Case Manager actor ID, and
            filtered recipient list.  Must create and persist the outbound
            AS2 activity and return its ID as a ``str``.
        name: Optional name override for the root Sequence node.

    Returns:
        Root node of the peer broadcast Sequence.
    """
    root = py_trees.composites.Sequence(
        name=name or "PeerBroadcastBT",
        memory=False,
        children=[
            FindCaseManagerNode(case_id=case_id),
            FilterPeerRecipientsNode(
                sender_actor_id=sender_actor_id,
                case_id=case_id,
            ),
            CreateBroadcastActivityNode(activity_builder=activity_builder),
            BroadcastQueueToOutboxNode(),
        ],
    )
    logger.debug(
        "Created PeerBroadcastBT for case_id=%s sender=%s",
        case_id,
        sender_actor_id,
    )
    return root
