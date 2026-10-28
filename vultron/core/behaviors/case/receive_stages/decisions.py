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

"""What the CASE_MANAGER decides after the door guards, before the act.

The clock decisions (CLP-10-025) and the answer to the ledger position the
received activity stamps (SYNC-18-007).  Split out of
``receive_activity_tree.py`` (CS-18-001).
"""

import py_trees

from vultron.core.behaviors.case.case_clock_decisions import (
    case_clock_decisions,
)
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    create_clock_decision_gate,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.lifecycle import (
    CommitCaseLedgerEntryNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    PostCloseExemption,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
)
from vultron.core.behaviors.exemption_registry import require_registered
from vultron.core.behaviors.sender_guard import (
    SenderCheckContext,
    SenderContext,
)
from vultron.core.behaviors.sync.ledger_position_stage import (
    create_ledger_position_stage,
)
from vultron.core.behaviors.sync.nodes.ledger_position import (
    LEDGER_POSITION_EXEMPTIONS,
    LedgerPositionExemption,
)
from vultron.errors import VultronWiringError


def clock_decision_stage(
    name: str,
    case_id: str | None,
    decisions: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
    post_close_exemption: PostCloseExemption | None,
) -> CaseManagerGate:
    """The tree's clock decisions, run only at the case's CASE_MANAGER.

    A clock decision commits only CASE_MANAGER-authored entries, one for each
    AS2 activity that expresses what it decided, and the changes they record,
    so it may hold neither the received activity's commit node nor the
    guarded-commit subtree around it (CLP-10-025): either would commit the
    activity's own assertion before the guards judge it.

    It writes, so both door guards must run first: the sender guard, so a
    sender with no standing never makes the CASE_MANAGER write (HP-01-006),
    and the post-close boundary, so nothing is recorded once the case is
    fully closed (CM-23-013).  A tree with no sender guard or with a
    post-close exemption cannot take clock decisions.

    The gate reads a case this store does not hold as "not the CASE_MANAGER"
    at ``debug`` level: a replica, or an invitee holding only a stub, never
    computes a clock decision (CM-28-014).

    Raises:
        VultronWiringError: *case_id* is ``None`` — there is no case whose
            CASE_MANAGER could take the decision — the tree has no sender
            guard or is exempt from the post-close boundary, or a decision
            holds the received activity's commit.
    """
    where = f"create_receive_activity_tree({name})"
    if case_id is None:
        raise VultronWiringError(
            f"{where}: clock_decisions need a case_id or manager_case_id,"
            " the case whose CASE_MANAGER takes them (CLP-10-025)"
        )
    if not sender_guarded:
        raise VultronWiringError(
            f"{where}: clock_decisions need a sender_rule, so the sender"
            " guard runs before the CASE_MANAGER writes (HP-01-006,"
            " CLP-10-025)"
        )
    if post_close_exemption is not None:
        raise VultronWiringError(
            f"{where}: clock_decisions cannot run on a tree exempt from the"
            f" post-close boundary ({post_close_exemption.name}); nothing is"
            " recorded once the case is fully closed (CM-23-013, CLP-10-025)"
        )
    activity_commits = sorted(
        {
            type(n).__name__
            for root in decisions
            for n in root.iterate()
            if isinstance(n, CommitCaseLedgerEntryNode)
        }
    )
    if activity_commits:
        raise VultronWiringError(
            f"{where}: a clock decision commits only its own entry, never"
            f" the received activity; found {activity_commits} (CLP-10-025)"
        )
    return create_clock_decision_gate(case_id, decisions)


def case_and_tree_decisions(
    case_id: str | None,
    tree_decisions: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
    post_close_exemption: PostCloseExemption | None,
) -> list[py_trees.behaviour.Behaviour]:
    """The case-wide clock decisions, then the tree's own.

    The case-wide decisions (the embargo end-time check, EMB-13-003) run on
    every tree that names a case, has a sender guard and keeps the
    post-close boundary, because both door guards must run before the
    CASE_MANAGER writes (HP-01-006, CM-23-013).  A tree with no sender guard
    takes them once it declares its sender rule (HP-01-008); a tree exempt
    from the post-close boundary never does.  The tree's own
    decisions are returned as given, so :func:`clock_decision_stage`
    refuses them on a tree where they cannot run.
    """
    if case_id is None or not sender_guarded or post_close_exemption:
        return tree_decisions
    return [*case_clock_decisions(case_id), *tree_decisions]


def ledger_position_stage(
    name: str,
    intake: IntakeReceivedActivityNode,
    sender_context: SenderContext | None,
    exemption: LedgerPositionExemption | None,
) -> list[py_trees.behaviour.Behaviour]:
    """The CASE_MANAGER's answer to the sender's stamped ledger position.

    Placed in every tree whose sender guard checks a named sender against a
    named case, the case and sender the position is about (SYNC-18-004,
    SYNC-18-005, SYNC-18-007).  A tree with no sender guard (a subtree of
    one that has it, or a tree that names no case) has no position to
    answer; a tree whose sender and case are read from a received ledger
    activity at run time is about an activity outside SYNC-18-001's scope.
    A tree that answers the position itself names a registered *exemption*.
    A redelivery that *intake* found already archived is not answered again
    (SYNC-18-002).

    Raises:
        VultronWiringError: *exemption* is not registered in
            ``LEDGER_POSITION_EXEMPTIONS``.
    """
    if exemption is not None:
        require_registered(
            exemption,
            LEDGER_POSITION_EXEMPTIONS,
            where=f"create_receive_activity_tree({name})",
            kind="ledger-position",
            registry_name="LEDGER_POSITION_EXEMPTIONS",
            spec_id="SYNC-18-007",
        )
        return []
    if not isinstance(sender_context, SenderCheckContext):
        return []
    if sender_context.case_id is None:
        return []
    return [
        create_ledger_position_stage(
            sender_context.case_id,
            sender_context.sender_id,
            is_redelivery=lambda: bool(intake.found_ids),
        )
    ]
