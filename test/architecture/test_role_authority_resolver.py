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
"""Architecture ratchet: single neutral role-authority resolver (ARCH-24-001/002/003).

Verifies the ADR-0088 invariant that ``resolve_case_manager_id`` is defined in
exactly one module (``vultron.core.participants.authority``), that neither
``vultron.core.behaviors`` nor ``vultron.core.use_cases`` contains a twin
definition, and that exactly one authority condition node
(``CheckIsCaseManagerNode``) exists — with the old Service-based nodes removed.

Spec: ARCH-24-001, ARCH-24-002, ARCH-24-003.
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
