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

"""Ratchet: core builds no ``payloadSnapshot`` by hand (VM-08-003, #3743).

A ledger entry's ``payloadSnapshot`` is either the activity received, as
received, or an activity the CASE_MANAGER sends: the blob the factory built
and sealed (VM-08-003).  A dict literal shaped like an activity, with a
``"type"`` and an ``"actor"`` key, assembled in ``vultron/core/``, records an
activity nobody sent, which is what case closure and the late-Accept
acknowledgement did before #3743.

Every such literal is counted by file and enclosing function and compared to
an exact baseline, so a new site, or a second literal in a baselined
function, fails, and a removed one must be taken out (the set may only
shrink, ARCH-18-002).  Each baseline row names the issue that removes it.
"""

import ast
from collections import Counter
from collections.abc import Iterator

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"

#: All three remaining sites wait on one ledger-vocabulary decision, held for
#: the maintainer in #4723 (ADR-0140): the AS2 shape that replaces the
#: synthetic ``Expire`` type (no AS2 type, no wire vocabulary class a factory
#: could build), and whether the honoured late Accept keeps an act entry of its
#: own.  The consent-row copy the two embargo-invitation rows once waited on
#: (#4295) has landed: each act is already followed by the CASE_MANAGER's
#: ``Update(EmbargoConsent)`` carrying the row, which replicas copy, so the act
#: entry changes no replica state; what is left is its shape and attribution
#: (the invitee or the accepter, who sent nothing).  The ownership-transfer
#: Offer expiry (CM-21-017) is already the CASE_MANAGER's own act and needs
#: only the shape.
_AWAITS_LEDGER_VOCABULARY = "#4723"

#: Activity-shaped dict literals still built in core, by ``(file, function)``,
#: with how many each holds.  Each row is removed by the issue it names; add
#: none (VM-08-003).
_BASELINE: dict[tuple[str, str], tuple[int, str]] = {
    (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "expiry_payload_snapshot",
    ): (1, _AWAITS_LEDGER_VOCABULARY),
    (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "honour_late_accept_payload_snapshot",
    ): (1, _AWAITS_LEDGER_VOCABULARY),
    (
        "vultron/core/behaviors/case/nodes/ownership_offer_expiry.py",
        "ownership_offer_expiry_snapshot",
    ): (1, _AWAITS_LEDGER_VOCABULARY),
}

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


def test_the_scan_finds_a_known_site():
    """Guard against a vacuous pass: the scan sees a baseline row."""
    assert (
        "vultron/core/behaviors/embargo/expiry_tree.py",
        "expiry_payload_snapshot",
    ) in _sites()


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


def test_core_builds_no_new_payload_snapshot_by_hand():
    """Activity-shaped dict literals in core equal the baseline (VM-08-003)."""
    actual = _sites()
    expected = {site: count for site, (count, _) in _BASELINE.items()}
    changed = {
        f"{path}::{qualname} ({expected.get((path, qualname), 0)} -> {count})"
        for (path, qualname), count in actual.items()
        if count != expected.get((path, qualname), 0)
    }
    gone = {
        f"{path}::{qualname}"
        for (path, qualname) in expected
        if (path, qualname) not in actual
    }
    assert not changed and not gone, (
        "Activity-shaped dict literals under vultron/core/ changed"
        " (VM-08-003).\n"
        f"  new or more (build the activity with a factory through"
        f" TriggerActivityPort and commit its sealed blob): {sorted(changed)}\n"
        f"  gone (remove the baseline row): {sorted(gone)}"
    )


def test_each_baseline_row_names_its_issue():
    assert all(issue.startswith("#") for _, issue in _BASELINE.values())
