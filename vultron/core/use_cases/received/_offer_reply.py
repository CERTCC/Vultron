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

"""Run the received tree of a reply to an Offer the CASE_MANAGER recorded.

A reply to an Offer the CASE_MANAGER relays — the target's ``Accept`` or
``Reject``, or the offerer's ``Undo`` — is handled the same way whatever the
Offer: an ownership-transfer Offer (CM-21) or a role Offer (CM-33).

:func:`run_offer_reply_tree` runs the reply's one received tree as the
receiving actor (CLP-10-005, ADR-0135).  The tree's factory composes every
outcome, a reply that names no case included: that tree archives the reply
and refuses it (CLP-10-018).  The handler's *refine* reads the verdict,
reporting a redelivery of the reply that closed the Offer as ``SKIPPED``
(HP-01-003), and a refusal is logged at WARNING with the sender and the case.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import (
    HandlerDisposition,
    HandlerResult,
)
from vultron.core.ports.case_outbox import CaseOutboxPersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases._helpers import resolve_receiving_actor_id
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

#: Reads a finished reply tree's verdict more closely, e.g. a redelivery.
VerdictRefinement = Callable[
    [py_trees.behaviour.Behaviour, HandlerResult], HandlerResult
]


def run_offer_reply_tree(
    *,
    dl: CaseOutboxPersistence,
    request: VultronEvent,
    tree: py_trees.behaviour.Behaviour,
    label: str,
    case_id: str | None,
    subject: str,
    refine: VerdictRefinement,
    sync_port: SyncActivityPort | None,
    wire_render_port: "WireRenderPort | None",
    trigger_activity: "TriggerActivityPort | None" = None,
    applied_note: str | None = None,
) -> HandlerResult:
    """Run the received tree of a reply to an Offer and read its verdict.

    Args:
        dl: The receiving actor's store.
        request: The received reply.
        tree: The reply's received tree, as its factory composed it for
            the case the reply names (or names none).
        label: The tree's name, for the verdict and the logs.
        case_id: The case the reply names, for the logs.
        subject: The Offer, as a log names it, e.g. ``"role offer"``.
        refine: Reads what the tree's guards say beyond success or failure,
            such as a redelivery reported ``SKIPPED`` (HP-01-003).
        sync_port: Delivers the entries the tree commits.
        wire_render_port: Renders the activities the tree builds.
        trigger_activity: Builds the CASE_MANAGER's own entries for the
            changes an applied reply causes.
        applied_note: When given, an applied reply is logged at INFO with it.
    """
    result = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree,
        actor_id=resolve_receiving_actor_id(dl, request.receiving_actor_id),
        activity=request,
    )
    verdict = refine(tree, verdict_from_bt(tree, result, label=label))
    if verdict.disposition is HandlerDisposition.REFUSED:
        logger.warning(
            "%s refused '%s' from '%s' for case '%s': %s",
            label,
            request.activity_id,
            request.actor_id,
            case_id,
            verdict.reason,
        )
    elif applied_note and verdict.disposition is HandlerDisposition.APPLIED:
        logger.info(
            "Actor '%s' %s %s '%s' for case '%s'",
            request.actor_id,
            applied_note,
            subject,
            request.object_id,
            case_id,
        )
    return verdict


__all__ = [
    "VerdictRefinement",
    "run_offer_reply_tree",
]
