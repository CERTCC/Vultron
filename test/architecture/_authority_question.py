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

"""One detector for "is this actor the case authority?" (ARCH-24-008/009).

Two questions share one set of helpers, and only one of them is bounded:

- *Who* is the authority? That returns an id, addressing needs it, and
  :func:`~vultron.core.participants.authority.resolve_case_manager_id` is its
  one implementation (ARCH-24-001). Its callers are not this module's
  business.
- *Is this actor* the authority? That returns a bool, and
  :func:`~vultron.core.participants.role_predicate.has_role` asked about
  ``CVDRole.CASE_MANAGER`` is its only source (ARCH-24-008).

This module reports the **two ingredient paths** that answer the second
question without the predicate (ARCH-24-009). Both are shapes, not names, so
a fourth way of computing the answer is reported for what it does rather than
for what it is called, and there is no list of sanctioned classes to keep:

1. :data:`COMPARISON` — the resolver's returned id compared with another id.
   Either order, either operator, the resolver call itself or a name the
   module bound to one. A comparison against ``None`` is **not** this shape:
   "does the case name an authority at all" is a fact about the case and
   stays legal.
2. :data:`ROLE_LIST` — a participant's role collection tested for the
   authority role: ``CVDRole.CASE_MANAGER in …`` or
   ``…has_role(CVDRole.CASE_MANAGER)``. A list says "this record holds the
   role"; authority is one answer per case, so on a roster recording the role
   twice (CM-33) the two disagree and a tree admitted on one answer skips the
   effect gated on the other (HP-01-005, #5921).

Why the keys are read off live objects: a ratchet keyed on an implementation
name loses its subjects to a rename while its non-empty guard still passes
(#5535, ``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act,
Not on the Name of What Performs It"). Every name here —
:data:`RESOLVER_NAME`, :data:`PREDICATE_NAME`, :data:`RECORD_PREDICATE_NAME`,
:data:`ROLE_ENUM_NAME`, :data:`AUTHORITY_ROLE_NAME`,
:data:`ID_COMPARISON_NAME` — comes from the object itself.

Exemptions, each scoped to a *function* rather than a file, because a
whole-file exemption would let a renamed copy sit beside the real one
(:data:`SANCTIONED_SOURCES`):

- the single resolver's own body, which is where the role list is read once
  (ARCH-24-001);
- the shared predicate's own body, which is where the id comparison is made
  once (ARCH-24-008);
- any Pydantic validator, because refusing a *claimed* role list at
  construction is validation at the edge, not authority determination: a
  ``CaseProposal`` whose ``proposerCaseRoles`` names ``CASE_MANAGER`` is
  refused there (CP-01-012) and no participant record is in question. The
  decorator names come from ``pydantic`` itself.

Per loose reading, whether it can miss a violation or invent one
(``notes/architecture-ratchet-corpus.md`` § "Say, Per Loose Reading, Whether
It Can Miss or Invent"):

- :func:`resolver_bindings` follows a name, not a binding, so a module that
  rebinds the same name to something else and then compares it is reported
  wrongly — it can **invent**. No module in the scan does; the alternative is
  resolving bindings.
- The comparison shape ignores ``in``/``not in``. Asking whether the resolved
  manager is a key of the roster index is a fact about the case, like the
  ``None`` test, so including it would **invent**. Excluding it can
  **miss** an identity test spelled as membership in a one-element set; no
  module in the scan spells it that way.
- The role-list shape matches a membership test of the authority role in
  *anything*, not only in a participant's own field, so a module holding a
  set of roles for another purpose and testing it would be reported — it can
  **invent**. That is deliberate: narrowing it to a named field would let a
  role list passed to a helper escape, which is exactly how
  ``has_case_manager_role`` hid the one site this detector was rewritten to
  see (#5921).
- Neither shape sees a second resolver reached through a role-parameterised
  lookup (``resolve_participant_actor_by_role(case, dl, CASE_MANAGER)``), so
  it can **miss** one. ARCH-24-001's twin-resolver scan
  (``test_exactly_one_resolver_module``) covers a definition; a *call* with
  the authority role as its argument has no instance in the scan today.
- A call matches on the callee's bare name, so ``mod.resolve_case_manager_id``
  is seen but an ``import ... as`` alias is not: that can **miss** a
  comparison, and resolving import aliases is the alternative. The same
  reading applies to the predicate, where an alias instead costs the
  *compliant-asker* control a module, which fails loudly rather than quietly.
"""

import ast
from pathlib import Path

from pydantic import field_validator, model_validator

from test.architecture import _corpus
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.role_predicate import has_role
from vultron.enums.roles import CVDRole
from vultron.primitives import same_actor_id

#: Read from the live objects, so a rename moves the detector with the code.
RESOLVER_NAME = resolve_case_manager_id.__name__
PREDICATE_NAME = has_role.__name__
RECORD_PREDICATE_NAME = CaseParticipant.has_role.__name__
ROLE_ENUM_NAME = CVDRole.__name__
AUTHORITY_ROLE_NAME = CVDRole.CASE_MANAGER.name
ID_COMPARISON_NAME = same_actor_id.__name__

#: The attribute a BT node reads the executing actor's id from
#: (``DataLayerConditionWithPorts.actor_id``).  Used only by the
#: receiver-scoped reading :func:`compares_resolved_manager_with_the_receiver`,
#: which the ADR-0153 migration ratchet asks for.
EXECUTING_ACTOR_ATTR = "actor_id"

#: The two ingredient paths ARCH-24-009 forbids, labelled by the act so the
#: label survives a rename of whatever performs it.
COMPARISON = "resolved-manager id comparison"
ROLE_LIST = "participant role-list authority test"

#: Pydantic's validator decorators, read off the live objects.  A function
#: carrying one is validating a claimed value, not deciding authority.
_VALIDATOR_DECORATORS = frozenset(
    {field_validator.__name__, model_validator.__name__}
)

#: ``{repo-relative module: {function}}`` whose body may hold an ingredient:
#: the resolver reads the role list, the predicate compares the ids, and each
#: is the one implementation its requirement names.  Scoped to the function,
#: never the file.
SANCTIONED_SOURCES: dict[str, frozenset[str]] = {
    "vultron/core/participants/authority.py": frozenset({RESOLVER_NAME}),
    "vultron/core/participants/role_predicate.py": frozenset({PREDICATE_NAME}),
}

#: ``(module path, shape)`` for a site that answers the question an
#: ingredient way.
IngredientSite = tuple[str, str]


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


def _is_none(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


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


def _is_resolved_manager(node: ast.expr, bound: frozenset[str]) -> bool:
    return _is_resolver_call(node) or _side_name(node) in bound


def compares_the_resolved_manager_with_an_id(tree: ast.AST) -> bool:
    """True when *tree* compares the resolved manager with another id.

    The :data:`COMPARISON` shape.  Equality and identity operators only, and
    never against ``None``: the resolved id has nothing but another actor id
    to be equal to, while ``is None`` asks whether the case names an
    authority at all.  :func:`~vultron.primitives.same_actor_id` given the
    resolved manager is the same act spelled as a call.
    """
    bound = resolver_bindings(tree)
    identity_ops = (ast.Eq, ast.NotEq, ast.Is, ast.IsNot)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if not any(isinstance(op, identity_ops) for op in node.ops):
                continue
            sides = [node.left, *node.comparators]
            if not any(_is_resolved_manager(side, bound) for side in sides):
                continue
            if any(
                not _is_none(side) and not _is_resolved_manager(side, bound)
                for side in sides
            ):
                return True
        elif (
            isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == ID_COMPARISON_NAME
        ):
            args = [*node.args, *(kw.value for kw in node.keywords)]
            if any(_is_resolved_manager(arg, bound) for arg in args):
                return True
    return False


def compares_resolved_manager_with_the_receiver(tree: ast.AST) -> bool:
    """True when the compared id is the *executing actor's* own id.

    The receiver-scoped reading of :data:`COMPARISON`.  ADR-0153's migration
    ratchet counts "the manager is me" specifically, because that is the
    question the received-tree path stage took over; ARCH-24-009 is wider and
    uses :func:`compares_the_resolved_manager_with_an_id`.
    """
    bound = resolver_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        sides = [node.left, *node.comparators]
        resolved = any(_is_resolved_manager(side, bound) for side in sides)
        if resolved and any(_is_executing_actor(side) for side in sides):
            return True
    return False


def _names_the_authority_role(node: ast.expr) -> bool:
    """True for ``CVDRole.CASE_MANAGER``, read off the live enum.

    Both halves are required: ``ReceivedPath.CASE_MANAGER`` names a path, not
    a role, and a received tree reads it to pick a branch (HP-01-038).
    """
    return (
        isinstance(node, ast.Attribute)
        and node.attr == AUTHORITY_ROLE_NAME
        and isinstance(node.value, ast.Name)
        and node.value.id == ROLE_ENUM_NAME
    )


def tests_a_role_list_for_the_authority_role(tree: ast.AST) -> bool:
    """True when *tree* tests a role collection for the authority role.

    The :data:`ROLE_LIST` shape: ``CVDRole.CASE_MANAGER in roles`` in either
    polarity, and the per-record
    :meth:`~vultron.core.models.case_participant.CaseParticipant.has_role`
    asked about that role.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            if not any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                continue
            if _names_the_authority_role(node.left):
                return True
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == RECORD_PREDICATE_NAME
        ):
            args = [*node.args, *(kw.value for kw in node.keywords)]
            if any(_names_the_authority_role(arg) for arg in args):
                return True
    return False


def asks_the_predicate_about_the_authority_role(tree: ast.AST) -> bool:
    """True when *tree* asks the shared predicate about the authority role.

    The sanctioned source (ARCH-24-008).  Used as the detector's permanent
    positive control: this codebase does ask the question, so a scan that
    finds no compliant asker has gone blind rather than found a clean repo.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == PREDICATE_NAME
        ):
            args = [*node.args, *(kw.value for kw in node.keywords)]
            if any(_names_the_authority_role(arg) for arg in args):
                return True
    return False


def ingredient_shapes_in(tree: ast.AST) -> frozenset[str]:
    """Every ARCH-24-009 shape *tree* writes."""
    found: set[str] = set()
    if compares_the_resolved_manager_with_an_id(tree):
        found.add(COMPARISON)
    if tests_a_role_list_for_the_authority_role(tree):
        found.add(ROLE_LIST)
    return frozenset(found)


def _rel(path: Path) -> str:
    return path.relative_to(_corpus.REPO_ROOT).as_posix()


def _decorator_names(node: ast.AST) -> frozenset[str]:
    decorators = getattr(node, "decorator_list", [])
    names = {
        name
        for dec in decorators
        if (
            name := _corpus.callee_name(
                dec.func if isinstance(dec, ast.Call) else dec
            )
        )
    }
    return frozenset(names)


def _is_exempt_definition(node: ast.stmt, exempt: frozenset[str]) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
        node.name in exempt
        or bool(_decorator_names(node) & _VALIDATOR_DECORATORS)
    )


def _without_exempt_functions(
    tree: ast.AST, exempt: frozenset[str]
) -> ast.AST:
    """*tree* with every exempt function definition dropped.

    Judging the remainder rather than subtracting the exempt bodies' shapes
    keeps the exemption from hiding a sibling: an ingredient written *beside*
    an exempt function is still in what is judged.  Classes are rebuilt
    without their exempt methods, so a validator is removed wherever it sits
    while the rest of its class is still judged.
    """

    def keep(node: ast.stmt) -> ast.stmt | None:
        if _is_exempt_definition(node, exempt):
            return None
        if isinstance(node, ast.ClassDef):
            pruned = ast.ClassDef(
                name=node.name,
                bases=[],
                keywords=[],
                body=[kept for child in node.body if (kept := keep(child))],
                decorator_list=[],
                type_params=[],
            )
            return ast.copy_location(pruned, node)
        return node

    body: list[ast.stmt] = getattr(tree, "body", [])
    remainder = ast.Module(
        body=[kept for child in body if (kept := keep(child))],
        type_ignores=[],
    )
    return remainder


def _shapes_outside_exempt_functions(
    tree: ast.AST, exempt: frozenset[str]
) -> frozenset[str]:
    """:func:`ingredient_shapes_in` over *tree* minus its exempt functions."""
    shapes = ingredient_shapes_in(tree)
    if not shapes:
        return shapes
    return ingredient_shapes_in(_without_exempt_functions(tree, exempt))


@_corpus.gc_paused()
def ingredient_sites(*roots: Path) -> frozenset[IngredientSite]:
    """Every ``(module, shape)`` under *roots* that writes an ingredient.

    ARCH-24-009's subjects.  Keyed on the module and the act, never on a
    class or function name, so a rename is reported as neither new nor stale
    (#5535).
    """
    found: set[IngredientSite] = set()
    for root in roots:
        for path, tree in _corpus.files_mentioning(
            RESOLVER_NAME, AUTHORITY_ROLE_NAME, under=root
        ):
            rel = _rel(path)
            exempt = SANCTIONED_SOURCES.get(rel, frozenset())
            for shape in _shapes_outside_exempt_functions(tree, exempt):
                found.add((rel, shape))
    return frozenset(found)


@_corpus.gc_paused()
def predicate_asker_modules(*roots: Path) -> frozenset[str]:
    """Every module under *roots* asking the predicate about the authority role.

    The compliant askers, and the detector's permanent non-vacuity control.
    """
    found: set[str] = set()
    for root in roots:
        for path, tree in _corpus.files_mentioning(PREDICATE_NAME, under=root):
            if asks_the_predicate_about_the_authority_role(tree):
                found.add(_rel(path))
    return frozenset(found)


@_corpus.gc_paused()
def scanned_modules(*roots: Path) -> frozenset[str]:
    """Every module the ingredient scan actually opens.

    An empty subject set means the prefilter, the corpus or the scan roots
    stopped matching, which is a failure rather than a clean bill of health.
    """
    found: set[str] = set()
    for root in roots:
        for path, _tree in _corpus.files_mentioning(
            RESOLVER_NAME, AUTHORITY_ROLE_NAME, under=root
        ):
            found.add(_rel(path))
    return frozenset(found)
