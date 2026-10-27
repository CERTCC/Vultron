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
5. A ``SenderRule`` is built only as a use case's ``sender_entitlement``
   declaration, so the guard is composed from the declaration alone
   (HP-01-008).
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
    """Yield (semantics, use_case_class) for every handled non-UNKNOWN entry.

    An entry with no use case is recognized but not handled (SE-05-002), so
    it has no use case to declare a sender entitlement.
    """
    unknown_names = {
        MessageSemantics.UNKNOWN.name,
        MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT.name,
    }
    for entry in SEMANTIC_REGISTRY:
        if (
            entry.semantics.name not in unknown_names
            and entry.use_case_class is not None
        ):
            yield entry.semantics, entry.use_case_class


# ---------------------------------------------------------------------------
# AC-1: every received use case declares sender_entitlement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "semantics,use_case_class",
    list(_received_entries()),
    ids=[semantics.name for semantics, _ in _received_entries()],
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

#: The only module that may call the composer's public builders
#: (:data:`_COMPOSE`): the receive-tree factory.  The pre-flights that ran
#: the same guards ahead of a handler's tree as a tree of their own were
#: retired once each handler composed its door guards into its one tree:
#: ``rule_refusal`` by #4642, and ``closed_sender_preflight`` by #4773, whose
#: callers pass ``closed_sender`` to the factory instead (CLP-10-005,
#: ADR-0135).
COMPOSE_CALLERS = frozenset(
    {
        "vultron/core/behaviors/case/receive_activity_tree.py",
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


#: The composer's public builders, which only :data:`COMPOSE_CALLERS` call.
_COMPOSE = frozenset(
    {
        "compose_sender_guard",
        "closed_sender_guard",
        "closed_sender_door",
        "case_owner_guard",
    }
)


def _composer_builders() -> frozenset[str]:
    """The composer's private builders, which no other module may call."""
    tree = _corpus.tree_of(_corpus.REPO_ROOT / _COMPOSER)
    return frozenset(
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("_")
    )


COMPOSER_BUILDERS = _composer_builders()


def _from_composer(module: str | None) -> bool:
    return (module or "").rpartition(".")[2] == "sender_guard"


def _tracked(name: str, from_composer: bool) -> bool:
    """*name* is a sender node or a public composer builder, or a private
    builder reached through the composer module."""
    return (
        name in SENDER_NODES
        or name in _COMPOSE
        or (name in COMPOSER_BUILDERS and from_composer)
    )


def _import_aliases(tree: ast.AST) -> tuple[dict[str, str], set[str]]:
    """The names *tree* binds to a sender node or a composer function, and
    the names it binds to the composer module itself.

    A sender node and ``compose_sender_guard`` are tracked by name wherever
    they come from; a private builder only when imported from the composer,
    so a module's own helper of the same name is not mistaken for it.
    """
    aliases = {name: name for name in SENDER_NODES | _COMPOSE}
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                if _tracked(alias.name, _from_composer(node.module)):
                    aliases[local] = alias.name
                elif alias.name == "sender_guard":
                    modules.add(local)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _from_composer(alias.name) and alias.asname:
                    modules.add(alias.asname)
    return aliases, modules


def _is_composer_module(node: ast.expr, modules: set[str]) -> bool:
    """*node* names the composer module (``sg`` or ``behaviors.sender_guard``)."""
    if isinstance(node, ast.Name):
        return node.id in modules
    return isinstance(node, ast.Attribute) and node.attr == "sender_guard"


def _named_sender_node(
    node: ast.AST, aliases: dict[str, str], modules: set[str], rel: str
) -> str | None:
    """The sender node or composer function *node* names, or ``None``.

    A public composer builder is not reported in :data:`COMPOSE_CALLERS`.
    """
    named: str | None = None
    if isinstance(node, ast.Name):
        named = aliases.get(node.id)
    elif isinstance(node, ast.Attribute) and _tracked(
        node.attr, _is_composer_module(node.value, modules)
    ):
        named = node.attr
    if named in _COMPOSE and rel in COMPOSE_CALLERS:
        return None
    return named


def _sender_references(tree: ast.AST, rel: str) -> Counter[Site]:
    """Every place in *tree* that names a sender node or composes a guard.

    A name counts wherever it is used, not only where it is called, so a node
    class or the composer bound to another name first, or reached through
    its module (``sender_entitlement.SenderIsX``), is still seen.  An import
    alias is followed; a name inside a type annotation composes nothing and
    is skipped.  A public composer builder counts outside
    :data:`COMPOSE_CALLERS`, and the composer's private builders count
    everywhere.  A site is scoped by its enclosing classes and functions.
    """
    aliases, modules = _import_aliases(tree)
    skipped = _annotation_nodes(tree)
    found: Counter[Site] = Counter()

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            scope = (*scope, node.name)
        if id(node) not in skipped and (
            named := _named_sender_node(node, aliases, modules, rel)
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
        *_COMPOSE,
        "sender_guard",
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
#: Empty: #4696 moved the last ones, whose case is resolved at run time, into
#: the factory, so a new entry is a regression.
GUARDS_NOT_YET_MIGRATED: dict[Site, Listed] = {}

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
        "vultron/core/behaviors/case/owner_close_embargo_guards.py",
        "owner_close_blocked_by_embargo_guards",
        "SenderIsCaseOwnerNode",
    ): Listed(
        1,
        "decides whether a live embargo blocks the closer's Leave, on receipt"
        " and in the leave-case trigger (CM-23-011, TRIG-13-003)",
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
}


def _listed() -> dict[Site, int]:
    return {
        site: entry.uses
        for site, entry in (GUARDS_NOT_YET_MIGRATED | STANDING_READS).items()
    }


def _site_lines(sites: dict[Site, int], listed: dict[Site, int]) -> str:
    return "\n".join(
        f"  - {s.module}::{s.function} ({s.node} x{uses},"
        f" allow-listed x{listed.get(s, 0)})"
        for s, uses in sorted(sites.items())
    )


@pytest.mark.spec("HP-01-007")
@pytest.mark.spec("HP-01-008")
def test_sender_nodes_are_composed_only_by_the_factory() -> None:
    """A sender node outside the factory's composer is allow-listed (AC-5)."""
    found = dict(_live_sites())
    listed = _listed()
    new = {s: n for s, n in found.items() if n > listed.get(s, 0)}
    fewer = {s: n for s, n in found.items() if listed.get(s, 0) > n > 0}
    stale = {s: n for s, n in listed.items() if s not in found}
    assert not new, (
        "These modules name a sender-entitlement node, or compose a sender"
        " guard, outside the receive-tree factory or more often than the"
        " allow-list says (HP-01-007, HP-01-008).  Declare the standing in"
        " the use case's SenderRule and pass it with a SenderCheckContext"
        " to the tree's factory:\n" + _site_lines(new, listed)
    )
    assert not fewer, (
        "These allow-list entries count more uses than the site now has;"
        " lower the count so the list only shrinks:\n"
        + _site_lines(fewer, listed)
    )
    assert not stale, (
        "These allow-list entries no longer name a sender node; remove them"
        " so the list only shrinks:\n" + _site_lines(stale, listed)
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
#: Empty: #4785 retired the last one, the Announce(VulnerabilityCase)
#: trust-anchor guard, when that use case declared its sender rule.  An entry
#: needs an open issue that retires it.
SENDER_CHECKS_DEFINED_ELSEWHERE: dict[tuple[str, str], str] = {}


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
    "compose-alias": (
        "from vultron.core.behaviors.sender_guard import"
        " compose_sender_guard as compose\n"
        "def execute(rule, ctx):\n"
        "    return compose(rule, ctx)\n"
    ),
    "compose-bound-before-call": (
        "from vultron.core.behaviors import sender_guard\n"
        "def execute(rule, ctx):\n"
        "    build = sender_guard.compose_sender_guard\n"
        "    return build(rule, ctx)\n"
    ),
    "handler-closed-sender-guard": (
        "from vultron.core.behaviors.sender_guard import"
        " closed_sender_guard\n"
        "def execute(case_id, sender_id):\n"
        "    return closed_sender_guard(case_id, sender_id)\n"
    ),
    "handler-closed-sender-door": (
        "from vultron.core.behaviors.sender_guard import"
        " closed_sender_door\n"
        "def execute(case_id, check):\n"
        "    return closed_sender_door(case_id, check)\n"
    ),
    "handler-case-owner-guard": (
        "from vultron.core.behaviors.sender_guard import"
        " case_owner_guard\n"
        "def execute(case_id, sender_id):\n"
        "    return case_owner_guard(case_id, sender_id)\n"
    ),
    "private-builder": (
        "from vultron.core.behaviors.sender_guard import _kind_node\n"
        "def build(kind, ctx):\n"
        "    return _kind_node(kind, ctx)\n"
    ),
    "private-builder-module-attribute": (
        "import vultron.core.behaviors.sender_guard as sg\n"
        "def build(kinds, ctx):\n"
        "    return sg._any_of(kinds, ctx, 'side')\n"
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
        "def closing(case_id, check):\n"
        "    return closed_sender_door(case_id, check)\n"
    )
    for caller in COMPOSE_CALLERS:
        assert not _sender_references(composed, caller)


def test_the_scan_ignores_a_local_helper_named_like_a_builder() -> None:
    """A private builder counts only when it comes from the composer."""
    local = _corpus.parse_inline(
        "def _any_of(xs):\n    return any(xs)\n"
        "def check(xs):\n    return _any_of(xs)\n"
    )
    assert not _sender_references(local, "vultron/x.py")


def test_the_scan_scopes_a_site_by_its_class() -> None:
    """Two classes' methods of one name are two sites, not one count."""
    source = _corpus.parse_inline(
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderIsCaseOwnerNode\n"
        "class A:\n    def build(self):\n"
        "        return SenderIsCaseOwnerNode()\n"
        "class B:\n    def build(self):\n"
        "        return SenderIsCaseOwnerNode()\n"
    )
    assert _sender_references(source, "vultron/x.py") == {
        Site("vultron/x.py", "A.build", "SenderIsCaseOwnerNode"): 1,
        Site("vultron/x.py", "B.build", "SenderIsCaseOwnerNode"): 1,
    }


# ---------------------------------------------------------------------------
# HP-01-008: the guard is composed from the declaration alone
# ---------------------------------------------------------------------------

_RULE_BUILDERS = frozenset({"SenderRule"})


def _rule_aliases(tree: ast.AST) -> set[str]:
    """The names *tree* binds to ``SenderRule``."""
    names = set(_RULE_BUILDERS)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(
                alias.asname
                for alias in node.names
                if alias.name in _RULE_BUILDERS and alias.asname
            )
    return names


def _builds_rule(func: ast.expr, names: set[str]) -> bool:
    """*func* is ``SenderRule`` or one of its constructors (``in_case``, …)."""
    if isinstance(func, ast.Name):
        return func.id in names
    if isinstance(func, ast.Attribute):
        return func.attr in _RULE_BUILDERS or _builds_rule(func.value, names)
    return False


def _declaration_nodes(tree: ast.AST) -> set[int]:
    """Ids of every node inside a class's ``sender_entitlement`` value."""
    ids: set[int] = set()
    for cls in ast.walk(tree):
        if not isinstance(cls, ast.ClassDef):
            continue
        for stmt in cls.body:
            if isinstance(stmt, ast.AnnAssign):
                targets: list[ast.expr] = [stmt.target]
            elif isinstance(stmt, ast.Assign):
                targets = stmt.targets
            else:
                continue
            declares = any(
                isinstance(t, ast.Name) and t.id == "sender_entitlement"
                for t in targets
            )
            if declares and (value := stmt.value) is not None:
                ids.update(id(sub) for sub in ast.walk(value))
    return ids


def _rules_built_outside_a_declaration(tree: ast.AST, rel: str) -> list[str]:
    """Each ``SenderRule`` *tree* builds anywhere but a declaration."""
    names = _rule_aliases(tree)
    declared = _declaration_nodes(tree)
    return [
        f"{rel}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _builds_rule(node.func, names)
        and id(node) not in declared
    ]


@pytest.mark.spec("HP-01-008")
def test_a_sender_rule_is_built_only_as_a_declaration() -> None:
    """A tree or handler passes its declared rule, never one of its own.

    ``sender_rule=`` takes a rule as an argument, so a
    rule built on the spot would compose a guard the use case never
    declared.  Building a ``SenderRule`` is allowed only as the value of a
    class's ``sender_entitlement``.
    """
    found = [
        site
        for path, tree in _corpus.files_mentioning(
            "SenderRule", under=_corpus.REPO_ROOT / "vultron"
        )
        if (rel := path.relative_to(_corpus.REPO_ROOT).as_posix()) != _HOME
        for site in _rules_built_outside_a_declaration(tree, rel)
    ]
    assert not found, (
        "A SenderRule is built outside a use case's sender_entitlement"
        " declaration (HP-01-008); pass the declared rule instead:\n"
        + "\n".join(f"  - {site}" for site in found)
    )


@pytest.mark.parametrize(
    "source",
    [
        "def execute(self):\n"
        "    return rule_refusal(dl, a, SenderRule.in_case(K.ANY_ACTOR), c)\n",
        "from vultron.core.behaviors.sender_entitlement import"
        " SenderRule as R\n"
        "def build():\n    return R(at_case_manager=frozenset())\n",
        "class UseCase:\n"
        "    sender_entitlement = SenderRule.in_case(K.INVITEE)\n"
        "    def execute(self):\n"
        "        return tree(sender_rule=SenderRule.before_case(K.ANY_ACTOR))\n",
    ],
    ids=["pre-flight", "alias", "beside-a-declaration"],
)
def test_the_rule_scan_sees_an_ad_hoc_rule(source: str) -> None:
    """Each ad hoc rule is reported (HP-01-008)."""
    tree = _corpus.parse_inline(source)
    assert len(_rules_built_outside_a_declaration(tree, "vultron/x.py")) == 1


def test_the_rule_scan_admits_a_declaration() -> None:
    """A ``sender_entitlement`` class declaration is where a rule is built."""
    tree = _corpus.parse_inline(
        "class UseCase:\n"
        "    sender_entitlement: ClassVar[SenderRule] = SenderRule.in_case(\n"
        "        K.INVITEE\n    )\n"
    )
    assert not _rules_built_outside_a_declaration(tree, "vultron/x.py")


# ---------------------------------------------------------------------------
# HP-01-007: an exemption names an open issue, or says no check applies
# ---------------------------------------------------------------------------

#: The open issues that own a not-yet-checked use case's sender rule.  The
#: list only shrinks: an exemption naming any other issue fails, and so does
#: an issue no exemption names any more.  That each is still open is checked
#: when an entry is added or reviewed, since the suite runs offline.
OPEN_EXEMPTION_ISSUES: dict[str, str] = {}

#: The use cases no sender check applies to, each declared with
#: ``no_sender_check``: nothing they do is gated on a sender's standing.
PERMANENT_EXEMPTIONS: frozenset[str] = frozenset(
    {
        "UnknownUseCase",
        "UnresolvableObjectUseCase",
    }
)


def _exemptions() -> dict[str, SenderExemption]:
    return {
        use_case.__name__: declared
        for entry in SEMANTIC_REGISTRY
        if (use_case := entry.use_case_class) is not None
        and isinstance(
            declared := getattr(use_case, "sender_entitlement", None),
            SenderExemption,
        )
    }


@pytest.mark.spec("HP-01-007")
def test_every_exemption_names_an_open_issue_or_no_check_applies() -> None:
    exemptions = _exemptions()
    permanent = {name for name, e in exemptions.items() if e.permanent}
    assert permanent == PERMANENT_EXEMPTIONS, (
        "A use case to which no sender check applies is listed here, so"
        " no_sender_check does not spread: found"
        f" {sorted(permanent ^ PERMANENT_EXEMPTIONS)}"
    )
    tracked = {
        e.tracking_issue
        for e in exemptions.values()
        if e.tracking_issue is not None
    }
    assert tracked <= set(OPEN_EXEMPTION_ISSUES), (
        "These exemptions name an issue not on the open list; point them at"
        f" the open issue that owns the check: {sorted(tracked - set(OPEN_EXEMPTION_ISSUES))}"
    )
    assert set(OPEN_EXEMPTION_ISSUES) <= tracked, (
        "No exemption names these issues any more; drop them so the list"
        f" only shrinks: {sorted(set(OPEN_EXEMPTION_ISSUES) - tracked)}"
    )
