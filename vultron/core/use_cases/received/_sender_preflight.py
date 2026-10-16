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

"""Ask the closed-sender guard before a handler's first write (CM-23-018).

:func:`closed_sender_preflight` runs the factory's post-close boundary
(:class:`~vultron.core.behaviors.case.nodes.post_close.CaseOpenToExternalWritesNode`)
and :func:`~vultron.core.behaviors.sender_guard.closed_sender_guard` as a
one-node tree, for a handler whose sender guard does not ask whether the case
already records the sender's closure.  It is the chained shape CLP-10-005
forbids (ADR-0135); #4773 composes the guard into its callers' trees, so no
new caller is added.
"""

import py_trees

from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
)
from vultron.core.behaviors.sender_guard import (
    case_owner_guard,
    closed_sender_guard,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received._bt_verdict import verdict_from_bt


def closed_sender_preflight(
    dl: CasePersistence,
    receiving_actor_id: str,
    request: VultronEvent,
    *,
    case_id: str | None,
    sender_actor_id: str,
    closes: bool,
    label: str,
    sync_port: SyncActivityPort | None = None,
    case_owner_completes: bool = False,
) -> HandlerResult | None:
    """The verdict owed to a sender whose closure the case records, or ``None``.

    For a handler whose sender guard does not ask
    :func:`~vultron.core.participants.recipients.may_act_on_case` (an
    invitee's reply), or whose act may close its sender.  When the case
    already records the sender's closure (CM-23-018):

    - an act that would close it again (*closes*: a
      ``Leave(VulnerabilityCase)``, a ``Close(Report)``, a ``Reject`` of a
      stub or full-case Invite) changes nothing, so it is ``SKIPPED``,
      whatever its activity id (ID-05-003);
    - any other act is ``REFUSED``.

    Either way nothing is committed or sent.  Otherwise ``None``, and the
    handler runs its tree.

    A *case_id* this store does not resolve records no closure.  The
    post-close boundary is asked first: on a fully closed case the act is
    left to the tree, which drops it (CM-23-013).

    With *case_owner_completes*, a closing act from the case's Case Owner is
    not a repeat: its effect is the case's closure too, which a failed first
    delivery may have left incomplete, so its redelivery runs the tree to
    complete it (a ``Leave``, CM-23-002).  The owner is asked in the same
    run, only when the sender's closure is recorded.  On a fully closed case
    the post-close boundary still decides first.

    Raises:
        VultronBTInternalError: The guard failed on an internal error.
    """
    if not case_id:
        return None
    guard = closed_sender_guard(case_id, sender_actor_id)
    # A closing act from the Case Owner is asked about in the same run: the
    # owner check runs only when the guard finds the sender closed.
    owner = (
        case_owner_guard(case_id, sender_actor_id)
        if closes and case_owner_completes
        else None
    )
    check: py_trees.behaviour.Behaviour = (
        guard
        if owner is None
        else py_trees.composites.Selector(
            name="SenderOpenOrClosingCaseOwner",
            memory=False,
            children=[guard, owner],
        )
    )
    tree = py_trees.composites.Sequence(
        name="ClosedSenderPreflight",
        memory=False,
        children=[CaseOpenToExternalWritesNode(case_id=case_id), check],
    )
    result = BTBridge(datalayer=dl, sync_port=sync_port).execute_with_setup(
        tree=tree, actor_id=receiving_actor_id, activity=request
    )
    # Raises on an internal error, the owner check's included: a crash is
    # never read as "not the Case Owner" (ARCH-15-001).
    verdict_from_bt(tree, result, label="ClosedSenderPreflight")
    if not guard.sender_closed:
        return None
    if owner is not None and owner.status is py_trees.common.Status.SUCCESS:
        return None
    if closes:
        return HandlerResult.skipped(
            f"{label}: {guard.feedback_message} — a repeat of a closing act,"
            " nothing to apply (ID-05-003)"
        )
    return HandlerResult.refused(
        f"{label}: {guard.feedback_message} — it may act on nothing further"
    )
