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

"""Architecture ratchet: every outbox drain runs under the actor's drain lock.

``outbox_handler`` is called from three places — the inbox background task,
the legacy inbox handler and the ``OutboxMonitor`` — and before ADR-0112 those
calls drained one FIFO concurrently, which is how a ledger fan-out reached a
replica scrambled (#3602).  OX-01-004 now requires one drain per actor outbox
at a time, and ``outbox_handler`` is the only entry that takes the lock.

The ratchet therefore pins two structural facts:

1. Nothing under ``vultron/`` other than ``outbox_handler.py`` calls the
   unlocked inner drain (``_drain_outbox``) or the per-row delivery
   (``handle_outbox_item``); a new caller must go through ``outbox_handler``.
2. Inside ``outbox_handler.py`` the inner drain is called exactly once, from
   ``outbox_handler``, after ``_drain_slot`` and inside a ``try`` whose
   ``finally`` clears the slot's ``busy`` flag.

Spec: OX-01-004 (``specs/outbox.yaml``).  ADR-0112.
"""

import ast

import pytest

from test.architecture import _corpus

_VULTRON = _corpus.REPO_ROOT / "vultron"
_HANDLER = _VULTRON / "adapters" / "driving" / "fastapi" / "outbox_handler.py"

_INNER_NAMES = ("_drain_outbox", "handle_outbox_item")
_SLOT_FACTORY = "_drain_slot"


def _callee(call: ast.Call) -> str:
    fn = call.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return getattr(fn, "id", "")


def _calls_named(tree: ast.AST, name: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _callee(node) == name
    ]


@pytest.mark.spec("OX-01-004")
@pytest.mark.parametrize("inner", _INNER_NAMES)
def test_inner_drain_is_called_only_from_outbox_handler_module(
    inner: str,
) -> None:
    """A drain that bypasses ``outbox_handler`` bypasses the lock."""
    offenders: list[str] = []
    for path, tree in _corpus.files_mentioning(inner, under=_VULTRON):
        if path == _HANDLER:
            continue
        if _calls_named(tree, inner):
            offenders.append(str(path.relative_to(_corpus.REPO_ROOT)))
    assert not offenders, (
        f"{inner}() is called outside outbox_handler.py in {offenders};"
        " every drain must enter through outbox_handler(), which takes the"
        " per-actor drain lock (OX-01-004, ADR-0112)."
    )


def _function(tree: ast.AST, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"async def {name} not found in outbox_handler.py")


def _handler_tree() -> ast.AST:
    """The AST of ``outbox_handler.py`` from the shared corpus (TB-13-001)."""
    for path, tree in _corpus.files_mentioning(
        "def outbox_handler(", under=_VULTRON
    ):
        if path == _HANDLER:
            return tree
    raise AssertionError(f"{_HANDLER} is not in the architecture corpus")


def _clears_busy(stmts: list[ast.stmt]) -> bool:
    return any(
        isinstance(st, ast.Assign)
        and any(
            isinstance(t, ast.Attribute) and t.attr == "busy"
            for t in st.targets
        )
        and isinstance(st.value, ast.Constant)
        and st.value.value is False
        for st in stmts
    )


@pytest.mark.spec("OX-01-004")
def test_outbox_handler_drains_inside_the_busy_slot() -> None:
    """The one ``_drain_outbox`` call runs with the slot busy and always clears it.

    The slot is a flag, not a lock — a caller that finds it set returns and
    asks the running drain to look again — so the property to pin is that the
    drain is entered only through ``outbox_handler``, after ``_drain_slot``,
    inside a ``try`` whose ``finally`` sets ``slot.busy = False``.
    """
    tree = _handler_tree()
    drains = _calls_named(tree, "_drain_outbox")
    assert len(drains) == 1, (
        f"expected exactly one _drain_outbox() call in outbox_handler.py,"
        f" found {len(drains)}"
    )
    handler = _function(tree, "outbox_handler")
    assert _calls_named(handler, _SLOT_FACTORY), (
        f"outbox_handler() must obtain its drain slot via {_SLOT_FACTORY}()"
    )
    enclosing_try = [
        node
        for node in ast.walk(handler)
        if isinstance(node, ast.Try)
        and any(
            n is drains[0]
            for body_stmt in node.body
            for n in ast.walk(body_stmt)
        )
    ]
    assert enclosing_try and _clears_busy(enclosing_try[0].finalbody), (
        "_drain_outbox() must be called inside a try whose finally clears"
        " `slot.busy` (OX-01-004, ADR-0112)"
    )
