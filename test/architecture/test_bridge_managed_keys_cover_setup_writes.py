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

"""Every key ``setup_tree`` registers must be restored by ``execute_with_setup``.

BT-17-007.  The same defect landed twice: `activity` and the `**context_data`
keys were outside ``managed_keys`` (#3161), and so was `actor_id` (#3516). Both
times a key that ``setup_tree`` writes outlived the execution that wrote it,
and both times the omission was invisible — nothing connects the two lists, so
adding a blackboard write to ``setup_tree`` and forgetting ``managed_keys`` is a
silent one-line mistake.

This closes that loop statically. ``setup_tree``'s literal
``register_key(key="X")`` calls are the complete set of keys it writes by name;
the ``**context_data`` keys go through a ``setattr`` loop and are added to
``managed_keys`` dynamically, so they are deliberately out of scope here and are
covered by the nested-execution tests in
``test/core/behaviors/test_bridge.py``.

Why a ratchet rather than a runtime assertion: the omission is only observable
when a *nested* execution reuses the key, which no single unit test of
``setup_tree`` would exercise.
"""

import ast

from test.architecture import _corpus

_BRIDGE = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "bridge.py"


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {_BRIDGE}")


def _registered_keys(fn: ast.FunctionDef) -> set[str]:
    """Literal ``key=`` arguments to ``register_key`` calls within *fn*."""
    keys: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (
            isinstance(func, ast.Attribute) and func.attr == "register_key"
        ):
            continue
        for kw in node.keywords:
            if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                if isinstance(kw.value.value, str):
                    keys.add(kw.value.value)
    return keys


def _string_elements(value: ast.expr) -> set[str]:
    """String literals directly in a list display, ignoring any unpacking.

    ``*context_data.keys()`` is not statically enumerable and is deliberately
    skipped — those keys are covered by the nested-execution tests.
    """
    if not isinstance(value, ast.List):
        raise AssertionError(
            "managed_keys is no longer built from list literals;"
            " update this ratchet"
        )
    return {
        elt.value
        for elt in value.elts
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
    }


def _managed_keys(fn: ast.FunctionDef) -> set[str]:
    """String literals assigned or appended to ``managed_keys`` within *fn*.

    Covers both the ``managed_keys = [...]`` literal and any
    ``managed_keys += [...]`` extension, so moving a key between the two does
    not change the answer.
    """
    keys: set[str] = set()
    found = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "managed_keys" not in names:
                continue
        elif isinstance(node, ast.AugAssign):
            target = node.target
            if not (
                isinstance(target, ast.Name) and target.id == "managed_keys"
            ):
                continue
        else:
            continue
        keys |= _string_elements(node.value)
        found = True
    if not found:
        raise AssertionError("no managed_keys assignment found")
    return keys


def _bridge_tree() -> ast.Module:
    """Return the cached AST for ``bridge.py`` (TB-13-002, TB-13-003)."""
    for path, tree in _corpus.all_trees(_BRIDGE.parent):
        if path == _BRIDGE and isinstance(tree, ast.Module):
            return tree
    raise AssertionError(f"{_BRIDGE} not in the shared corpus")


def test_managed_keys_covers_every_key_setup_tree_registers() -> None:
    """BT-17-007: no key `setup_tree` writes may outlive its execution."""
    tree = _bridge_tree()
    registered = _registered_keys(_function(tree, "setup_tree"))
    managed = _managed_keys(_function(tree, "execute_with_setup"))

    # Guard against a vacuous pass if either extractor stops matching.
    assert "datalayer" in registered
    assert "actor_id" in registered
    assert len(registered) >= 7

    missing = registered - managed
    assert not missing, (
        "setup_tree registers blackboard key(s) that execute_with_setup does"
        f" not restore: {sorted(missing)}.\n\n"
        "Blackboard.storage is process-global and execute_with_setup is"
        " re-entrant, so a nested call that writes one of these overwrites the"
        " outer execution's value and never puts it back — the outer tree then"
        " finishes its ticks against the inner call's value (#3161, #3516)."
        " Add the key to managed_keys, or, if it genuinely must survive the"
        " execution, record why here and in BT-17-007."
    )
