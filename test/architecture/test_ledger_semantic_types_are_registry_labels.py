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

"""Architecture ratchet: every ledger semantic type is a registry label (ADR-0140).

An entry's ``semantic_type`` is the semantic registry's label for its
payload, so every type the code base can commit is a ``MessageSemantics``
member with a pattern in ``SEMANTIC_REGISTRY`` (#4724 AC-1).  The committed
set is derived from code (``_ledger_commit_inventory``).

The label is named through ``MessageSemantics``, never spelled as a string:
no code string under ``vultron/core/behaviors/`` equals a semantic type
(#4724 AC-4), so renaming a member breaks the code that names it instead of
leaving a stale string.  The
in-process demo and per-actor-store harnesses check each written entry
against the registry's matcher (``test/support/ledger_labels.py``).
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._ledger_commit_inventory import (
    committed_semantic_types,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import lookup_entry
from vultron.semantic_registry._entry import DISPATCHER_FALLBACKS

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"


@pytest.mark.spec("SE-02-001")
@pytest.mark.spec("CLP-02-014")
def test_every_committed_semantic_type_has_a_registry_pattern():
    labels = {m.value: m for m in MessageSemantics}
    committed = committed_semantic_types()
    assert committed, "the inventory found nothing: the check is vacuous"
    unknown = sorted(committed - set(labels))
    assert not unknown, f"committed, but no MessageSemantics member: {unknown}"
    unmatched = sorted(
        value
        for value in committed
        if labels[value] in DISPATCHER_FALLBACKS
        or lookup_entry(labels[value]).pattern is None
    )
    assert not unmatched, f"committed, but no registry pattern: {unmatched}"


_LABELS = frozenset(m.value for m in MessageSemantics)


def _docstring_ids(tree: ast.AST) -> set[int]:
    """The ``id`` of each docstring constant in *tree*, which names nothing."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
            ):
                ids.add(id(body[0].value))
    return ids


def _all_list_ids(tree: ast.AST) -> set[int]:
    """The ``id`` of each string in an ``__all__``, which names a symbol."""
    return {
        id(element)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        )
        for element in ast.walk(node.value)
    }


def _string_literals(path: Path, tree: ast.AST) -> list[str]:
    """Each string literal in *tree* that spells a semantic type, as ``path:line``.

    Any code string equal to a ``MessageSemantics`` value counts, whatever it
    is bound to or passed as: a constant of any name, a ``semantic_type=``
    keyword, a positional argument or a comparison.  Docstrings and
    ``__all__`` entries are prose and symbol names, so they are left out.
    """
    skipped = _docstring_ids(tree) | _all_list_ids(tree)
    rel = path.relative_to(_corpus.REPO_ROOT)
    return [
        f"{rel}:{node.lineno}: {node.value!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and "_" in node.value
        and node.value in _LABELS
        and id(node) not in skipped
    ]


@pytest.mark.spec("SE-02-001")
def test_no_behavior_spells_a_semantic_type_as_a_string():
    """A semantic type is named through ``MessageSemantics`` (#4724 AC-4)."""
    trees = list(_corpus.all_trees(_BEHAVIORS_ROOT))
    assert trees, "no behavior module was scanned: vacuous"
    literals = [
        literal
        for path, tree in trees
        for literal in _string_literals(path, tree)
    ]
    assert not literals, (
        "string-literal semantic types; name the MessageSemantics member"
        f" instead: {literals}"
    )


@pytest.mark.parametrize(
    "source",
    [
        "FOO_SEMANTIC_TYPE = 'close_case'\n",
        "_CLOSE = 'close_case'\n",
        "f(semantic_type='close_case')\n",
        "commit(case_id, object_id, 'close_case', activity)\n",
        "ok = entry.semantic_type == 'close_case'\n",
    ],
)
def test_the_literal_scan_finds_each_spelling(source):
    """Guard against a vacuous pass: every way of spelling one is found."""
    tree = _corpus.parse_inline(source)
    assert len(_string_literals(_BEHAVIORS_ROOT / "x.py", tree)) == 1


def test_the_literal_scan_skips_prose_and_symbol_names():
    tree = _corpus.parse_inline(
        '"""Commits close_case."""\n'
        "def f():\n"
        '    """\'close_case\'"""\n'
        "__all__ = ['refusal_notice']\n"
    )
    assert _string_literals(_BEHAVIORS_ROOT / "x.py", tree) == []
