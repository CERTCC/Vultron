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

"""Compose a sender guard from a declared :class:`SenderRule` (HP-01-025),
and tell whether a received tree's run ended at it.
"""

from collections.abc import Callable

import py_trees
from py_trees.common import Status

from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
    on_any_of_paths,
)
from vultron.core.behaviors.sender_check_context import (
    LedgerActivityContext,
    SenderContext,
)
from vultron.core.behaviors.sender_entitlement import (
    AddresseeSide,
    NoSenderAdmittedNode,
    SenderEntitlementKind,
    SenderHoldsNoneOfNode,
    SenderRule,
    in_declaration_order,
)
from vultron.core.behaviors.sender_guard.kind_nodes import (
    _kind_node,
    _ledger_kind_node,
)
from vultron.errors import VultronWiringError

#: The names :func:`compose_sender_guard` gives the composites it builds.
_RULE_GUARD = "SenderRuleGuard"
_ANY_OF = "AnyOfSenderKinds"

#: The attribute :func:`compose_sender_guard` sets on the guard it returns,
#: so :func:`sender_guard_refused` knows that node by its origin, never by
#: its name or type: another sender node at the root is not the guard.
_COMPOSED_GUARD_MARK = "_vultron_composed_sender_guard"


def is_composed_sender_guard(node: py_trees.behaviour.Behaviour) -> bool:
    """*node* is the guard :func:`compose_sender_guard` returned.

    Read from the mark the factory set, so the guard is known by its origin
    and not by its name, its type, or the checks inside it.  That is what
    the levels ratchet asks of a door: a composed guard reads the level of
    every refusal inside it from its own placement (SL-03-002), whether or
    not any check in it happens to be a
    :class:`~vultron.core.behaviors.sender_entitlement.SenderEntitlementConditionNode`
    (#5786).
    """
    return getattr(node, _COMPOSED_GUARD_MARK, False) is True


def sender_guard_refused(root: py_trees.behaviour.Behaviour) -> bool:
    """True when a received tree's run ended at its composed sender guard.

    The factory places the guard as one child of the tree's root Sequence
    (HP-01-025); the run ended there when the first child that failed is
    that guard.  A sender node deeper in the tree, which picks an effect
    after admission, is not it.  A handler that answers a refused assertion
    (a processing fault, say) asks this first: a sender with no standing is
    owed no answer about its content (HP-01-006).
    """
    for child in root.children:
        if child.status is Status.FAILURE:
            return is_composed_sender_guard(child)
    return False


def _any_of(
    kinds: frozenset[SenderEntitlementKind],
    node_for: Callable[[SenderEntitlementKind], py_trees.behaviour.Behaviour],
    side: str,
) -> py_trees.behaviour.Behaviour | None:
    """The guard for one side: ``None`` when it admits any actor."""
    if not kinds:
        return NoSenderAdmittedNode(side=side)
    if SenderEntitlementKind.ANY_ACTOR in kinds:
        return None
    nodes = [node_for(kind) for kind in in_declaration_order(kinds)]
    if len(nodes) == 1:
        return nodes[0]
    # The last arm fails naming every kind, so the refusal reason is the
    # side's whole rule rather than the last kind tried (BT-13-001).
    return py_trees.composites.Selector(
        name=_ANY_OF,
        memory=False,
        children=[*nodes, SenderHoldsNoneOfNode(kinds)],
    )


def _or_pass(
    guard: py_trees.behaviour.Behaviour | None, name: str
) -> py_trees.behaviour.Behaviour:
    """*guard*, or a success leaf for a side that admits any actor."""
    if guard is not None:
        return guard
    return py_trees.behaviours.Success(name=f"{name}AnyActor")


def compose_sender_guard(
    rule: SenderRule,
    ctx: SenderContext,
    path_stage: ReceivedPathNode | None = None,
) -> py_trees.behaviour.Behaviour | None:
    """Compose the guard *rule* requires for the activity *ctx* describes.

    Each side of the rule is the standing a sender needs on one received
    path, and the path the stage resolved picks it (HP-01-036, ADR-0153):

    - ``at_case_manager`` on the manager path,
    - ``at_participant`` on the participant-replica path,
    - ``outside_case`` on the no-case path.

    Only the paths the stage declares are judged, since the stage refuses
    any other before this guard runs (CLP-10-010).  When those paths' sides
    name the same kinds, the guard is that one side and reads no path.
    Otherwise it has one arm per distinct side, each read off the stage's
    answer, so the role question is asked once (HP-01-036).  What the
    context names never picks the side.

    A context that names no case, in a tree declaring only in-case paths,
    composes its in-case checks with no case at build time: such a check
    reads ``/case_id`` or the activity at run time, and one that cannot
    (an ``AUTHOR`` check on a participant record, say) raises here.  The
    combination is not refused outright, because each such tree's stage
    reads its case from the activity, which names none, so the stage
    refuses the delivery first; making those case-scoped types declare the
    no-case path instead would go against HP-01-041.

    Args:
        rule: The use case's declared sender rule.
        ctx: The sender and the records its kinds are checked against, or a
            :class:`LedgerActivityContext` for an activity whose case the
            ledger entry it carries names.  A ledger activity's sides are
            picked by the path like any other's; their nodes read the case
            from the entry at run time (HP-01-024, HP-01-036).
        path_stage: The tree's path door stage.  A tree with no stage can
            compose only a rule whose three sides name the same kinds, since
            nothing then says which path the receiver is on.

    Returns:
        The guard, or ``None`` when every judged side admits any actor.

    Raises:
        VultronWiringError: The rule's sides differ and no path stage picks
            one (HP-01-036); the context lacks a record a kind needs: an
            ``INVITEE`` kind without ``invite_id``, a ``NAMED_ACTOR`` kind
            without ``request``, an ``AUTHOR`` kind without
            ``authored_object``, or a case-scoped check without
            ``case_id``; or a ledger activity's rule declares a kind that
            cannot read the case at run time.
    """
    guard = _compose(rule, ctx, path_stage)
    if guard is not None:
        setattr(guard, _COMPOSED_GUARD_MARK, True)
    return guard


#: The side of a rule each received path reads (HP-01-036, ADR-0153).
_SIDE_ON_PATH: dict[ReceivedPath, AddresseeSide] = {
    ReceivedPath.CASE_MANAGER: AddresseeSide.CASE_MANAGER,
    ReceivedPath.PARTICIPANT_REPLICA: AddresseeSide.PARTICIPANT,
    ReceivedPath.NO_CASE: AddresseeSide.OUTSIDE_CASE,
}

#: Each path's arm name and the receiver it names in a refusal reason.
_ARM_NAME: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: "AtCaseManager",
    ReceivedPath.PARTICIPANT_REPLICA: "AtParticipant",
    ReceivedPath.NO_CASE: "OutsideCase",
}
_RECEIVER: dict[ReceivedPath, str] = {
    ReceivedPath.CASE_MANAGER: "the CASE_MANAGER",
    ReceivedPath.PARTICIPANT_REPLICA: (
        "a participant other than the CASE_MANAGER"
    ),
    ReceivedPath.NO_CASE: (
        "a receiver with no case to act on for this activity (the tree names"
        " no case this store holds)"
    ),
}
_IN_CASE = frozenset(
    {ReceivedPath.CASE_MANAGER, ReceivedPath.PARTICIPANT_REPLICA}
)


def _receiver_of(paths: frozenset[ReceivedPath]) -> str:
    """The receiver *paths* put the guard at, for a refusal reason."""
    if paths == _IN_CASE:
        return "a case actor"
    return " or ".join(
        _RECEIVER[path] for path in ReceivedPath if path in paths
    )


def _arm_name(paths: frozenset[ReceivedPath]) -> str:
    return "Or".join(_ARM_NAME[path] for path in ReceivedPath if path in paths)


def _sides(
    rule: SenderRule, path_stage: ReceivedPathNode | None
) -> list[tuple[frozenset[ReceivedPath], frozenset[SenderEntitlementKind]]]:
    """The judged paths grouped by the kinds their side names.

    In the enum's order, so the built guard reads the same whatever order a
    declaration listed its paths in.
    """
    judged = (
        frozenset(ReceivedPath) if path_stage is None else path_stage.declared
    )
    groups: dict[frozenset[SenderEntitlementKind], set[ReceivedPath]] = {}
    for path in ReceivedPath:
        if path in judged:
            groups.setdefault(rule.side(_SIDE_ON_PATH[path]), set()).add(path)
    return [(frozenset(paths), kinds) for kinds, paths in groups.items()]


def _compose(
    rule: SenderRule,
    ctx: SenderContext,
    path_stage: ReceivedPathNode | None = None,
) -> py_trees.behaviour.Behaviour | None:
    """The guard :func:`compose_sender_guard` returns, before it is marked."""

    # A ledger activity's nodes read the sender and the case from the entry
    # it carries; every other context's nodes are bound to the records it
    # names.  Either way the path the stage resolved picks the side.
    def node_for(kind: SenderEntitlementKind) -> py_trees.behaviour.Behaviour:
        if isinstance(ctx, LedgerActivityContext):
            return _ledger_kind_node(kind)
        return _kind_node(kind, ctx)

    sides = _sides(rule, path_stage)
    if len(sides) == 1:
        paths, kinds = sides[0]
        return _any_of(kinds, node_for, _receiver_of(paths))
    if path_stage is None:
        raise VultronWiringError(
            "compose_sender_guard: the rule names different kinds on"
            " different paths, and only the path stage may say which path"
            " the receiver is on; declare the tree's paths (HP-01-036)"
        )
    # Each arm passes off its own paths, and on them fails on its own
    # kinds' failure, so the refusal reason is the failing kind's
    # (BT-13-001).  The last arm passes on every other arm's paths, so it
    # judges the receiver whichever path the others do not claim.
    arms: list[py_trees.behaviour.Behaviour] = []
    for index, (paths, kinds) in enumerate(sides):
        name = _arm_name(paths)
        guard = _or_pass(_any_of(kinds, node_for, _receiver_of(paths)), name)
        if index < len(sides) - 1:
            skip: py_trees.behaviour.Behaviour = py_trees.decorators.Inverter(
                name=f"Not{name}", child=on_any_of_paths(path_stage, paths)
            )
        else:
            others = frozenset(ReceivedPath) - paths
            skip = on_any_of_paths(path_stage, others & path_stage.declared)
        arms.append(
            py_trees.composites.Selector(
                name=name, memory=False, children=[skip, guard]
            )
        )
    return py_trees.composites.Sequence(
        name=_RULE_GUARD, memory=False, children=arms
    )
