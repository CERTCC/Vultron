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

- :func:`refuse_reply_naming_no_case` archives a reply that names no case
  and refuses it, before any tree that needs a case is built (CLP-10-018).
- :func:`run_offer_reply_tree` runs the reply's received tree as the
  receiving actor and reads its verdict: the handler's *refine* reports a
  redelivery of the reply that closed the Offer as ``SKIPPED`` (HP-01-003),
  and a refusal is logged at WARNING with the sender and the case.
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
from vultron.core.use_cases.received._bt_verdict import (
    applied_or_raise,
    verdict_from_bt,
)
from vultron.core.use_cases.received._intake_only import run_intake_only

if TYPE_CHECKING:
    from vultron.core.ports.trigger_activity import TriggerActivityPort
    from vultron.core.ports.wire_render import WireRenderPort

logger = logging.getLogger(__name__)

#: Reads a finished reply tree's verdict more closely, e.g. a redelivery.
VerdictRefinement = Callable[
    [py_trees.behaviour.Behaviour, HandlerResult], HandlerResult
]


def refuse_reply_naming_no_case(
    *,
    dl: CaseOutboxPersistence,
    request: VultronEvent,
    label: str,
    verb: str,
    subject: str,
    sync_port: SyncActivityPort | None,
    wire_render_port: "WireRenderPort | None",
) -> HandlerResult:
    """Archive a reply (*verb*) to an Offer (*subject*) naming no case; refuse it.

    Intake archives what arrived even when it is refused (CLP-10-018); no
    other tree runs, since there is no case to act on.
    """
    tree, result = run_intake_only(
        dl,
        request,
        name=label,
        sync_port=sync_port,
        wire_render_port=wire_render_port,
    )
    applied_or_raise(tree, result, label=label)
    logger.warning(
        "%s(%s): '%s' from '%s' names no case",
        verb,
        subject,
        request.activity_id,
        request.actor_id,
    )
    return HandlerResult.refused(f"{verb}({subject}) names no case")


def run_offer_reply_tree(
    *,
    dl: CaseOutboxPersistence,
    request: VultronEvent,
    tree: py_trees.behaviour.Behaviour,
    label: str,
    case_id: str,
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
        tree: The reply's received tree.
        label: The tree's name, for the verdict and the logs.
        case_id: The case the reply names.
        subject: The Offer, as a log names it, e.g. ``"role offer"``.
        refine: Reads what the tree's guards say beyond success or failure,
            such as a redelivery reported ``SKIPPED`` (HP-01-003).
        sync_port: Delivers the entries the tree commits.
        wire_render_port: Renders the activities the tree builds.
        trigger_activity: Builds the CASE_MANAGER's own entries for the
            changes an applied reply causes.
        applied_note: When given, an applied reply is logged at INFO with it.
    """
    receiving_actor_id = resolve_receiving_actor_id(
        dl, request.receiving_actor_id
    )
    result = BTBridge(
        datalayer=dl,
        trigger_activity=trigger_activity,
        wire_render_port=wire_render_port,
        sync_port=sync_port,
    ).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id, activity=request
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
    "refuse_reply_naming_no_case",
    "run_offer_reply_tree",
]
