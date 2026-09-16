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
"""Architecture ratchet: single neutral role-authority resolver (ARCH-24-001..004).

Verifies the ADR-0088 invariant that ``resolve_case_manager_id`` is defined in
exactly one module (``vultron.core.participants.authority``), that neither
``vultron.core.behaviors`` nor ``vultron.core.use_cases`` contains a twin
definition, and that exactly one authority condition node
(``CheckIsCaseManagerNode``) exists — with the old Service-based nodes removed.

Also ratchets the *negative* half of the ADR: no protocol-logic module may
branch on the ``case-actor`` name/URL shape (the retired
``is_case_actor_identity`` predicate or the URL substring) to determine
authority, recognition, or routing.

Spec: ARCH-24-001, ARCH-24-002, ARCH-24-003, ARCH-24-004, CM-02-013.
"""

import ast

from test.architecture import _corpus

_RESOLVER_NAME = "resolve_case_manager_id"
_NEUTRAL_MODULE = "vultron/core/participants/authority.py"
_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"
_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"
_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"

_AUTHORITY_NODE_NAME = "CheckIsCaseManagerNode"
_REMOVED_NODE_NAMES = ["CheckIsOwnCaseActorNode", "CheckIsNotOwnCaseActorNode"]

#: The retired URL-shape predicate.  Deleted by ADR-0088; must not come back.
_SHAPE_PREDICATE = "is_case_actor_identity"

#: The URL substring that carries no protocol meaning (CM-02-013).
_COSMETIC_SUBSTRING = "case-actor"

#: Protocol logic, for ARCH-24-004's purposes.  ``vultron/demo/`` and
#: ``vultron/config/`` are excluded on purpose: provisioning a container at a
#: readable ``case-actor`` URL is exactly the cosmetic convenience ADR-0088 §7
#: preserves.  ``case_actor_identity.py`` builds that provisioned identity and
#: legitimately owns the segment constant.
_PROTOCOL_ROOTS = [
    _corpus.REPO_ROOT / "vultron" / "core",
    _corpus.REPO_ROOT / "vultron" / "wire",
    _corpus.REPO_ROOT / "vultron" / "adapters",
]
_PROVISIONING_EXEMPT = {
    "vultron/core/behaviors/case/case_actor_identity.py",
}

#: String methods that turn a literal into a branch on identity shape.
_SHAPE_TEST_METHODS = {"startswith", "endswith", "find", "index", "count"}


def _defines_function(tree: ast.AST, name: str) -> bool:
    """Return True if *tree* contains a top-level ``def name(...)``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return True
    return False


def _defines_class(tree: ast.AST, name: str) -> bool:
    """Return True if *tree* contains a ``class name(...)`` definition."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return True
    return False


def _collect_defining_modules() -> set[str]:
    """Return repo-relative paths of all modules that define *_RESOLVER_NAME*."""
    found: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_VULTRON_ROOT
    ):
        if _defines_function(tree, _RESOLVER_NAME):
            found.add(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    return found


def test_exactly_one_resolver_module():
    """Only ``vultron/core/participants/authority.py`` may define resolve_case_manager_id.

    Spec: ARCH-24-001
    """
    defining = _collect_defining_modules()
    assert defining == {_NEUTRAL_MODULE}, (
        f"Expected exactly one definition of '{_RESOLVER_NAME}' in"
        f" '{_NEUTRAL_MODULE}'.\n"
        f"Actual defining modules: {sorted(defining)}"
    )


def test_behaviors_does_not_define_resolver():
    """vultron/core/behaviors/ must not define its own resolve_case_manager_id twin.

    Spec: ARCH-24-002, BTND-04-003
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_BEHAVIORS_ROOT
    ):
        if _defines_function(tree, _RESOLVER_NAME):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"behaviors/ must not define '{_RESOLVER_NAME}'; found in:"
        f" {violations}"
    )


def test_use_cases_does_not_define_resolver():
    """vultron/core/use_cases/ must not define its own _resolve_case_manager_id twin.

    Spec: ARCH-24-001
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _RESOLVER_NAME, under=_USE_CASES_ROOT
    ):
        if _defines_function(tree, _RESOLVER_NAME):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"use_cases/ must not define '{_RESOLVER_NAME}'; found in:"
        f" {violations}"
    )


def test_removed_authority_nodes_are_not_defined():
    """ARCH-24-003: CheckIsOwnCaseActorNode and CheckIsNotOwnCaseActorNode must not be defined.

    These Service-scan nodes were retired by ADR-0088 in favour of the single
    role-based ``CheckIsCaseManagerNode``.  Any re-introduction is a spec
    violation.

    Spec: ARCH-24-003
    """
    violations: list[str] = []
    for node_name in _REMOVED_NODE_NAMES:
        for py_file, tree in _corpus.files_mentioning(
            node_name, under=_VULTRON_ROOT
        ):
            if _defines_class(tree, node_name):
                violations.append(
                    f"{py_file.relative_to(_corpus.REPO_ROOT).as_posix()}:"
                    f" {node_name}"
                )
    assert not violations, (
        "Retired Service-scan authority nodes must not be defined anywhere:\n"
        + "\n".join(violations)
    )


def test_exactly_one_authority_condition_node():
    """ARCH-24-003: CheckIsCaseManagerNode is defined in exactly one module.

    Spec: ARCH-24-003
    """
    defining: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _AUTHORITY_NODE_NAME, under=_VULTRON_ROOT
    ):
        if _defines_class(tree, _AUTHORITY_NODE_NAME):
            defining.append(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    assert len(defining) == 1, (
        f"Expected exactly one definition of '{_AUTHORITY_NODE_NAME}'.\n"
        f"Actual: {sorted(defining)}"
    )


# ---------------------------------------------------------------------------
# ARCH-24-004 / CM-02-013 — the name and URL shape carry no protocol meaning
# ---------------------------------------------------------------------------


def test_shape_predicate_is_not_defined_anywhere():
    """ARCH-24-004: ``is_case_actor_identity`` must not exist.

    ADR-0088 deleted it.  Authority derives from the ``CVDRole.CASE_MANAGER``
    role alone, so a predicate whose whole job is testing a URL suffix has no
    correct caller.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _SHAPE_PREDICATE, under=_VULTRON_ROOT
    ):
        if _defines_function(tree, _SHAPE_PREDICATE):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"'{_SHAPE_PREDICATE}' was retired by ADR-0088 and must not be"
        f" redefined; found in: {violations}"
    )


def _references_name(tree: ast.AST, name: str) -> bool:
    """Return True if *tree* imports or references *name* in executable code."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == name for alias in node.names):
                return True
    return False


def test_shape_predicate_has_no_callers():
    """ARCH-24-004: nothing under ``vultron/`` may import or call the shape predicate.

    Catches a re-introduction that lands the definition outside ``vultron/``
    (a test helper, say) and imports it into protocol logic.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for py_file, tree in _corpus.files_mentioning(
        _SHAPE_PREDICATE, under=_VULTRON_ROOT
    ):
        if _references_name(tree, _SHAPE_PREDICATE):
            violations.append(
                py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            )
    assert not violations, (
        f"'{_SHAPE_PREDICATE}' must have no callers; referenced in:"
        f" {violations}"
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Return ``id()`` of every docstring Constant node in *tree*.

    Docstrings *describing* the retired signal are wanted — several modules
    explain why it is gone.  Only executable code is a branch.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue
        body = getattr(node, "body", [])
        if not body or not isinstance(body[0], ast.Expr):
            continue
        first = body[0].value
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            ids.add(id(first))
    return ids


#: Names that stand in for the literal.  A module that imports
#: ``CASE_ACTOR_SEGMENT`` (or binds its own constant) and then tests a suffix
#: built from it never contains the string `case-actor`, so matching only on the
#: literal would miss verbatim the body of the deleted ``is_case_actor_identity``.
_SEGMENT_ALIASES = frozenset({"CASE_ACTOR_SEGMENT", "CASE_ACTOR_SLUG"})


def _binds_the_segment(tree: ast.AST) -> set[str]:
    """Return local names bound to a ``case-actor`` literal or a known alias.

    Catches the indirection that defeats a literal-only scan::

        SUFFIX = "/actors/case-actor"      # or: from ... import CASE_ACTOR_SEGMENT
        if actor_id.endswith(SUFFIX):      # no `case-actor` literal in sight
    """
    names = set(_SEGMENT_ALIASES)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _SEGMENT_ALIASES:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Assign):
            if not _mentions_segment(node.value, set(), names):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _mentions_segment(
    node: ast.AST, skip: set[int], names: frozenset[str] | set[str]
) -> bool:
    """True if *node*'s subtree holds a ``case-actor`` literal or a bound alias."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant):
            if id(sub) in skip:
                continue
            if (
                isinstance(sub.value, str)
                and _COSMETIC_SUBSTRING in sub.value.lower()
            ):
                return True
        elif isinstance(sub, ast.Name) and sub.id in names:
            return True
        elif isinstance(sub, ast.Attribute) and sub.attr in names:
            return True
    return False


def _shape_branches(tree: ast.AST) -> list[str]:
    """Return descriptions of branches taken on the ``case-actor`` identity shape."""
    skip = _docstring_nodes(tree)
    names = _binds_the_segment(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        # `x == "...case-actor"`, `"case-actor" in x`, `x == SUFFIX`, etc.
        if isinstance(node, ast.Compare) and _mentions_segment(
            node, skip, names
        ):
            found.append(
                f"line {node.lineno}: comparison on the case-actor shape"
            )
        # `x.endswith("...case-actor")` / `x.endswith(SUFFIX)` and friends.
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _SHAPE_TEST_METHODS
            and any(_mentions_segment(arg, skip, names) for arg in node.args)
        ):
            found.append(
                f"line {node.lineno}: .{node.func.attr}() on the case-actor shape"
            )
    return found


def test_no_protocol_logic_branches_on_the_case_actor_url():
    """ARCH-24-004: no protocol-logic module may branch on the ``case-actor`` URL.

    The string is a provisioning convenience with no protocol meaning
    (CM-02-013).  Holding a literal is fine — example URIs and the provisioned
    identity segment both do — but *testing* one to decide authority,
    recognition, or routing is the violation, so this ratchet flags comparisons
    and shape-test calls rather than mere occurrences.

    Spec: ARCH-24-004, CM-02-013
    """
    violations: list[str] = []
    for root in _PROTOCOL_ROOTS:
        # The alias fragments matter as much as the literal: a module that
        # imports `CASE_ACTOR_SEGMENT` and builds the suffix from it holds no
        # `case-actor` string, so a literal-only prefilter would never open it.
        for py_file, tree in _corpus.files_mentioning(
            _COSMETIC_SUBSTRING, *_SEGMENT_ALIASES, under=root
        ):
            rel = py_file.relative_to(_corpus.REPO_ROOT).as_posix()
            if rel in _PROVISIONING_EXEMPT:
                continue
            violations.extend(f"{rel}:{hit}" for hit in _shape_branches(tree))
    assert not violations, (
        "Protocol logic must not branch on the cosmetic 'case-actor' URL"
        " (ARCH-24-004); authority is the CVDRole.CASE_MANAGER role:\n"
        + "\n".join(violations)
    )


def test_ratchet_detects_a_shape_branch():
    """The ARCH-24-004 scanner must actually fire on a violating pattern.

    Without this, a scanner bug would read as a clean repo.  Spec: ARCH-24-004
    """
    offending = _corpus.parse_inline(
        "def f(actor_id):\n"
        '    """Docstring naming /actors/case-actor must not count."""\n'
        '    return actor_id.endswith("/actors/case-actor")\n'
    )
    assert _shape_branches(offending), "scanner missed an endswith() branch"

    compare = _corpus.parse_inline(
        'x = a == "https://e.org/actors/case-actor"\n'
    )
    assert _shape_branches(compare), "scanner missed a comparison branch"

    benign = _corpus.parse_inline(
        'CASE_ACTOR_URI = "https://example.org/actors/case-actor"\n'
    )
    assert not _shape_branches(benign), "scanner flagged a plain literal"

    docstring_only = _corpus.parse_inline(
        '"""Explains why .../actors/case-actor is cosmetic."""\n'
    )
    assert not _shape_branches(
        docstring_only
    ), "scanner flagged a docstring mention"


def test_ratchet_is_not_evaded_by_binding_the_literal_to_a_name():
    """Indirection must not launder the branch. Spec: ARCH-24-004

    A literal-only matcher is defeated two ways, and both reconstruct the body
    of the deleted ``is_case_actor_identity`` without ever writing
    ``case-actor``: import the segment constant, or bind a local one.
    """
    via_import = _corpus.parse_inline(
        "from vultron.core.behaviors.case.case_actor_identity import (\n"
        "    CASE_ACTOR_SEGMENT,\n"
        ")\n"
        "def f(actor_id):\n"
        '    return actor_id.rstrip("/").endswith(\n'
        '        f"/actors/{CASE_ACTOR_SEGMENT}"\n'
        "    )\n"
    )
    assert _shape_branches(
        via_import
    ), "scanner missed a branch built from the imported segment constant"

    via_local_constant = _corpus.parse_inline(
        'SUFFIX = "/actors/case-actor"\n'
        "def f(actor_id):\n"
        "    return actor_id.endswith(SUFFIX)\n"
    )
    assert _shape_branches(
        via_local_constant
    ), "scanner missed a branch built from a locally bound constant"

    aliased_import = _corpus.parse_inline(
        "from x import CASE_ACTOR_SEGMENT as SEG\n"
        "def f(a):\n"
        "    return a == SEG\n"
    )
    assert _shape_branches(
        aliased_import
    ), "scanner missed a branch on an as-renamed segment import"
