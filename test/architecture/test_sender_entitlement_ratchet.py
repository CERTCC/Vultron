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
from collections import Counter
from types import ModuleType
from typing import NamedTuple

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


class Site(NamedTuple):
    """A place a sender node is named."""

    module: str
    function: str
    node: str


class Listed(NamedTuple):
    """An allow-listed site: how many times it names the node, and why.

    The count is per site, so a second use added beside a listed one fails
    the ratchet instead of riding on the entry.
    """

    uses: int
    why: str


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
        and _corpus.callee_name(node.func) == "compose_sender_guard"
        and rel not in COMPOSE_CALLERS
    ):
        return "compose_sender_guard"
    return None


def _sender_references(tree: ast.AST, rel: str) -> Counter[Site]:
    """Every place in *tree* that names a sender node or composes a guard.

    A name counts wherever it is used, not only where it is called, so a node
    class bound to another name first, or reached through the module
    (``sender_entitlement.SenderIsX``), is still seen.  An import alias is
    followed; a name inside a type annotation composes nothing and is skipped.
    A call to ``compose_sender_guard`` counts outside :data:`COMPOSE_CALLERS`.
    """
    aliases = _import_aliases(tree)
    skipped = _annotation_nodes(tree)
    found: Counter[Site] = Counter()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scope = (*scope, node.name)
        if id(node) not in skipped and (
            named := _named_sender_node(node, aliases, rel)
        ):
            found[Site(rel, ".".join(scope) or "<module>", named)] += 1
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(tree, ())
    return found


def _live_sites() -> Counter[Site]:
    """Every sender-node reference in ``vultron/`` outside its two homes."""
    found: Counter[Site] = Counter()
    for path, tree in _corpus.files_mentioning(
        "sender_entitlement",
        "compose_sender_guard",
        *SENDER_NODES,
        under=_corpus.REPO_ROOT / "vultron",
    ):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        if rel not in {_HOME, _COMPOSER}:
            found += _sender_references(tree, rel)
    return found


#: Sender guards a received tree still places itself, each naming the open
#: issue that moves it into the declared rule the factory composes.  The list
#: only shrinks: a new entry, or a stale one, fails the test.
GUARDS_NOT_YET_MIGRATED: dict[Site, Listed] = {
    Site(
        "vultron/core/behaviors/report/prioritize_tree.py",
        "create_engage_case_tree",
        "SenderIsParticipantNode",
    ): Listed(
        1,
        "#4696: follows the snapshot steps, which store the sender's own"
        " participant record when the Engage carries it inline",
    ),
    Site(
        "vultron/core/behaviors/report/received_report_trees.py",
        "_report_verdict_stages",
        "SenderIsParticipantNode",
    ): Listed(
        1,
        "#4696: follows RequireCaseForReport, which resolves the case of a"
        " Close/Invalidate(Report) at run time",
    ),
    Site(
        "vultron/core/behaviors/sync/announce_tree.py",
        "create_announce_log_entry_tree",
        "SenderIsCaseManagerNode",
    ): Listed(
        2,
        "#4696: the case comes from the announced entry at run time; each"
        " role arm checks after its own CASE_MANAGER gate",
    ),
    Site(
        "vultron/core/behaviors/sync/reject_tree.py",
        "create_reject_log_entry_tree",
        "SenderIsActiveLedgerParticipantNode",
    ): Listed(
        1,
        "#4615: the ledger Reject's own standing (SYNC-03-005), read from"
        " the case the ledger activity names",
    ),
}

#: Standing reads that choose an effect after the declared rule has admitted
#: the sender, or that read an actor other than the sender.  They admit no
#: one, so they are not sender guards and need no migration; each says why.
STANDING_READS: dict[Site, Listed] = {
    Site(
        "vultron/core/behaviors/case/suggest_actor_tree.py",
        "create_recommend_actor_to_case_received_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(
        4,
        "in manager_effects: picks the owner's direct Invite or re-invite"
        " (and its CM-11-015 closed-participant check) or the Offer to the"
        " owner (CM-16)",
    ),
    Site(
        "vultron/core/behaviors/case/receive_close_case_tree.py",
        "create_close_case_received_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(2, "picks the owner's or a participant's Leave arm (CM-23-003)"),
    Site(
        "vultron/core/behaviors/case/receive_close_case_tree.py",
        "create_close_case_received_tree._decline_decision_guards",
        "SenderIsCaseOwnerNode",
    ): Listed(
        1, "decides whether a live embargo declines the close (CM-23-011)"
    ),
    Site(
        "vultron/core/behaviors/status/add_participant_status_tree.py",
        "add_participant_status_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(
        1,
        "in manager_effects: the owner's status bypasses the adoption"
        " call-out (RSH-01-002)",
    ),
    Site(
        "vultron/core/behaviors/embargo/response_decision_tree.py",
        "create_embargo_response_decision_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(1, "reads the local deciding actor, not a sender (EMB-15-002)"),
    Site(
        "vultron/core/behaviors/embargo/announce_teardown_tree.py",
        "invite_to_embargo_on_case_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(
        2, "reads the local invitee answering on its replica (EP-09-005)"
    ),
    Site(
        "vultron/core/behaviors/report/trigger_report_trees.py",
        "create_close_case_trigger_tree",
        "SenderIsCaseOwnerNode",
    ): Listed(1, "a trigger tree: reads the triggering actor's own standing"),
}


def _listed() -> dict[Site, int]:
    return {
        site: entry.uses
        for site, entry in (GUARDS_NOT_YET_MIGRATED | STANDING_READS).items()
    }


def _site_lines(sites: dict[Site, int]) -> str:
    return "\n".join(
        f"  - {s.module}::{s.function} ({s.node} x{uses})"
        for s, uses in sorted(sites.items())
    )


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("HP-01-008")
def test_sender_nodes_are_composed_only_by_the_factory() -> None:
    """A sender node outside the factory's composer is allow-listed (AC-5)."""
    found = dict(_live_sites())
    listed = _listed()
    new = {s: n for s, n in found.items() if listed.get(s) != n}
    stale = {s: n for s, n in listed.items() if s not in found}
    assert not new, (
        "These modules name a sender-entitlement node, or compose a sender"
        " guard, outside the receive-tree factory or more often than the"
        " allow-list says (HP-01-007, HP-01-008).  Declare the standing in"
        " the use case's SenderRule and pass it with a SenderCheckContext;"
        " a pre-flight asks rule_refusal():\n" + _site_lines(new)
    )
    assert not stale, (
        "These allow-list entries no longer name a sender node; remove them"
        " so the list only shrinks:\n" + _site_lines(stale)
    )


def test_every_unmigrated_guard_names_its_tracking_issue() -> None:
    """The remaining migration is a visible list of issues (AC-5).

    The format is checked here; that each issue is still open is checked
    when an entry is added or reviewed, since the suite runs offline.
    """
    malformed = {
        site: entry.why
        for site, entry in GUARDS_NOT_YET_MIGRATED.items()
        if re.match(r"#\d+: ", entry.why) is None
    }
    assert not malformed, f"Entries without a tracking issue: {malformed}"
    assert set(GUARDS_NOT_YET_MIGRATED).isdisjoint(STANDING_READS)


#: Sender checks defined outside the sender-entitlement module, each naming
#: the open issue that retires it (HP-01-007: the module has no twin).
SENDER_CHECKS_DEFINED_ELSEWHERE: dict[tuple[str, str], str] = {
    (
        "vultron/core/behaviors/case/nodes/replica_bootstrap.py",
        "CheckSenderIsSnapshotManagerNode",
    ): "#4472",
}


@pytest.mark.spec("HP-01-007")
def test_no_sender_check_is_defined_outside_its_module() -> None:
    """A node class named for the sender lives in the one module.

    The subclass check above misses a sender check on another base; its
    name gives it away (``...Sender...Node``).
    """
    found = {
        (path.relative_to(_corpus.REPO_ROOT).as_posix(), node.name)
        for path, tree in _corpus.files_mentioning(
            "Sender", under=_corpus.REPO_ROOT / "vultron"
        )
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and "Sender" in node.name
        and node.name.endswith("Node")
    }
    found = {site for site in found if site[0] not in {_HOME, _COMPOSER}}
    assert found == set(SENDER_CHECKS_DEFINED_ELSEWHERE), (
        "Sender checks outside vultron/core/behaviors/sender_entitlement.py"
        f" differ from the allow-list: new {sorted(found - set(SENDER_CHECKS_DEFINED_ELSEWHERE))},"
        f" stale {sorted(set(SENDER_CHECKS_DEFINED_ELSEWHERE) - found)}"
    )


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
    assert {site.module for site in sites} == {rel}
    assert {site.function for site in sites} <= {"build", "execute"}


def test_the_scan_counts_each_use_at_a_site() -> None:
    """A second guard beside an allow-listed use does not ride on its entry."""
    source = _corpus.parse_inline(
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsCaseOwnerNode\n"
        "def build():\n"
        "    return [SenderIsCaseOwnerNode(), SenderIsCaseOwnerNode()]\n"
    )
    site = Site("vultron/x.py", "build", "SenderIsCaseOwnerNode")
    assert _sender_references(source, "vultron/x.py") == {site: 2}


def test_the_scan_skips_annotations_and_the_sanctioned_callers() -> None:
    """A type annotation composes nothing; the factory may compose."""
    annotated = _corpus.parse_inline(
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsInviteeNode\n"
        "def find(tree) -> SenderIsInviteeNode | None:\n"
        "    return None\n"
    )
    assert not _sender_references(annotated, "vultron/x.py")
    composed = _corpus.parse_inline(
        "def stage(rule, ctx):\n    return compose_sender_guard(rule, ctx)\n"
    )
    for caller in COMPOSE_CALLERS:
        assert not _sender_references(composed, caller)
