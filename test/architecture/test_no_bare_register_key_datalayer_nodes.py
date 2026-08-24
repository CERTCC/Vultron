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
import pathlib
from collections import Counter

# ---------------------------------------------------------------------------
# Audited baseline — (path_relative_to_behaviors_root, class_name)
#
# Each entry is a DataLayerAction or DataLayerCondition (non-WithPorts)
# subclass that still calls register_key() in setup().  These represent
# the migration backlog.  Do NOT add new entries; migrate instead.
# To retire an entry, replace register_key() with typed Ports and remove it.
# ---------------------------------------------------------------------------
AUDITED_SITES: list[tuple[str, str]] = sorted([])


def _collect_sites() -> list[tuple[str, str]]:  # noqa: C901
    """Return sorted (rel_path, class_name) for non-WithPorts DataLayer*
    subclasses whose setup() method calls register_key()."""
    non_ports_bases = {"DataLayerAction", "DataLayerCondition"}
    root = pathlib.Path("vultron/core/behaviors")
    found: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:  # pragma: no cover
            continue
        for cls_node in ast.walk(tree):
            if not isinstance(cls_node, ast.ClassDef):
                continue
            base_names: set[str] = set()
            for base in cls_node.bases:
                if isinstance(base, ast.Name):
                    base_names.add(base.id)
                elif isinstance(base, ast.Attribute):
                    base_names.add(base.attr)
            if not (base_names & non_ports_bases):
                continue
            # Scan the setup() method for register_key calls.
            has_register_key = False
            for item in cls_node.body:
                if not (
                    isinstance(item, ast.FunctionDef) and item.name == "setup"
                ):
                    continue
                for stmt in ast.walk(item):
                    if not isinstance(stmt, ast.Call):
                        continue
                    func = stmt.func
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr == "register_key"
                    ):
                        has_register_key = True
                        break
                if has_register_key:
                    break
            if has_register_key:
                rel = str(path.relative_to(root)).replace("\\", "/")
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
