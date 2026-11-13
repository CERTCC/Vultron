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

"""The door guards of a received tree (CLP-10-010, HP-01-005, CM-23-013).

In ADR-0154's order: the addressee check, the seen-before door, the
held-case door of an act that names its case (AKM-03-006), the path
stage, the post-close guard, the closed-sender check, any case resolution and
the sender guard.  Intake follows them, so nothing is written before the last
door admits the message.
Split out of ``receive_activity_tree.py`` (CS-18-005).
"""

from collections.abc import Collection

import py_trees

from vultron.core.behaviors.case.nodes.addressee import (
    ADDRESSEE_EXEMPTIONS,
    ActivityAddressedToReceiverNode,
    AddresseeExemption,
)
from vultron.core.behaviors.case.nodes.case_lookup import CaseResolving
from vultron.core.behaviors.case.nodes.held_case import (
    CaseNamedByReference,
    ReceiverHoldsNamedCaseNode,
)
from vultron.core.behaviors.case.nodes.post_close import (
    CaseOpenToExternalWritesNode,
    PostCloseExemption,
)
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    declared_paths,
)
from vultron.core.behaviors.case.nodes.seen_before import (
    ActivityNotSeenBeforeNode,
)
from vultron.core.behaviors.case.receive_stages.guards import refusal_stage
from vultron.core.behaviors.emit_capable import EmitCapable
from vultron.core.behaviors.exemption_registry import require_registered
from vultron.core.behaviors.sender_entitlement import SenderRule
from vultron.core.behaviors.sender_guard import (
    ClosedSenderCheck,
    LedgerActivityContext,
    SenderCheckContext,
    SenderContext,
    closed_sender_door,
    compose_sender_guard,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.errors import VultronWiringError


def addressee_stage(
    name: str, exemption: AddresseeExemption | None
) -> list[py_trees.behaviour.Behaviour]:
    """The addressee door guard, labelled with the tree's name (HP-01-005).

    Nothing for a tree that passes a registered exemption.

    Raises:
        VultronWiringError: *exemption* is not registered in
            ``ADDRESSEE_EXEMPTIONS``.
    """
    if exemption is None:
        return [ActivityAddressedToReceiverNode(label=name)]
    require_registered(
        exemption,
        ADDRESSEE_EXEMPTIONS,
        where=f"create_receive_activity_tree({name})",
        kind="addressee",
        registry_name="ADDRESSEE_EXEMPTIONS",
        spec_id="HP-01-005",
    )
    return []


def check_nested(
    name: str,
    *,
    addressee_exemption: AddresseeExemption | None,
    post_close_exemption: PostCloseExemption | None,
    has_sender_rule: bool = False,
) -> None:
    """Refuse a nested tree that would run a door its enclosing tree ran.

    A nested tree runs after its enclosing tree's intake, so the record is
    already in holding: a post-close stage there would read the first run as
    a re-run (``began_in_an_earlier_run`` before intake) and skip its reply,
    and an addressee check would ask again what the enclosing door answered.
    So a nested tree names both exemptions (ADR-0154).  It takes no sender
    rule either: the sender guard brings the ledger-position and
    sender-sequence stages, which would answer the delivery a second time
    on its first run (SYNC-18-009, SYNC-21-018).

    Raises:
        VultronWiringError: either exemption is missing, or a sender rule is
            given.
    """
    missing = [
        argument
        for argument, value in (
            ("addressee_exemption", addressee_exemption),
            ("post_close_exemption", post_close_exemption),
        )
        if value is None
    ]
    if missing:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): a nested tree runs on its"
            f" enclosing tree's doors, so it needs {', '.join(missing)}"
            " (ADR-0154)"
        )
    if has_sender_rule:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): a nested tree runs on its"
            " enclosing tree's sender guard, so it takes no sender_rule: its"
            " own would answer the ledger position and the sender's number"
            " again (ADR-0154)"
        )


def seen_before_stage(
    name: str, *, nested: bool = False
) -> list[py_trees.behaviour.Behaviour]:
    """The seen-before door, labelled with the tree's name (ADR-0154).

    Every received tree carries it, after the addressee check: a resend is
    answered from the message's record before intake writes anything, and no
    tree opts out.  A *nested* received tree has none: its enclosing tree's
    door answered the delivery (``create_receive_activity_tree(nested=True)``).
    """
    if nested:
        return []
    return [ActivityNotSeenBeforeNode(label=name)]


def held_case_stage(
    name: str,
    case_id: str | None,
    act: CaseNamedByReference | None,
    *,
    nested: bool = False,
) -> list[py_trees.behaviour.Behaviour]:
    """The held-case door of a tree whose act names its case (AKM-03-006).

    Nothing for a tree that passes no *act*.  Placed after the seen-before
    door and before the path stage: an act that names a case this receiver
    does not hold is refused naming the activity and the case, which the
    path stage's no-case reason does not (AKM-03-006, HP-01-039).

    Raises:
        VultronWiringError: *act* is given to a tree that names no case to
            check, or to a nested tree, whose enclosing tree's doors ran.
    """
    if act is None:
        return []
    where = f"create_receive_activity_tree({name})"
    if nested:
        raise VultronWiringError(
            f"{where}: a nested tree runs on its enclosing tree's doors, so"
            " the held-case door belongs to the enclosing tree (ADR-0154)"
        )
    if not case_id:
        raise VultronWiringError(
            f"{where}: held_case needs the case the act names, as case_id,"
            " manager_case_id or the sender context's case (AKM-03-006)"
        )
    return [ReceiverHoldsNamedCaseNode(act=act, case_id=case_id)]


def post_close_stage(
    name: str,
    guard_case_id: str | None,
    exemption: PostCloseExemption | None,
    reply: list[py_trees.behaviour.Behaviour],
) -> list[py_trees.behaviour.Behaviour]:
    """The post-close write-boundary guard, with its optional reply.

    Returns the nodes to place beside the sender guard, ahead of it: nothing
    for an exempt tree, the bare :class:`CaseOpenToExternalWritesNode` when
    the tree owes no reply, or a refusal stage that runs *reply* only when
    the guard refuses (CM-23-013).  Whether a closed case takes the write is
    a question about the case, asked once the message is known to be for
    the receiver (ADR-0154).

    Raises:
        VultronWiringError: an exempt tree passes a reply (the reply could
            never run), or a reply node is not emit-capable or writes state.
    """
    if exemption is not None:
        if reply:
            raise VultronWiringError(
                f"create_receive_activity_tree({name}): post_close_reply"
                f" needs the post-close guard, but the tree is exempt"
                f" ({exemption}) (CM-23-013)"
            )
        return []
    guard = CaseOpenToExternalWritesNode(
        case_id=guard_case_id, name="CaseOpenToExternalWrites"
    )
    if not reply:
        return [guard]
    return [
        refusal_stage(
            name,
            [guard],
            reply,
            guard_case_id,
            # The post-close stage is a door, ahead of intake (ADR-0154).
            intake_ran=False,
            stage_name="PostCloseStage",
            guards_name="PostCloseGuard",
            gate_suffix="PostCloseReplyIfCaseManager",
            argument="post_close_reply",
        )
    ]


def path_stage_case_id(
    case_id: str | None,
    manager_case_id: str | None,
    sender_context: SenderContext | None,
) -> str | None:
    """The case the path stage reads the receiver's role in (ADR-0153).

    The tree's commit case, else the case whose CASE_MANAGER gates its
    effects, else the case its sender context names — the same case the
    sender guard judges the sender against, which is the case the activity
    is about even in a tree that commits nothing (HP-01-025).  ``None`` for
    a tree that names no case at build time; the stage then resolves it at
    run time, from the blackboard or the activity, and reads a case it
    cannot find as the no-case path.
    """
    if case_id is not None:
        return case_id
    if manager_case_id is not None:
        return manager_case_id
    if isinstance(sender_context, SenderCheckContext):
        return sender_context.case_id
    return None


def received_path_stage(
    name: str,
    case_id: str | None,
    paths: Collection[ReceivedPath] | None,
    *,
    case_resolved_at_run_time: bool = False,
    sender_rule: SenderRule | None = None,
) -> ReceivedPathNode | None:
    """The path door stage of a tree that declared its paths (ADR-0153).

    Placed after the addressee check and before the sender guard
    (CLP-10-010, HP-01-012): one role question picks the manager,
    participant-replica or no-case path, the sender guard reads that answer
    instead of asking again, and a path the message type did not declare is
    refused there, with the reason the stage composes from the resolved path
    and the declaration (HP-01-005, HP-01-039).

    The node takes no case: the caller seeds its ``/case_id`` port with
    *case_id* (:func:`~vultron.core.behaviors.case_id_scope.with_case_id`,
    BTND-01-006) where it places the stage, and *case_id* is read here only
    to refuse a tree whose case nothing ahead of the stage could name.

    ``None`` for a tree that declares no paths; such a tree may compose
    only a sender rule whose sides name the same kinds (HP-01-036).

    Raises:
        VultronWiringError: The declaration names no path — a tree that
            handles no path would refuse every delivery, so an empty
            declaration is a wiring mistake, not a path stage — or the tree
            names no case at build time, resolves it with
            ``case_resolution``, which runs *after* this stage, and declares
            a path other than the no-case one: nothing ahead of the stage
            names the case, so it reads the role only in a case the activity
            itself names, and an in-case declaration would refuse every other
            delivery at the stage.  Declaring the no-case path alone is
            admitted only when *sender_rule*'s ``outside_case`` side admits
            no sender: the delivery then passes the stage on the no-case
            path and the guard refuses it (HP-01-036), so a case that
            ``case_resolution`` finds later can never admit a sender on the
            outside-case side while the receiver sits in that case.
    """
    if paths is None:
        return None
    declared = declared_paths(paths)
    where = f"create_receive_activity_tree({name})"
    if not declared:
        raise VultronWiringError(
            f"{where}: paths must name at least one ReceivedPath (ADR-0153)"
        )
    if (
        case_id is None
        and case_resolved_at_run_time
        and declared != {ReceivedPath.NO_CASE}
    ):
        raise VultronWiringError(
            f"{where}: the path stage runs before case_resolution, so a tree"
            " whose case only that stage resolves has no case to read the"
            " receiver's role in; name the case at build time or declare the"
            " no-case path alone (ADR-0153, HP-01-025)"
        )
    if (
        case_id is None
        and case_resolved_at_run_time
        and sender_rule is not None
        and sender_rule.outside_case
    ):
        raise VultronWiringError(
            f"{where}: a tree whose case only case_resolution resolves passes"
            " the stage on the no-case path, so its rule's outside_case side"
            " must admit no sender, or a case found later would be judged on"
            " that side (HP-01-036, HP-01-025)"
        )
    return ReceivedPathNode(declared=declared, label=name)


def closed_sender_stage(
    name: str, case_id: str | None, check: ClosedSenderCheck
) -> py_trees.behaviour.Behaviour:
    """The closed-sender door guard on the tree's case (CM-23-018).

    Raises:
        VultronWiringError: The tree names no case to check the sender's
            closure on.
    """
    if case_id is None:
        raise VultronWiringError(
            f"create_receive_activity_tree({name}): closed_sender needs the"
            " tree's case_id or manager_case_id (CM-23-018)"
        )
    return closed_sender_door(case_id, check)


def case_resolution_stage(
    name: str,
    steps: list[py_trees.behaviour.Behaviour],
    *,
    sender_guarded: bool,
) -> list[py_trees.behaviour.Behaviour]:
    """The steps that resolve the case the sender guard reads (HP-01-025).

    They run just before the sender guard, ahead of intake, so they may
    only read: a sender with no standing must leave nothing behind
    (HP-01-006).  A step may publish what it resolved on the blackboard
    (``/case_id``), which is not a DataLayer write.  Not every writer carries
    a marker (a ledger commit, replication state), so a step is admitted by
    the :class:`~vultron.core.behaviors.case.nodes.case_lookup.CaseResolving`
    marker on each of its leaves, and refused if any node in it is also
    marked as a state writer or an emitter.

    Raises:
        VultronWiringError: steps are given without a sender guard to run
            them for, or a step holds a leaf without the ``CaseResolving``
            marker, a state writer or an emit-capable node.
    """
    if not steps:
        return []
    where = f"create_receive_activity_tree({name})"
    if not sender_guarded:
        raise VultronWiringError(
            f"{where}: case_resolution resolves the case the sender guard"
            " reads; pass it only with a sender_rule (HP-01-025)"
        )
    nodes = [n for root in steps for n in root.iterate()]
    refused = sorted(
        {
            type(n).__name__
            for n in nodes
            if isinstance(n, (StateWriteCapable, EmitCapable))
            or (not n.children and not isinstance(n, CaseResolving))
        }
    )
    if refused:
        raise VultronWiringError(
            f"{where}: case_resolution runs before the sender guard, so it"
            " may only read; each leaf must be a CaseResolving node that"
            f" writes no state and emits nothing; found {refused}"
            " (HP-01-006)"
        )
    return steps


def sender_guard_stage(
    name: str,
    case_id: str | None,
    manager_case_id: str | None,
    sender_rule: SenderRule | None,
    sender_context: SenderContext | None,
    path_stage: ReceivedPathNode | None = None,
) -> py_trees.behaviour.Behaviour | None:
    """The tree's sender guard, composed from the declared rule (HP-01-025).

    A tree that commits (``case_id`` set) must judge the sender against that
    case, and a tree that commits nothing but writes for a CASE_MANAGER
    (*manager_case_id*, the close-case tree) against that one; a tree with
    neither judges it against the case its *sender_context* names.  A
    :class:`~vultron.core.behaviors.sender_guard.LedgerActivityContext`
    reads the case from the activity at run time, so it is given only to a
    tree with no commit case at build time.

    With *path_stage* the rule's side is selected from the path that stage
    resolved, so the role question is asked once (HP-01-036).
    """
    if sender_rule is None:
        if sender_context is not None:
            raise VultronWiringError(
                f"{name}: sender_context is given without a sender_rule"
            )
        return None
    if sender_context is None:
        raise VultronWiringError(
            f"{name}: sender_rule needs a sender_context (HP-01-025)"
        )
    if isinstance(sender_context, LedgerActivityContext):
        context_case, tree_case = None, case_id
    else:
        context_case = sender_context.case_id
        tree_case = case_id or manager_case_id
    if tree_case is not None and context_case != tree_case:
        raise VultronWiringError(
            f"{name}: sender_context names case {context_case!r}"
            f" but the tree's case is {tree_case!r} (HP-01-025)"
        )
    return compose_sender_guard(sender_rule, sender_context, path_stage)
