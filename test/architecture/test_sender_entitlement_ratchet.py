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
4. No sender-entitlement condition node is composed outside the receive-tree
   factory's composer, except where an allow-list names it (HP-01-007,
   HP-01-008, #4437): a guard not yet migrated names the open issue that
   migrates it, and a standing read that decides an effect rather than
   admission names why it is not a sender guard.
"""

import ast
import importlib
import inspect
import re
import sys
from types import ModuleType

import py_trees
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
    # The CASE_MANAGER's check on its own echoed announcement is the
    # CASE_MANAGER kind's node, not a named-actor node (HP-01-009, #4437).
    (
        "vultron.core.behaviors.sender_entitlement",
        "SenderIsNamedActorNode",
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
# HP-01-007 / HP-01-008: sender nodes are composed only by the factory
# ---------------------------------------------------------------------------

_HOME = "vultron/core/behaviors/sender_entitlement.py"
_COMPOSER = "vultron/core/behaviors/sender_guard.py"

#: The only modules that may call ``compose_sender_guard``: the receive-tree
#: factory and the pre-flight that runs the same guard ahead of a handler's
#: first write (``rule_refusal``).
COMPOSE_CALLERS = frozenset(
    {
        "vultron/core/behaviors/case/receive_activity_tree.py",
        "vultron/core/use_cases/received/_sender_preflight.py",
    }
)

#: A place a sender node is named: (module path, enclosing function, node).
Site = tuple[str, str, str]


def _sender_node_names() -> frozenset[str]:
    """Every behaviour class defined in the sender-entitlement module."""
    home = importlib.import_module("vultron.core.behaviors.sender_entitlement")
    return frozenset(
        name
        for name, obj in inspect.getmembers(home, inspect.isclass)
        if obj.__module__ == home.__name__
        and issubclass(obj, py_trees.behaviour.Behaviour)
    )


SENDER_NODES = _sender_node_names()


def _annotation_nodes(tree: ast.AST) -> set[int]:
    """Ids of every AST node inside a type annotation in *tree*."""
    roots: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                roots.append(node.returns)
            args = node.args
            roots.extend(
                a.annotation
                for a in [
                    *args.posonlyargs,
                    *args.args,
                    *args.kwonlyargs,
                    *([args.vararg] if args.vararg else []),
                    *([args.kwarg] if args.kwarg else []),
                ]
                if a.annotation is not None
            )
        elif isinstance(node, ast.AnnAssign):
            roots.append(node.annotation)
    return {id(sub) for root in roots for sub in ast.walk(root)}


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    """Each local name in *tree* bound to a sender node, to the node's name."""
    aliases = {name: name for name in SENDER_NODES}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in SENDER_NODES and alias.asname:
                    aliases[alias.asname] = alias.name
    return aliases


def _named_sender_node(
    node: ast.AST, aliases: dict[str, str], rel: str
) -> str | None:
    """The sender node *node* names, or ``compose_sender_guard`` it calls."""
    if isinstance(node, ast.Name):
        return aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        return node.attr if node.attr in SENDER_NODES else None
    if (
        isinstance(node, ast.Call)
        and _called_name(node) == "compose_sender_guard"
        and rel not in COMPOSE_CALLERS
    ):
        return "compose_sender_guard"
    return None


def _sender_references(tree: ast.AST, rel: str) -> set[Site]:
    """Every place in *tree* that names a sender node or composes a guard.

    A name counts wherever it is used, not only where it is called, so a node
    class bound to another name first, or reached through the module
    (``sender_entitlement.SenderIsX``), is still seen.  An import alias is
    followed; a name inside a type annotation composes nothing and is skipped.
    A call to ``compose_sender_guard`` counts outside :data:`COMPOSE_CALLERS`.
    """
    aliases = _import_aliases(tree)
    skipped = _annotation_nodes(tree)
    found: set[Site] = set()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
        if id(node) not in skipped and (
            named := _named_sender_node(node, aliases, rel)
        ):
            found.add((rel, ".".join(scope) or "<module>", named))
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, ())
    return found


def _called_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else None


def _live_sites() -> set[Site]:
    """Every sender-node reference in ``vultron/`` outside its two homes."""
    found: set[Site] = set()
    for path, tree in _corpus.files_mentioning(
        "sender_entitlement",
        "compose_sender_guard",
        *SENDER_NODES,
        under=_corpus.REPO_ROOT / "vultron",
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        if rel not in {_HOME, _COMPOSER}:
            found |= _sender_references(tree, rel)
    return found


#: Sender guards a received tree still places itself, each naming the open
#: issue that moves it into the declared rule the factory composes.  The list
#: only shrinks: a new entry, or a stale one, fails the test.
GUARDS_NOT_YET_MIGRATED: dict[Site, str] = {
    # The guard must follow the Engage's snapshot steps, which store the
    # sender's own participant record when the Engage carries it inline.
    (
        "vultron/core/behaviors/report/prioritize_tree.py",
        "create_engage_case_tree",
        "SenderIsParticipantNode",
    ): "#4696",
    # The case is resolved from the report at run time (RequireCaseForReport),
    # so the guard follows that step in the Close/Invalidate(Report) trees.
    (
        "vultron/core/behaviors/report/received_report_trees.py",
        "_report_verdict_stages",
        "SenderIsParticipantNode",
    ): "#4696",
    # The case comes from the announced entry at run time; each role arm
    # checks CASE_MANAGER standing after its own CASE_MANAGER gate.
    (
        "vultron/core/behaviors/sync/announce_tree.py",
        "create_announce_log_entry_tree",
        "SenderIsCaseManagerNode",
    ): "#4696",
    # The ledger Reject's own standing (SYNC-03-005), read from the case the
    # ledger activity names; #4615 gives it its own kind.
    (
        "vultron/core/behaviors/sync/reject_tree.py",
        "create_reject_log_entry_tree",
        "SenderIsActiveLedgerParticipantNode",
    ): "#4615",
}

#: Standing reads that choose an effect after the declared rule has admitted
#: the sender, or that read an actor other than the sender.  They admit no
#: one, so they are not sender guards and need no migration; each names why.
STANDING_READS: dict[Site, str] = {
    (
        "vultron/core/behaviors/case/suggest_actor_tree.py",
        "create_recommend_actor_to_case_received_tree",
        "SenderIsCaseOwnerNode",
    ): "picks the owner-direct Invite or the Offer to the owner (CM-16)",
    (
        "vultron/core/behaviors/case/receive_close_case_tree.py",
        "create_close_case_received_tree",
        "SenderIsCaseOwnerNode",
    ): "picks the owner's or a participant's Leave arm (CM-23-003)",
    (
        "vultron/core/behaviors/case/receive_close_case_tree.py",
        "create_close_case_received_tree._decline_decision_guards",
        "SenderIsCaseOwnerNode",
    ): "decides whether the close is declined for a live embargo (CM-23-011)",
    (
        "vultron/core/behaviors/status/add_participant_status_tree.py",
        "add_participant_status_tree",
        "SenderIsCaseOwnerNode",
    ): "the owner's status bypasses the adoption call-out (RSH-01-002)",
    (
        "vultron/core/behaviors/embargo/response_decision_tree.py",
        "create_embargo_response_decision_tree",
        "SenderIsCaseOwnerNode",
    ): "reads the local deciding actor, not a sender (EMB-15-002)",
    (
        "vultron/core/behaviors/embargo/announce_teardown_tree.py",
        "invite_to_embargo_on_case_tree",
        "SenderIsCaseOwnerNode",
    ): "reads the local invitee answering on its replica (EP-09-005)",
    (
        "vultron/core/behaviors/report/trigger_report_trees.py",
        "create_close_case_trigger_tree",
        "SenderIsCaseOwnerNode",
    ): "a trigger tree: reads the triggering actor's own standing",
}


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("HP-01-008")
def test_sender_nodes_are_composed_only_by_the_factory() -> None:
    """A sender node outside the factory's composer is allow-listed (AC-5)."""
    found = _live_sites()
    listed = set(GUARDS_NOT_YET_MIGRATED) | set(STANDING_READS)
    new = sorted(found - listed)
    stale = sorted(listed - found)
    assert not new, (
        "These modules name a sender-entitlement node or compose a sender"
        " guard outside the receive-tree factory (HP-01-007, HP-01-008)."
        " Declare the standing in the use case's SenderRule and pass it with"
        " a SenderCheckContext; a pre-flight asks rule_refusal():\n"
        + "\n".join(f"  - {p}::{f} ({n})" for p, f, n in new)
    )
    assert not stale, (
        "These allow-list entries no longer name a sender node; remove them"
        " so the list only shrinks:\n"
        + "\n".join(f"  - {p}::{f} ({n})" for p, f, n in stale)
    )


def test_every_unmigrated_guard_names_its_tracking_issue() -> None:
    """The remaining migration is a visible list of issues (AC-5)."""
    malformed = {
        site: issue
        for site, issue in GUARDS_NOT_YET_MIGRATED.items()
        if re.fullmatch(r"#\d+", issue) is None
    }
    assert not malformed, f"Entries without a tracking issue: {malformed}"
    assert set(GUARDS_NOT_YET_MIGRATED).isdisjoint(STANDING_READS)


#: Source shapes the scan must see, each composing a sender guard outside
#: the factory.
_VIOLATIONS = {
    "direct-call": (
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsParticipantNode\n"
        "def build():\n"
        "    return SenderIsParticipantNode(sender_actor_id='a', case_id='c')\n"
    ),
    "import-alias": (
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsCaseOwnerNode as Owner\n"
        "def build():\n"
        "    return Owner(sender_actor_id='a', case_id='c')\n"
    ),
    "module-attribute": (
        "from vultron.core.behaviors import sender_entitlement\n"
        "def build():\n"
        "    return sender_entitlement.SenderIsInviteeNode('i', 'a')\n"
    ),
    "bound-before-call": (
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsCaseManagerNode\n"
        "def build():\n"
        "    node = SenderIsCaseManagerNode\n"
        "    return node()\n"
    ),
    "handler-compose": (
        "from vultron.core.behaviors.sender_guard import"
        " compose_sender_guard\n"
        "def execute(rule, ctx):\n"
        "    return compose_sender_guard(rule, ctx)\n"
    ),
}


@pytest.mark.parametrize("source", _VIOLATIONS.values(), ids=_VIOLATIONS)
def test_the_scan_sees_a_sender_guard_composed_outside_the_factory(
    source: str,
) -> None:
    """Each shape is reported, so the ratchet fails on it (AC-5)."""
    rel = "vultron/core/use_cases/received/example.py"
    sites = _sender_references(_corpus.parse_inline(source), rel)
    assert sites
    assert all(path == rel for path, _func, _node in sites)
    assert {func for _path, func, _node in sites} <= {"build", "execute"}


def test_the_scan_skips_annotations_and_the_sanctioned_callers() -> None:
    """A type annotation composes nothing; the factory may compose."""
    annotated = _corpus.parse_inline(
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsInviteeNode\n"
        "def find(tree) -> SenderIsInviteeNode | None:\n"
        "    return None\n"
    )
    assert _sender_references(annotated, "vultron/x.py") == set()
    composed = _corpus.parse_inline(
        "def stage(rule, ctx):\n    return compose_sender_guard(rule, ctx)\n"
    )
    for caller in COMPOSE_CALLERS:
        assert _sender_references(composed, caller) == set()
