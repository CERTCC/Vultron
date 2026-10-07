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

"""Derive, from code, the ledger ``event_type`` values the CASE_MANAGER commits.

Companion to ``test_ledger_event_types_are_replayed.py`` (RSH-08-004).  Two
paths commit an entry:

* **The receive-side commit.**  ``CommitCaseLedgerEntryNode`` records the
  received activity under its ``MessageSemantics`` value.  A received use case
  reaches it when a tree factory it calls — directly or through further
  ``vultron.core`` functions — passes ``create_receive_activity_tree`` a
  ``case_id`` that is not the literal ``None`` (CLP-10-013), or builds the
  commit node or guarded-commit subtree itself.  :func:`received_commit_semantics`
  follows those calls from every routed use case's methods.
* **Explicit commits.**  A node that commits an entry of its own passes
  ``event_type=`` to the commit tree; :func:`explicit_event_types` collects
  every such keyword whose value is a string literal or a module-level
  constant, plus every module- or class-level constant named ``*EVENT_TYPE``
  under ``vultron/core``.  A value threaded through a parameter
  (``event_type=event_type``) is found at the call that supplies it.

Not covered, by design: the ``sync-log-entry`` trigger
(``vultron/core/use_cases/triggers/sync_log_entry.py``), an operator tool
whose client names the event type of an ``Announce(VulnerabilityCase)``
snapshot.  No trees from ``_corpus`` here are parsed twice (TB-13-003); source
reached through ``inspect`` goes through ``_corpus.parse_inline``.
"""

import ast
import importlib
import inspect
import textwrap
from collections.abc import Callable, Iterator
from types import ModuleType
from typing import Any

from test.architecture import _corpus
from vultron.semantic_registry import use_case_map

_RECEIVE_FACTORY = "create_receive_activity_tree"
#: Building either of these commits the received activity whatever the case id.
_COMMIT_BUILDERS = frozenset(
    {
        "CommitCaseLedgerEntryNode",
        "create_guarded_commit_case_ledger_entry_tree",
    }
)
_CORE_ROOT = _corpus.REPO_ROOT / "vultron" / "core"
_MAX_DEPTH = 8


def _callee_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _resolve(name: str, module: ModuleType) -> Any:
    """Resolve *name* as *module* sees it, or through a module it imported."""
    found = getattr(module, name, None)
    if found is not None:
        return found
    for value in vars(module).values():
        if inspect.ismodule(value) and hasattr(value, name):
            return getattr(value, name)
    return None


def _commits(fn: Callable[..., Any], seen: set[Any], depth: int = 0) -> bool:
    """True when *fn*, or a ``vultron.core`` function it calls, commits."""
    if fn in seen or depth > _MAX_DEPTH:
        return False
    seen.add(fn)
    try:
        source = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return False
    module = inspect.getmodule(fn)
    assert module is not None
    calls = [
        node
        for node in ast.walk(_corpus.parse_inline(source))
        if isinstance(node, ast.Call) and _callee_name(node) is not None
    ]
    return any(_call_commits(call, module, seen, depth) for call in calls)


def _passes_a_case_id(call: ast.Call) -> bool:
    """True unless a ``create_receive_activity_tree`` call passes ``None``."""
    case_id = next(
        (kw.value for kw in call.keywords if kw.arg == "case_id"),
        call.args[1] if len(call.args) > 1 else None,
    )
    return not (isinstance(case_id, ast.Constant) and case_id.value is None)


def _call_commits(
    call: ast.Call, module: ModuleType, seen: set[Any], depth: int
) -> bool:
    """True when *call* commits, directly or through the function it names."""
    name = _callee_name(call)
    assert name is not None
    if name in _COMMIT_BUILDERS:
        return True
    if name == _RECEIVE_FACTORY:
        return _passes_a_case_id(call)
    target = _resolve(name, module)
    if inspect.isclass(target):
        target = getattr(target, "__init__", None)
    return (
        inspect.isfunction(target)
        and target.__module__.startswith("vultron.core")
        and _commits(target, seen, depth + 1)
    )


def received_commit_semantics() -> set[str]:
    """``MessageSemantics`` values a received use case commits as an entry."""
    committed: set[str] = set()
    for semantic, use_case in use_case_map().items():
        seen: set[Any] = set()
        if any(
            # Inherited methods too: a shared base class may build the tree.
            _commits(member, seen)
            for _, member in inspect.getmembers(use_case, inspect.isfunction)
        ):
            committed.add(semantic.value)
    return committed


def _module_name(path: Any) -> str:
    rel = path.relative_to(_corpus.REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _constant_value(expr: ast.expr, module: ModuleType) -> str | None:
    """The string *expr* names, when it is a literal or a module constant."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        value = getattr(module, expr.id, None)
        return value if isinstance(value, str) else None
    return None


def _event_type_constants(tree: ast.AST) -> Iterator[tuple[str | None, str]]:
    """``(class name or None, constant name)`` for each ``*EVENT_TYPE``."""
    scopes: list[tuple[str | None, list[ast.stmt]]] = [
        (None, getattr(tree, "body", []))
    ]
    scopes += [
        (node.name, node.body)
        for node in getattr(tree, "body", [])
        if isinstance(node, ast.ClassDef)
    ]
    for owner, body in scopes:
        for stmt in body:
            targets = (
                stmt.targets
                if isinstance(stmt, ast.Assign)
                else [stmt.target]
                if isinstance(stmt, ast.AnnAssign)
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id.endswith(
                    "EVENT_TYPE"
                ):
                    yield owner, target.id


def explicit_event_types() -> set[str]:
    """Event types a ``vultron.core`` node passes to a commit of its own."""
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning("EVENT_TYPE", under=_CORE_ROOT):
        module = importlib.import_module(_module_name(path))
        for owner, name in _event_type_constants(tree):
            holder = getattr(module, owner) if owner else module
            value = getattr(holder, name, None)
            if isinstance(value, str):
                found.add(value)
    for path, tree in _corpus.files_mentioning(
        "event_type=", under=_CORE_ROOT
    ):
        module = importlib.import_module(_module_name(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg != "event_type":
                    continue
                value = _constant_value(kw.value, module)
                if value is not None:
                    found.add(value)
    return found


def committed_event_types() -> set[str]:
    """Every ``event_type`` the code base can commit to a case ledger."""
    return received_commit_semantics() | explicit_event_types()
