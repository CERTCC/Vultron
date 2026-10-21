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

"""Core builds no ``payloadSnapshot`` by hand (VM-08-003, #3743).

A ledger entry's ``payloadSnapshot`` is either the activity received, as
received, or an activity the CASE_MANAGER sends: the blob the factory built
and sealed (VM-08-003).  A dict literal shaped like an activity, with a
``"type"`` and an ``"actor"`` key, assembled in ``vultron/core/``, records an
activity nobody sent, which is what case closure, the late-Accept
acknowledgement, the invitation expiry, the honoured late Accept and the
ownership-transfer Offer expiry did before #3743 (ADR-0140).

The ratchet has reached zero: no core function holds such a literal.  Build
the activity with a factory through ``TriggerActivityPort`` and commit its
sealed blob instead.
"""

import ast
from collections import Counter
from collections.abc import Iterator

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"

_ACTIVITY_KEYS = frozenset({"type", "actor"})


def _constant_keys(node: ast.Dict) -> set[str]:
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _is_activity_shaped(node: ast.AST) -> bool:
    """A ``{...}`` literal or ``dict(...)`` call with ``type`` and ``actor`` keys."""
    if isinstance(node, ast.Dict):
        return _constant_keys(node) >= _ACTIVITY_KEYS
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "dict"
    ):
        return {kw.arg for kw in node.keywords if kw.arg} >= _ACTIVITY_KEYS
    return False


def _activity_literals(
    node: ast.AST, scope: tuple[str, ...] = ()
) -> Iterator[tuple[str, int]]:
    """``(enclosing qualname, line)`` of each activity-shaped dict literal."""
    for child in ast.iter_child_nodes(node):
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            yield from _activity_literals(child, (*scope, child.name))
            continue
        if _is_activity_shaped(child):
            yield ".".join(scope) or "<module>", _corpus.node_line(child)
        yield from _activity_literals(child, scope)


def _sites() -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for path, tree in _corpus.all_trees(_CORE):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for qualname, _ in _activity_literals(tree):
            found[(rel, qualname)] += 1
    return found


def test_the_scan_reads_core():
    """Guard against a vacuous pass: the scan parses the core tree."""
    assert any(True for _ in _corpus.all_trees(_CORE))


def test_the_scan_sees_a_literal_inside_a_method():
    tree = _corpus.parse_inline(
        "class Node:\n"
        "    def update(self):\n"
        "        return {'type': 'Leave', 'actor': 'urn:a'}\n"
    )
    assert [q for q, _ in _activity_literals(tree)] == ["Node.update"]


def test_the_scan_sees_a_dict_call():
    tree = _corpus.parse_inline(
        "def build():\n    return dict(type='Leave', actor='urn:a')\n"
    )
    assert [q for q, _ in _activity_literals(tree)] == ["build"]


def test_core_builds_no_payload_snapshot_by_hand():
    """No activity-shaped dict literal remains under core (VM-08-003)."""
    sites = sorted(f"{path}::{qualname}" for path, qualname in _sites())
    assert not sites, (
        "Activity-shaped dict literals under vultron/core/ (VM-08-003): build"
        " the activity with a factory through TriggerActivityPort and commit"
        f" its sealed blob: {sites}"
    )
