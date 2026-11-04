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

"""One detector for "is the executing actor the case authority?" (ARCH-24-003).

Two ratchets ask it and must agree on what the act *is*, so the detector lives
here rather than in either of them (CS-22-001):

- ``test_role_authority_resolver.py`` holds the inventory of **node classes**
  that answer the question, which is ARCH-24-003's cardinality.
- ``test_received_path_role_question.py`` holds the inventory of **modules**
  that ask it other than through the path stage, which is the ADR-0153
  migration.

Two spellings answer it, and each is read from the live object, so renaming
the resolver, the predicate or the role moves the detector with the code
instead of blinding it (#5535):

1. The resolved manager compared with the executing actor's own id —
   ``resolve_case_manager_id(case, dl) == self.actor_id``, in either order,
   with either operator, and with the resolver's result bound to a name one
   or more statements earlier.
2. The shared predicate asked about the executing actor and that role —
   ``has_role(self.actor_id, case_id, CVDRole.CASE_MANAGER, dl)``.

``self.actor_id`` is the executing actor on a BT node
(``DataLayerConditionWithPorts.actor_id``). A comparison against a *local* of
the same name is usually about the sender or a ledger entry's author, which is
a different question and stays legal, so the detector requires the attribute.
"""

import ast
from pathlib import Path

from test.architecture import _corpus
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole

#: Read from the live objects, so a rename moves the detector with the code.
RESOLVER_NAME = resolve_case_manager_id.__name__
PREDICATE_NAME = has_role.__name__
AUTHORITY_ROLE_NAME = CVDRole.CASE_MANAGER.name

#: The attribute a BT node reads the executing actor's id from.
EXECUTING_ACTOR_ATTR = "actor_id"

#: ``(module path, class name)`` for a node class that answers the question.
AuthorityAsker = tuple[str, str]


def _is_resolver_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and _corpus.callee_name(node.func) == RESOLVER_NAME
    )


def _is_executing_actor(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == EXECUTING_ACTOR_ATTR
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _side_name(node: ast.expr) -> str | None:
    """The dotted name one side of a comparison reads, if it is a name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def resolver_bindings(tree: ast.AST) -> frozenset[str]:
    """Every name *tree* binds to a resolver call.

    ``manager_id = resolve_case_manager_id(case, dl)`` and its walrus and
    ``self.<attr>`` spellings, so a comparison one statement later is still
    the same act.  Without this the detector saw only the one-liner, and two
    real sites — the reporter introduction's and the condition node's own —
    were silently exempt (#5041 review).
    """
    bound: set[str] = set()

    def record(target: ast.expr) -> None:
        if isinstance(target, ast.Name):
            bound.add(target.id)
        elif isinstance(target, ast.Attribute) and isinstance(
            target.value, ast.Name
        ):
            bound.add(f"{target.value.id}.{target.attr}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_resolver_call(node.value):
            for target in node.targets:
                record(target)
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_resolver_call(node.value)
        ) or (
            isinstance(node, ast.NamedExpr) and _is_resolver_call(node.value)
        ):
            record(node.target)
    return frozenset(bound)


def compares_resolved_manager_with_the_receiver(tree: ast.AST) -> bool:
    """True when *tree* compares the resolved manager with ``self.actor_id``.

    Either order, and either operator: the act is the comparison, not the way
    it is spelled.  The resolved manager is the resolver call itself or any
    name the module bound to one (:func:`resolver_bindings`).
    """
    bound = resolver_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left, *node.comparators]
        resolved = any(
            _is_resolver_call(side) or _side_name(side) in bound
            for side in sides
        )
        if resolved and any(_is_executing_actor(side) for side in sides):
            return True
    return False


def _names_the_authority_role(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == AUTHORITY_ROLE_NAME


def asks_the_predicate_about_the_receiver(tree: ast.AST) -> bool:
    """True when *tree* asks the shared predicate about ``self.actor_id``.

    Both markers must be in the same call: the executing actor's own id, and
    the authority role.  ``has_role(self.actor_id, case_id, CVDRole.VENDOR,
    dl)`` is a permission rule inside a path, not the authority question
    (HP-01-037).
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == PREDICATE_NAME
        ):
            args = [*node.args, *(kw.value for kw in node.keywords)]
            if any(_is_executing_actor(arg) for arg in args) and any(
                _names_the_authority_role(arg) for arg in args
            ):
                return True
    return False


def answers_the_authority_question(tree: ast.AST) -> bool:
    """True when *tree* answers "is the executing actor the case authority"."""
    return compares_resolved_manager_with_the_receiver(
        tree
    ) or asks_the_predicate_about_the_receiver(tree)


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


@_corpus.gc_paused()
def node_classes_answering_it(under: Path) -> frozenset[AuthorityAsker]:
    """Every class under *under* whose body answers the authority question."""
    found: set[AuthorityAsker] = set()
    for path, tree in _corpus.files_mentioning(
        RESOLVER_NAME, PREDICATE_NAME, under=under
    ):
        for node in ast.walk(tree):
            if isinstance(
                node, ast.ClassDef
            ) and answers_the_authority_question(node):
                found.add((_rel(path), node.name))
    return frozenset(found)
