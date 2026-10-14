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

"""Architecture ratchet: sender entitlement declarations (ADR-0115).

Enforces:
1. Every received use case in SEMANTIC_REGISTRY declares ``sender_entitlement``.
2. No ``SenderEntitlementConditionNode`` subclass is defined outside
   ``vultron.core.behaviors.sender_entitlement``.
3. Old node names no longer live in their former modules.
4. A received tree builds its own ``sender_guard`` only when it is on the
   allow-list of trees not yet composing the guard from the declared rule
   (HP-01-008, #4437).
"""

import ast
import importlib
import inspect
import sys
from types import ModuleType

import pytest

from test.architecture import _corpus
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementConditionNode,
    SenderEntitlementKind,
    SenderExemption,
    SenderRule,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _received_entries():
    """Yield (semantics, use_case_class) for every non-UNKNOWN registry entry."""
    unknown_names = {
        MessageSemantics.UNKNOWN.name,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.name,
    }
    for entry in SEMANTIC_REGISTRY:
        if entry.semantics.name not in unknown_names:
            yield entry.semantics, entry.use_case_class


# ---------------------------------------------------------------------------
# AC-1: every received use case declares sender_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "semantics,use_case_class",
    list(_received_entries()),
    ids=[
        e.semantics.name
        for e in SEMANTIC_REGISTRY
        if e.semantics.name
        not in {
            MessageSemantics.UNKNOWN.name,
            MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.name,
        }
    ],
)
def test_use_case_has_sender_entitlement_declared(semantics, use_case_class):
    """Every received use case must declare ``sender_entitlement``."""
    assert hasattr(use_case_class, "sender_entitlement"), (
        f"{use_case_class.__name__} (semantics={semantics.name}) "
        f"is missing the ``sender_entitlement`` ClassVar. "
        f"Add one to {inspect.getfile(use_case_class)} — "
        f"use a SenderRule (HP-01-008) or exempt('#NNNN', 'reason')."
    )
    declaration = use_case_class.sender_entitlement
    assert isinstance(declaration, (SenderRule, SenderExemption)), (
        f"{use_case_class.__name__}.sender_entitlement must be "
        f"SenderRule or SenderExemption, got {type(declaration)!r}"
    )


# ---------------------------------------------------------------------------
# AC-2: no SenderEntitlementConditionNode subclass defined outside the module
# ---------------------------------------------------------------------------


def _all_loaded_modules() -> list[ModuleType]:
    """Return all currently loaded vultron modules."""
    return [
        mod
        for name, mod in sys.modules.items()
        if name.startswith("vultron") and isinstance(mod, ModuleType)
    ]


def _import_vultron_behaviors() -> None:
    """Pre-import the BT behaviors package to ensure subclasses are loaded."""
    prefixes = [
        "vultron.core.behaviors",
        "vultron.core.use_cases",
    ]
    for prefix in prefixes:
        try:
            importlib.import_module(prefix)
        except ImportError:
            pass


def test_no_sender_condition_node_outside_sender_entitlement_module():
    """No SenderEntitlementConditionNode subclass may live outside sender_entitlement.py."""
    _import_vultron_behaviors()

    MODULE = "vultron.core.behaviors.sender_entitlement"
    violations = []
    for mod in _all_loaded_modules():
        if mod.__name__ == MODULE:
            continue  # the canonical home — all good
        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, SenderEntitlementConditionNode)
                and obj is not SenderEntitlementConditionNode
                and obj.__module__ != MODULE
            ):
                violations.append(f"{obj.__module__}.{obj.__name__}")
    assert not violations, (
        "SenderEntitlementConditionNode subclasses found outside "
        f"'{MODULE}':\n" + "\n".join(f"  - {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# AC-3: old node names no longer live at their former module paths
# ---------------------------------------------------------------------------


OLD_NAMES = [
    (
        "vultron.core.behaviors.status.nodes.conditions",
        "VerifySenderIsParticipantNode",
    ),
    (
        "vultron.core.behaviors.case.nodes.vfd_role_guards",
        "CheckIsCaseOwnerNode",
    ),
    (
        "vultron.core.behaviors.sync.nodes.conditions",
        "VerifySenderIsCaseActorNode",
    ),
    (
        "vultron.core.behaviors.sync.nodes.conditions",
        "VerifySenderIsOwnIdNode",
    ),
]


@pytest.mark.parametrize(
    "module_path,class_name",
    OLD_NAMES,
    ids=[f"{m}.{c}" for m, c in OLD_NAMES],
)
def test_old_node_name_removed_from_former_module(module_path, class_name):
    """Old sender-check node names must no longer exist in their former module."""
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        pytest.skip(f"Module {module_path!r} not importable")
    assert not hasattr(mod, class_name), (
        f"{module_path}.{class_name} still exists — "
        f"it has been consolidated into "
        f"vultron.core.behaviors.sender_entitlement (ADR-0115, AC-2). "
        f"Remove the definition and update any importers."
    )


# ---------------------------------------------------------------------------
# HP-01-011: ANY_ACTOR is reserved for the two new-report use cases
# ---------------------------------------------------------------------------

#: The received use cases HP-01-010 entitles any actor to send to.
ANY_ACTOR_USE_CASES = frozenset(
    {"CreateReportReceivedUseCase", "SubmitReportReceivedUseCase"}
)


@pytest.mark.spec("HP-01-011")
def test_any_actor_is_declared_only_by_new_report_use_cases():
    """``ANY_ACTOR`` declares no check, so it must not spread as an exemption."""
    declaring = {
        use_case_class.__name__
        for _semantics, use_case_class in _received_entries()
        if isinstance(
            declared := getattr(use_case_class, "sender_entitlement", None),
            SenderRule,
        )
        and SenderEntitlementKind.ANY_ACTOR in declared.kinds
    }
    assert declaring == ANY_ACTOR_USE_CASES, (
        "Only the use cases receiving a new report may declare ANY_ACTOR "
        f"(HP-01-011); found {sorted(declaring)}"
    )


# ---------------------------------------------------------------------------
# HP-01-008: trees still building their own sender guard (temporary)
# ---------------------------------------------------------------------------

_PIECE_2 = "#4437 (piece 2: one addressee kind, AC-3)"
_PIECE_3 = "#4437 (piece 3: widened rules, AC-4)"
_PIECE_4 = "#4437 (piece 4: ratchet, AC-5)"

#: Received-tree builders that still pass their own ``sender_guard`` to
#: ``create_receive_activity_tree`` instead of the declared ``sender_rule``,
#: keyed by (module path, function), each naming the work that migrates it.
#: The list only shrinks: a new entry, or a stale one, fails the test.
SENDER_GUARD_ALLOW_LIST: dict[tuple[str, str], str] = {
    (
        "vultron/core/behaviors/case/accept_case_proposal_received_tree.py",
        "create_accept_case_proposal_received_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/case/reject_case_proposal_received_tree.py",
        "create_reject_case_proposal_received_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/case/ownership_transfer_tree.py",
        "create_accept_ownership_transfer_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/case/ownership_transfer_tree.py",
        "create_reject_ownership_transfer_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/case/ownership_transfer_tree.py",
        "create_undo_ownership_transfer_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/report/received_report_trees.py",
        "create_ack_report_received_tree",
    ): _PIECE_2,
    (
        "vultron/core/behaviors/note/remove_note_received_tree.py",
        "create_remove_note_from_case_received_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/embargo/announce_teardown_tree.py",
        "invite_to_embargo_on_case_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/embargo/announce_teardown_tree.py",
        "remove_embargo_from_case_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/case/case_participant_received_tree.py",
        "create_add_case_participant_received_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/case/case_participant_received_tree.py",
        "create_remove_case_participant_received_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/case/suggest_actor_tree.py",
        "create_recommend_actor_to_case_received_tree",
    ): _PIECE_3,
    (
        "vultron/core/behaviors/status/add_participant_status_tree.py",
        "add_participant_status_tree",
    ): _PIECE_3,
    # Two-sided (CASE_OWNER at the CASE_MANAGER, CASE_MANAGER at a replica).
    (
        "vultron/core/behaviors/case/add_report_received_tree.py",
        "create_add_report_to_case_received_tree",
    ): _PIECE_4,
    # The Invite may name no case, which needs an ``outside_case`` side.
    (
        "vultron/core/behaviors/case/invite_actor_to_case_received_tree.py",
        "create_reject_invite_actor_to_case_received_tree",
    ): _PIECE_4,
}


def _sender_guard_builders() -> set[tuple[str, str]]:
    """Every (module path, function) whose body passes ``sender_guard=``."""
    found: set[tuple[str, str]] = set()
    for path, tree in _corpus.files_mentioning(
        "sender_guard", under=_corpus.REPO_ROOT / "vultron"
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(
                isinstance(call, ast.Call)
                and any(kw.arg == "sender_guard" for kw in call.keywords)
                for call in ast.walk(func)
            ):
                found.add((rel, func.name))
    return found


@pytest.mark.spec("HP-01-008")
def test_only_allow_listed_trees_build_their_own_sender_guard():
    """A tree composes its sender guard from the rule unless allow-listed."""
    found = _sender_guard_builders()
    new = sorted(found - set(SENDER_GUARD_ALLOW_LIST))
    stale = sorted(set(SENDER_GUARD_ALLOW_LIST) - found)
    assert not new, (
        "These received trees pass their own sender_guard; pass the use"
        " case's sender_rule and a SenderCheckContext instead (HP-01-008):\n"
        + "\n".join(f"  - {path}::{func}" for path, func in new)
    )
    assert not stale, (
        "These allow-list entries no longer pass sender_guard; remove them"
        " so the list only shrinks:\n"
        + "\n".join(f"  - {path}::{func}" for path, func in stale)
    )
