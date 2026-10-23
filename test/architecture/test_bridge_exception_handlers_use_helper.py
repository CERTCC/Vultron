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

"""Every classifying handler in ``bridge.py`` builds its result via one helper.

CS-22-001.  #3080 was a log-level divergence between two of ``BTBridge``'s
near-identical exception handlers, invisible to a reader comparing them because
nothing said the difference was accidental.  ``BTBridge._exception_result``
collapsed all six classifying handlers onto one input so the divergence is not
expressible — but "not expressible" is only true while every handler actually
goes through it, and nothing checked that.

``test_no_broad_except_outside_bt_update.py`` does not cover this: it counts only
``except Exception``/``BaseException``/bare handlers, so it pins three of the six
and is blind to the three ``except VultronError`` handlers.  A new or edited
``except VultronError`` block that built a ``BTExecutionResult`` inline — with
its own message format or its own log level — would pass every check in the
suite, which is precisely how #3080 happened the first time.

This ratchet closes that gap: any handler in ``bridge.py`` that returns a value
must return ``self._exception_result(...)``.  The one handler that returns
nothing is the ``bt.shutdown()`` guard in ``execute_tree``'s ``finally``, whose
job is to preserve the result a classified handler already returned; it is
allowed precisely because it builds none.

Spec: CS-22-001 (``specs/code-style.yaml``); BT-17 (``BTExecutionResult``
classification).  See ``notes/bt-pitfalls.md`` § "Every Classifying Exception
Handler Is One Helper" and ``notes/architecture-ratchet-corpus.md`` for the
corpus pattern.
"""

import ast

from test.architecture import _corpus

_BRIDGE = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors" / "bridge.py"

_HELPER = "_exception_result"


def _bridge_tree() -> ast.Module:
    """Return the cached AST for ``bridge.py`` (TB-13-002, TB-13-003)."""
    for path, tree in _corpus.all_trees(_BRIDGE.parent):
        if path == _BRIDGE and isinstance(tree, ast.Module):
            return tree
    raise AssertionError(f"{_BRIDGE} not in the shared corpus")


def _handlers(tree: ast.Module) -> list[ast.ExceptHandler]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]


def _returned_values(handler: ast.ExceptHandler) -> list[ast.expr]:
    """Non-bare ``return`` expressions lexically owned by *handler*.

    A ``return`` inside a function defined within the handler belongs to that
    function, not to the handler, so nested definitions are not descended into.
    """
    found: list[ast.expr] = []

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(child, ast.Return) and child.value is not None:
                found.append(child.value)
            visit(child)

    for stmt in handler.body:
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            found.append(stmt.value)
        else:
            visit(stmt)
    return found


def _is_helper_call(value: ast.expr) -> bool:
    """True if *value* is ``self._exception_result(...)``."""
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and value.func.attr == _HELPER
    )


def test_every_returning_handler_routes_through_the_helper() -> None:
    """CS-22-001: one helper owns message, log level and internal_error."""
    tree = _bridge_tree()
    handlers = _handlers(tree)

    # Guard against a vacuous pass if the extractor stops matching: the module
    # is known to carry six classifying handlers plus the shutdown guard.
    assert len(handlers) >= 7, (
        f"expected at least 7 except handlers in {_BRIDGE.name}, found"
        f" {len(handlers)} — has the extractor stopped matching?"
    )

    offenders: list[str] = []
    routed = 0
    for handler in handlers:
        for value in _returned_values(handler):
            if _is_helper_call(value):
                routed += 1
            else:
                exc = ast.unparse(handler.type) if handler.type else "bare"
                offenders.append(
                    f"line {handler.lineno} (except {exc}) returns"
                    f" {ast.unparse(value)[:70]}"
                )

    assert not offenders, (
        "exception handler(s) in bridge.py build a result without going through"
        f" BTBridge.{_HELPER}:\n  " + "\n  ".join(offenders) + "\n\n"
        "The message text, the log level and the internal_error flag must all"
        " derive from one input, or they drift apart: #3080 was exactly that"
        " divergence between two of these handlers (CS-22-001).  Call"
        f" self.{_HELPER}(e, prefix=..., internal_error=...) instead of"
        " constructing BTExecutionResult here."
    )

    assert routed >= 6, (
        f"only {routed} handler(s) route through {_HELPER}; expected at least"
        " 6 (setup and execution phases, each split by VultronError vs."
        " Exception, plus the tick handlers in execute_tree).  A drop means a"
        " classifying handler was removed rather than re-routed."
    )


def test_the_shutdown_guard_is_the_only_handler_that_returns_nothing() -> None:
    """The exemption is narrow and stays narrow.

    ``execute_tree``'s ``finally`` catches around ``bt.shutdown()`` so a
    teardown error cannot replace the classified result already returned.  That
    is the *only* reason a handler here may skip the helper, so assert there is
    exactly one such handler rather than leaving the exemption open-ended.
    """
    tree = _bridge_tree()
    silent = [h for h in _handlers(tree) if not _returned_values(h)]

    assert len(silent) == 1, (
        "expected exactly one non-returning except handler in bridge.py (the"
        " bt.shutdown() guard in execute_tree's finally), found"
        f" {len(silent)} at line(s) {sorted(h.lineno for h in silent)}.\n\n"
        "A handler that swallows an exception without returning a classified"
        " result is only defensible when it has no result to build.  If a new"
        " one is genuinely needed, say why here."
    )
