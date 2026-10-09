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

"""Architecture ratchet: an embargo trigger writes EM only as the CASE_MANAGER.

A trigger writes shared EM state only when the executing actor holds
``CVDRole.CASE_MANAGER`` (EP-09-008, ADR-0113, BT-17-001).  A participant
asks the manager instead and its replica moves on the manager's commit.  An
``_EmbargoLifecycleNode`` reached without the role gate writes canonical EM
state on a replica that does not own it (#3962).

The ratchet builds every embargo trigger BT factory and asserts each
``_EmbargoLifecycleNode`` in it has a ``create_case_manager_gated_tree``
ancestor, inside the gated branch.  A completeness check makes a new public
factory in ``trigger_tree`` fail here until it is listed.
"""

import inspect
from collections.abc import Callable, Iterator

import py_trees
import pytest

from vultron.core.behaviors.case.nodes.role_gates import (
    CheckIsCaseManagerNode,
)
from vultron.core.behaviors.embargo import trigger_tree
from vultron.core.behaviors.embargo.nodes.lifecycle import (
    _EmbargoLifecycleNode,
)
from vultron.core.behaviors.embargo.terminate_active_embargo_tree import (
    create_terminate_active_embargo_tree,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.states.embargo_register import TerminationReason

_CASE = "https://example.org/cases/ratchet-case"
_ACTOR = "https://example.org/actors/ratchet-actor"


def _builder(_to: list[str] | None) -> tuple[str, str]:
    return "", ""


def _embargo() -> EmbargoEvent:
    return EmbargoEvent(context=_CASE, end_time=days_from_now_utc(30))


_FACTORIES: dict[str, Callable[[], py_trees.behaviour.Behaviour]] = {
    "propose_embargo_trigger_bt": lambda: (
        trigger_tree.propose_embargo_trigger_bt(
            case_id=_CASE,
            actor_id=_ACTOR,
            embargo=_embargo(),
            result_out={},
            activity_builder=_builder,
        )
    ),
    "propose_embargo_revision_trigger_bt": lambda: (
        trigger_tree.propose_embargo_revision_trigger_bt(
            case_id=_CASE,
            actor_id=_ACTOR,
            embargo=_embargo(),
            result_out={},
            activity_builder=_builder,
        )
    ),
    "accept_embargo_trigger_bt": lambda: (
        trigger_tree.accept_embargo_trigger_bt(
            case_id=_CASE,
            embargo_id="urn:uuid:e",
            result_out={},
            activity_builder=_builder,
        )
    ),
    "activate_embargo_trigger_bt": lambda: (
        trigger_tree.activate_embargo_trigger_bt(
            case_id=_CASE,
            embargo_id="urn:uuid:e",
            result_out={},
            activity_builder=_builder,
        )
    ),
    "reject_embargo_proposal_trigger_bt": lambda: (
        trigger_tree.reject_embargo_proposal_trigger_bt(
            case_id=_CASE,
            embargo_id="urn:uuid:e",
            result_out={},
            activity_builder=_builder,
        )
    ),
    "reject_embargo_trigger_bt": lambda: (
        trigger_tree.reject_embargo_trigger_bt(
            case_id=_CASE,
            embargo_id="urn:uuid:e",
            result_out={},
            activity_builder=_builder,
        )
    ),
    "terminate_embargo_bt": lambda: trigger_tree.terminate_embargo_bt(
        case_id=_CASE,
        result_out={},
        reason=TerminationReason.EARLY,
        activity_builder=_builder,
    ),
    "terminate_embargo_bt (cascade)": lambda: (
        trigger_tree.terminate_embargo_bt(
            case_id=_CASE,
            result_out={},
            reason=TerminationReason.THREAT_SIGNAL,
        )
    ),
    "reject_proposed_embargo_bt": lambda: (
        trigger_tree.reject_proposed_embargo_bt(case_id=_CASE, result_out={})
    ),
    "create_terminate_active_embargo_tree": lambda: (
        create_terminate_active_embargo_tree(
            case_id=_CASE, result_out={}, activity_builder=_builder
        )
    ),
}

#: Public ``trigger_tree`` factories this ratchet deliberately does not gate,
#: with the reason and an issue.  Each is a known gap, not a licence; none is
#: left (#4131 gated the P/X/A abandonment cascade).
_EXEMPT: dict[str, str] = {}


def _walk(
    node: py_trees.behaviour.Behaviour,
) -> Iterator[py_trees.behaviour.Behaviour]:
    yield node
    for child in node.children:
        yield from _walk(child)


def _is_case_manager_gate(node: py_trees.behaviour.Behaviour) -> bool:
    """True for the Selector ``create_case_manager_gated_tree`` builds."""
    if not isinstance(node, py_trees.composites.Selector):
        return False
    if len(node.children) != 2:
        return False
    skip = node.children[0]
    if skip.name != "SkipIfNotCaseManager" or len(skip.children) != 1:
        return False
    inverter = skip.children[0]
    return isinstance(inverter, py_trees.decorators.Inverter) and isinstance(
        inverter.decorated, CheckIsCaseManagerNode
    )


def _gated_by_case_manager(node: py_trees.behaviour.Behaviour) -> bool:
    child, parent = node, node.parent
    while parent is not None:
        if _is_case_manager_gate(parent) and child is parent.children[1]:
            return True
        child, parent = parent, parent.parent
    return False


@pytest.mark.spec("EP-09-008")
@pytest.mark.spec("BT-17-001")
@pytest.mark.parametrize("factory_name", sorted(_FACTORIES))
def test_every_lifecycle_write_is_case_manager_gated(
    factory_name: str,
) -> None:
    tree = _FACTORIES[factory_name]()
    writes = [n for n in _walk(tree) if isinstance(n, _EmbargoLifecycleNode)]

    assert writes, f"{factory_name} builds no EM lifecycle write to check"
    ungated = [n.name for n in writes if not _gated_by_case_manager(n)]
    assert ungated == [], (
        f"{factory_name}: EM lifecycle write(s) {ungated} run without the"
        " CASE_MANAGER gate (EP-09-008)"
    )


def test_every_public_trigger_tree_factory_is_classified() -> None:
    public = {
        name
        for name, obj in inspect.getmembers(trigger_tree, inspect.isfunction)
        if obj.__module__ == trigger_tree.__name__ and not name.startswith("_")
    }
    covered = {name.split(" ", 1)[0] for name in _FACTORIES}

    assert public - covered - set(_EXEMPT) == set(), (
        "new trigger_tree factory: add it to _FACTORIES (or, with a reason"
        " and an issue, to _EXEMPT)"
    )
    assert set(_EXEMPT) <= public, "stale _EXEMPT entry"
