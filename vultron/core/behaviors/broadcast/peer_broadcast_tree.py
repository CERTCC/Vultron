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

"""Shared fail-fast peer broadcast BT factory (BT-14-001, BT-14-002).

:func:`peer_broadcast_bt` builds a plain ``memory=False`` Sequence — no
guaranteed-success fallback — so FAILURE propagates to the caller when any
broadcast preparation or outbox-enqueueing step fails.

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
    """Build a fail-fast peer broadcast Sequence (BT-14-001, BT-14-002).

    Composes :class:`~vultron.core.behaviors.broadcast.nodes.FindCaseManagerNode`,
    :class:`~vultron.core.behaviors.broadcast.nodes.FilterPeerRecipientsNode`,
    :class:`~vultron.core.behaviors.broadcast.nodes.CreateBroadcastActivityNode`,
    and :class:`~vultron.core.behaviors.broadcast.nodes.BroadcastQueueToOutboxNode`
    into a ``memory=False`` Sequence.

    Unlike the old ``Selector``-with-``Success``-fallback pattern, this
    Sequence propagates FAILURE when broadcast preparation or outbox
    enqueueing fails, satisfying BT-14-001.  No-op paths (empty recipient
    list) return SUCCESS to avoid blocking downstream BT steps that do not
    depend on broadcast completion.

    Blackboard keys shared across all four nodes:

    - ``broadcast_case_manager_id``: Case Manager actor ID
    - ``broadcast_peer_recipient_ids``: filtered peer actor ID list
    - ``broadcast_activity_id``: created activity ID (absent when no-op)

    The caller must execute the tree via
    :meth:`~vultron.core.behaviors.bridge.BTBridge.execute_with_setup` so
    that ``datalayer``, ``actor_id``, and (when broadcasting)
    ``trigger_activity_factory`` are present on the blackboard.

    Args:
        case_id: ID of the
            :class:`~vultron.wire.as2.vocab.objects.vulnerability_case.VulnerabilityCase`
            whose CASE_MANAGER should originate the broadcast.
        sender_actor_id: Actor ID of the entity whose update is being
            forwarded; excluded from the recipient set.
        activity_builder: ``(factory, case_manager_id, recipient_ids) ->
            activity_id`` — called by
            :class:`~vultron.core.behaviors.broadcast.nodes.CreateBroadcastActivityNode`
            with the resolved factory instance, Case Manager actor ID, and
            filtered recipient list.  Must create and persist the outbound
            AS2 activity and return its ID as a ``str``.
        name: Optional name override for the root Sequence node.

    Returns:
        Root node of the fail-fast peer broadcast Sequence.
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
