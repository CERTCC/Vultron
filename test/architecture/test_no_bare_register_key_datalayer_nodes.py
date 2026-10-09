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

"""AC-1 architecture ratchet: no new bare register_key DataLayer* leaf nodes.

AST-scans ``vultron/core/behaviors/`` for classes that:
  - directly inherit from ``DataLayerAction`` or ``DataLayerCondition``
    (the non-WithPorts variants), AND
  - contain a ``register_key()`` call in their ``setup()`` method.

Asserts the result matches the audited baseline below.  A new entry
means a new DataLayer node was added using the legacy ``register_key``
pattern instead of typed Ports — the test fails immediately, forcing an
explicit migration decision.  A removed entry means an audited node was
migrated to typed Ports — update the baseline to keep the ratchet tight.

Per specs/behavior-tree-node-design.yaml BTND-03-009.
Closes #1887 AC-1.
"""

import ast
from collections import Counter

from test.architecture import _corpus

# ---------------------------------------------------------------------------
# Audited baseline — (path_relative_to_behaviors_root, class_name)
#
# Each entry is a DataLayerAction or DataLayerCondition (non-WithPorts)
# subclass that still calls register_key() in setup().  These represent
# the migration backlog.  Do NOT add new entries; migrate instead.
# To retire an entry, replace register_key() with typed Ports and remove it.
# ---------------------------------------------------------------------------
AUDITED_SITES: list[tuple[str, str]] = sorted([])

_BEHAVIORS_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"


_NON_PORTS_BASES = {"DataLayerAction", "DataLayerCondition"}


def _base_names(cls_node: ast.ClassDef) -> set[str]:
    """Return the simple names of *cls_node*'s bases (``a.B`` -> ``B``)."""
    names: set[str] = set()
    for base in cls_node.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def _setup_calls_register_key(cls_node: ast.ClassDef) -> bool:
    """Whether *cls_node*'s ``setup()`` method calls ``register_key()``."""
    return any(
        isinstance(stmt, ast.Call)
        and isinstance(stmt.func, ast.Attribute)
        and stmt.func.attr == "register_key"
        for item in cls_node.body
        if isinstance(item, ast.FunctionDef) and item.name == "setup"
        for stmt in ast.walk(item)
    )


def _collect_sites() -> list[tuple[str, str]]:
    """Return sorted (rel_path, class_name) for non-WithPorts DataLayer*
    subclasses whose setup() method calls register_key()."""
    found: list[tuple[str, str]] = []
    for path, tree in _corpus.files_mentioning(
        "register_key",
        "DataLayerAction",
        "DataLayerCondition",
        under=_BEHAVIORS_ROOT,
    ):
        for cls_node in ast.walk(tree):
            if (
                isinstance(cls_node, ast.ClassDef)
                and _base_names(cls_node) & _NON_PORTS_BASES
                and _setup_calls_register_key(cls_node)
            ):
                rel = str(path.relative_to(_BEHAVIORS_ROOT)).replace("\\", "/")
                found.append((rel, cls_node.name))
    return sorted(found)


def test_no_new_bare_register_key_datalayer_nodes() -> None:
    """No new non-WithPorts DataLayer* nodes with register_key() in setup().

    A NEW entry (a class added with the legacy pattern) fails this test
    immediately — migrate to typed Ports instead.  A REMOVED entry means a
    node was successfully migrated — remove it from AUDITED_SITES to keep the
    ratchet tight.
    """
    actual = _collect_sites()
    actual_counts = Counter(actual)
    expected_counts = Counter(AUDITED_SITES)

    new_sites = actual_counts - expected_counts
    removed_sites = expected_counts - actual_counts

    messages: list[str] = []
    if new_sites:
        messages.append(
            "NEW non-WithPorts DataLayer* nodes with register_key() found —"
            " migrate to typed Ports (BehaviourWithPorts / DataLayerConditionWithPorts /"
            " DataLayerActionWithPorts) or add a justified exemption:\n"
            + "\n".join(
                f"  + {path!r}  {cls}" for path, cls in sorted(new_sites)
            )
        )
    if removed_sites:
        messages.append(
            "Nodes in AUDITED_SITES were migrated away from register_key()"
            " — remove them from the baseline to keep the ratchet tight:\n"
            + "\n".join(
                f"  - {path!r}  {cls}" for path, cls in sorted(removed_sites)
            )
        )
    assert not messages, "\n\n".join(messages)
