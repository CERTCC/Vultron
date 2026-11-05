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

from vultron.core.behaviors.case.nodes.conditions import CheckIsCaseManagerNode
from vultron.core.behaviors.case.nodes.received_path import (
    CheckReceivedPathNode,
    ReceivedPathNode,
)
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.sender_check_context import (
    LedgerActivityContext,
    SenderContext,
)
from vultron.core.behaviors.sender_entitlement import (
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


def _ledger_guard(rule: SenderRule) -> py_trees.behaviour.Behaviour | None:
    """The guard *rule* requires for a ledger activity's case."""
    if rule.at_case_manager != rule.at_participant:
        raise VultronWiringError(
            "compose_sender_guard: a ledger activity's case is read at run"
            " time, so its rule must state the same kinds at the CASE_MANAGER"
            " and at a participant (HP-01-024)"
        )
    return _any_of(rule.at_case_manager, _ledger_kind_node, "a case actor")


def compose_sender_guard(
    rule: SenderRule,
    ctx: SenderContext,
    path_stage: ReceivedPathNode | None = None,
) -> py_trees.behaviour.Behaviour | None:
    """Compose the guard *rule* requires for the activity *ctx* describes.

    Args:
        rule: The use case's declared sender rule.
        ctx: The sender and the records its kinds are checked against, or a
            :class:`LedgerActivityContext` for an activity whose case the
            ledger entry it carries names.
        path_stage: The tree's path door stage, when it declared its paths.
            The rule's ``at_case_manager`` and ``at_participant`` arms are
            then selected from the path that stage resolved, so the role
            question is asked once, ahead of this guard (HP-01-036).
            Without it the arms read the role themselves, as every tree did
            before the path stage.  No received tree reaches that fallback
            any more — every call site that passes a sender rule declares
            its paths — so it survives for the tests that compose a guard in
            isolation, and goes with them in #5876.  The ``outside_case``
            side is still
            selected by the context naming no case, not by the no-case path
            HP-01-036 would map it onto: that side is chosen at
            composition time, and a tree whose context names a case the
            receiver does not hold has always been judged by the
            ``at_participant`` side.  Moving it is a behaviour change beyond
            what HP-01-036 asks for, so it is #5744's, not the migration
            waves'.

    Returns:
        The guard, or ``None`` when the receiver's side admits any actor.

    Raises:
        VultronWiringError: The context lacks a record a kind needs: an
            ``INVITEE`` kind without ``invite_id``, a ``NAMED_ACTOR`` kind
            without ``request``, an ``AUTHOR`` kind without
            ``authored_object``, or a case-scoped check without
            ``case_id``; or a ledger activity's rule declares a kind that
            cannot read the case at run time, or differs by side.
    """
    guard = _compose(rule, ctx, path_stage)
    if guard is not None:
        setattr(guard, _COMPOSED_GUARD_MARK, True)
    return guard


def _at_case_manager(
    case_id: str, path_stage: ReceivedPathNode | None
) -> py_trees.behaviour.Behaviour:
    """The condition "this receiver is the case's CASE_MANAGER", for an arm.

    The path stage's answer when the tree declared its paths (ADR-0153), and
    the role read of
    :class:`~vultron.core.behaviors.case.nodes.conditions.CheckIsCaseManagerNode`
    otherwise.  One helper, so both arms of the rule guard agree on which it
    is.

    The second branch is the last entry in
    ``test/architecture/test_received_path_role_question.py``'s
    ``KNOWN_ROLE_QUESTION_SITES``.  No received tree reaches it; it is held
    open by the guard-composition tests, and #5876 retires both together.
    """
    if path_stage is not None:
        return CheckReceivedPathNode.on_manager_path(path_stage)
    return with_case_id(
        CheckIsCaseManagerNode(case_may_be_absent=True), case_id
    )


def _compose(
    rule: SenderRule,
    ctx: SenderContext,
    path_stage: ReceivedPathNode | None = None,
) -> py_trees.behaviour.Behaviour | None:
    """The guard :func:`compose_sender_guard` returns, before it is marked."""
    if isinstance(ctx, LedgerActivityContext):
        return _ledger_guard(rule)

    def node_for(kind: SenderEntitlementKind) -> py_trees.behaviour.Behaviour:
        return _kind_node(kind, ctx)

    if ctx.case_id is None:
        return _any_of(
            rule.outside_case,
            node_for,
            "a receiver that holds no case for it (the activity names no"
            " case this store holds)",
        )
    if rule.at_case_manager == rule.at_participant:
        return _any_of(rule.at_case_manager, node_for, "a case actor")
    manager = _or_pass(
        _any_of(rule.at_case_manager, node_for, "the CASE_MANAGER"),
        "AtCaseManager",
    )
    participant = _or_pass(
        _any_of(
            rule.at_participant,
            node_for,
            "a participant other than the CASE_MANAGER",
        ),
        "AtParticipant",
    )
    return py_trees.composites.Sequence(
        name=_RULE_GUARD,
        memory=False,
        children=[
            py_trees.composites.Selector(
                name="AtCaseManager",
                memory=False,
                children=[
                    py_trees.decorators.Inverter(
                        name="NotAtCaseManager",
                        child=_at_case_manager(ctx.case_id, path_stage),
                    ),
                    manager,
                ],
            ),
            py_trees.composites.Selector(
                name="AtParticipant",
                memory=False,
                children=[
                    _at_case_manager(ctx.case_id, path_stage),
                    participant,
                ],
            ),
        ],
    )
