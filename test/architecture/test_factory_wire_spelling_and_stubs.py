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
"""Architecture checks for how activity factories get their wire shape.

- AF-01-007: no production module outside the wire layer builds an
  ``as_VulnerabilityCaseStub`` to hand a factory; it hands the domain object
  and the factory builds the stub.
- AF-01-008: no factory spells an AS2 field name by hand; the alias a core
  object inherits is the only source of the wire spelling (ARCH-12-013).
"""

import ast
import re

import pytest

from test.architecture import _corpus

_STUB_CLASS = "as_VulnerabilityCaseStub"

#: The wire layer defines the stub and its factories build it.
_STUB_ALLOWED_PREFIX = "vultron/wire/as2/"

_FACTORIES = _corpus.REPO_ROOT / "vultron" / "wire" / "as2" / "factories"

#: A bare camelCase identifier, the form every AS2 member name takes.
_CAMEL = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")


def _names_stub_class(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == _STUB_CLASS:
            return True
        if isinstance(node, ast.Attribute) and node.attr == _STUB_CLASS:
            return True
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == _STUB_CLASS for alias in node.names
        ):
            return True
    return False


@pytest.mark.spec("AF-01-007")
def test_no_production_module_outside_the_wire_layer_builds_a_case_stub():
    """A caller hands the factory the case, never a stub it assembled."""
    offenders = sorted(
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in _corpus.files_mentioning(
            _STUB_CLASS, under=_corpus.REPO_ROOT / "vultron"
        )
        if not path.relative_to(_corpus.REPO_ROOT)
        .as_posix()
        .startswith(_STUB_ALLOWED_PREFIX)
        and _names_stub_class(tree)
    )
    assert offenders == [], (
        f"These modules name {_STUB_CLASS} outside the wire layer; hand the"
        f" factory the domain object instead (AF-01-007): {offenders}"
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """ids of the string constants that are docstrings or bare expressions."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            found.add(id(node.value))
    return found


def _hand_spelled_members(tree: ast.AST) -> list[tuple[int, str]]:
    skip = _docstring_nodes(tree)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skip
        and _CAMEL.match(node.value)
    ]


@pytest.mark.spec("AF-01-008")
def test_no_factory_spells_an_as2_member_name_by_hand():
    """Factories take each wire spelling from the inherited field alias."""
    offenders = [
        f"{path.relative_to(_corpus.REPO_ROOT).as_posix()}:{line}: {text!r}"
        for path, tree in _corpus.all_trees(_FACTORIES)
        for line, text in _hand_spelled_members(tree)
    ]
    assert offenders == [], (
        "These factory string literals look like hand-spelled AS2 member"
        " names; read the spelling from the field alias instead"
        f" (AF-01-008, ARCH-12-013): {offenders}"
    )


def test_the_camel_case_check_catches_a_hand_spelled_member():
    """The AF-01-008 scan is not vacuous: it flags a dict key like ``activeEmbargo``."""
    tree = _corpus.parse_inline(
        'def f():\n    """inReplyTo"""\n    return {"activeEmbargo": 1}\n'
    )
    assert _hand_spelled_members(tree) == [(3, "activeEmbargo")]


def test_the_stub_check_catches_a_stub_built_outside_the_wire_layer():
    """The AF-01-007 scan is not vacuous: it flags a call to the stub class."""
    tree = _corpus.parse_inline(
        "x = as_VulnerabilityCaseStub(case_id='urn:x')\n"
    )
    assert _names_stub_class(tree)
