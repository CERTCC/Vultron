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
no ``*SEMANTIC_TYPE`` constant and no ``semantic_type=`` argument under
``vultron/core/behaviors/`` is a string literal (#4724 AC-4), so renaming a
member breaks the code that names it instead of leaving a stale string.  The
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


def _string_literals(path: Path, tree: ast.AST) -> list[str]:
    """Each string-literal semantic type in *tree*, as ``path:line``."""
    found: list[str] = []
    rel = path.relative_to(_corpus.REPO_ROOT)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            named = any(
                isinstance(t, ast.Name) and t.id.endswith("SEMANTIC_TYPE")
                for t in targets
            )
            if (
                named
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                found.append(f"{rel}:{node.lineno}")
        elif isinstance(node, ast.Call):
            found.extend(
                f"{rel}:{kw.value.lineno}"
                for kw in node.keywords
                if kw.arg == "semantic_type"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            )
    return found


@pytest.mark.spec("SE-02-001")
def test_no_behavior_spells_a_semantic_type_as_a_string():
    """A semantic type is named through ``MessageSemantics`` (#4724 AC-4)."""
    scanned = 0
    literals: list[str] = []
    for path, tree in _corpus.files_mentioning(
        "SEMANTIC_TYPE", "semantic_type=", under=_BEHAVIORS_ROOT
    ):
        scanned += 1
        literals.extend(_string_literals(path, tree))
    assert scanned, "no behavior module names a semantic type: vacuous"
    assert not literals, (
        "string-literal semantic types; name the MessageSemantics member"
        f" instead: {literals}"
    )


def test_the_literal_scan_finds_a_literal():
    """Guard against a vacuous pass: the scan sees both spellings."""
    tree = _corpus.parse_inline(
        "FOO_SEMANTIC_TYPE = 'close_case'\nf(semantic_type='close_case')\n"
    )
    assert len(_string_literals(_BEHAVIORS_ROOT / "x.py", tree)) == 2
