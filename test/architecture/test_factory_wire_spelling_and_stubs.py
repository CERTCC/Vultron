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

- AF-01-007: no production module outside the wire layer builds a
  ``CasePreview`` (wire alias ``as_CasePreview``) to hand a factory; it hands
  the domain object and the factory builds the case's preview.
- AF-01-008: no factory spells an AS2 field name by hand; the alias a core
  object inherits is the only source of the wire spelling (ARCH-12-013).
"""

import ast
import re

import pytest

from test.architecture import _corpus

#: The case's preview, one class under two names (ARCH-25-003).
_PREVIEW_NAMES = frozenset({"CasePreview", "as_CasePreview"})

#: The wire layer's factories build the preview.
_STUB_ALLOWED_PREFIX = "vultron/wire/as2/"

_FACTORIES = _corpus.REPO_ROOT / "vultron" / "wire" / "as2" / "factories"

#: A bare camelCase identifier, the form every AS2 member name takes.
_CAMEL = re.compile(r"^[a-z]+(?:[A-Z][a-z0-9]*)+$")


def _builds_a_preview(tree: ast.AST) -> bool:
    """Whether *tree* calls the preview class to construct one."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr
            if isinstance(func, ast.Attribute)
            else None
        )
        if name in _PREVIEW_NAMES:
            return True
    return False


@pytest.mark.spec("AF-01-007")
def test_no_production_module_outside_the_wire_layer_builds_a_case_preview():
    """A caller hands the factory the case, never a preview it assembled."""
    offenders = sorted(
        path.relative_to(_corpus.REPO_ROOT).as_posix()
        for path, tree in _corpus.files_mentioning(
            "CasePreview", under=_corpus.REPO_ROOT / "vultron"
        )
        if not path.relative_to(_corpus.REPO_ROOT)
        .as_posix()
        .startswith(_STUB_ALLOWED_PREFIX)
        and _builds_a_preview(tree)
    )
    assert offenders == [], (
        "These modules build a CasePreview outside the wire layer; hand the"
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


@pytest.mark.parametrize(
    "source",
    [
        "x = as_CasePreview(summary='s')\n",
        "x = CasePreview(summary='s')\n",
        "x = models.CasePreview(summary='s')\n",
    ],
)
def test_the_preview_check_catches_a_preview_built_outside_the_wire_layer(
    source: str,
) -> None:
    """The AF-01-007 scan is not vacuous: it flags a call to either name."""
    assert _builds_a_preview(_corpus.parse_inline(source))


def test_the_preview_check_passes_a_mere_mention() -> None:
    """Naming the class in an annotation builds nothing."""
    tree = _corpus.parse_inline("def f(p: CasePreview) -> None: ...\n")
    assert not _builds_a_preview(tree)
