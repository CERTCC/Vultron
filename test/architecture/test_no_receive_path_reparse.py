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
"""Architecture ratchet: the receive path never re-parses the raw body (MV-11-005).

After ``parse_activity`` returns, the parsed object graph is the authority for
what arrived in each slot.  The raw request body is received evidence
(VM-08-002), kept for audit, not a second source to parse from.  The retired
``inbox_storage._reparse_as_specific_type`` re-validated an inline object from
the raw body; once the parse edge set unknown keys aside (MV-11-003), that
re-parse met them again on a core class, failed ``extra="forbid"``, and stored
a less specific type in silence (#3922).

This ratchet walks every module under ``vultron/adapters/driving/`` and
``vultron/core/`` and fails on any ``model_validate``/``model_validate_json``
call whose argument is built from the received evidence or from a raw-body
variable (``body``, ``payload``, ``raw_body``, ``raw_obj``, ``request_body``;
``payload`` is what the inbox pipeline calls it) — directly or
through a local name assigned from one.  There is no exemption list.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_ROOT = _corpus.REPO_ROOT

#: The receive path MV-11-005 governs.
_RECEIVE_PATH = (
    _ROOT / "vultron" / "adapters" / "driving",
    _ROOT / "vultron" / "core",
)

#: Calls that validate a mapping into a model.  ``TypeAdapter`` spells it
#: ``validate_python``/``validate_json``; a ``**``-splat into a constructor is
#: the same validation by another name and is checked separately.
_VALIDATORS = frozenset(
    {
        "model_validate",
        "model_validate_json",
        "validate_python",
        "validate_json",
    }
)

#: Local names that hold the raw request body, or a piece of it.  A name on
#: this list stops being raw once the scope rebinds it to something else
#: (``payload = activity.model_dump()``), so a reused name is not a false hit.
_RAW_BODY_NAMES = frozenset(
    {"body", "payload", "raw_body", "raw_obj", "request_body"}
)


def _self_attr(node: ast.AST) -> str | None:
    """``"self.x"`` for a ``self.x`` expression, else ``None``."""
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    ):
        return f"self.{node.attr}"
    return None


class _Taint:
    """Which names in one scope hold the raw body or the received evidence."""

    def __init__(self, raw_attrs: set[str]) -> None:
        self.tainted: set[str] = set()
        self.cleaned: set[str] = set()
        self.raw_attrs = raw_attrs

    def is_raw(self, node: ast.AST) -> bool:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and (
                (sub.id in _RAW_BODY_NAMES and sub.id not in self.cleaned)
                or sub.id in self.tainted
                or "received_evidence" in sub.id
            ):
                return True
            if isinstance(sub, ast.Attribute) and (
                "received_evidence" in sub.attr
                or _self_attr(sub) in self.raw_attrs
            ):
                return True
        return False

    def bind(self, target: ast.AST, value_is_raw: bool) -> None:
        names = [n.id for n in ast.walk(target) if isinstance(n, ast.Name)]
        if value_is_raw:
            self.tainted.update(names)
            self.cleaned.difference_update(names)
        else:
            self.tainted.difference_update(names)
            self.cleaned.update(n for n in names if n in _RAW_BODY_NAMES)


def _bindings(node: ast.AST) -> list[tuple[ast.AST, ast.AST]]:
    """The ``(target, value)`` pairs a statement or expression binds."""
    if isinstance(node, ast.Assign):
        return [(target, node.value) for target in node.targets]
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value:
        return [(node.target, node.value)]
    if isinstance(node, ast.NamedExpr):
        return [(node.target, node.value)]
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [(node.target, node.iter)]
    if isinstance(
        node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
    ):
        # Bound at the comprehension itself, which sorts ahead of its element
        # expression — the element is written before the ``for`` it reads.
        return [(gen.target, gen.iter) for gen in node.generators]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [
            (item.optional_vars, item.context_expr)
            for item in node.items
            if item.optional_vars is not None
        ]
    return []


def _is_validation_of_raw(node: ast.AST, taint: _Taint) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute) and node.func.attr in _VALIDATORS:
        return any(
            taint.is_raw(arg)
            for arg in [*node.args, *(k.value for k in node.keywords)]
        )
    # ``C(**raw)``: a constructor fed the raw mapping validates it just the same.
    return any(k.arg is None and taint.is_raw(k.value) for k in node.keywords)


def _raw_self_attrs(tree: ast.AST) -> set[str]:
    """Every ``self.x`` the module binds from a raw-body name.

    Module-wide rather than per function: the pre-#3922 shape stored the body
    in ``__init__`` (``self._body = body``) and read it in another method.
    """
    taint = _Taint(set())
    return {
        attr
        for node in ast.walk(tree)
        for target, value in _bindings(node)
        if (attr := _self_attr(target)) is not None and taint.is_raw(value)
    }


def _position(node: ast.AST) -> tuple[int, int]:
    """Source position, for ordering bindings ahead of the reads they feed."""
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))


def _offending_calls(tree: ast.AST) -> list[int]:
    """Return the line of every validation fed from the raw body."""
    offenders: list[int] = []
    raw_attrs = _raw_self_attrs(tree)
    # The module itself (its top-level statements) and each function on its
    # own, so a name tainted in one function does not taint another's.
    scopes: list[ast.AST] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    for scope in scopes:
        taint = _Taint(raw_attrs)
        # ``ast.walk`` is breadth-first; sort by position so a binding is seen
        # before the call that reads the name it binds.
        nodes = sorted(
            (n for n in ast.walk(scope) if hasattr(n, "lineno")),
            key=_position,
        )
        for node in nodes:
            for target, value in _bindings(node):
                taint.bind(target, taint.is_raw(value))
            if _is_validation_of_raw(node, taint):
                offenders.append(_position(node)[0])
    return sorted(set(offenders))


@pytest.mark.spec("MV-11-005")
def test_receive_path_never_revalidates_the_raw_body() -> None:
    """No receive-path module re-parses an inline object from the raw body."""
    offenders: list[str] = []
    for root in _RECEIVE_PATH:
        for path, tree in _corpus.files_mentioning(
            *_VALIDATORS, "**", under=root
        ):
            offenders.extend(
                f"{Path(path).relative_to(_ROOT)}:{line}"
                for line in _offending_calls(tree)
            )
    assert offenders == [], (
        "the receive path re-validates from the raw request body or the "
        "received evidence; the parsed object is the authority after "
        f"parse_activity (MV-11-005, #3922): {offenders}"
    )


@pytest.mark.parametrize(
    "source",
    [
        # The retired shape itself.
        "def f(nested, raw_obj):\n    return C.model_validate(raw_obj)\n",
        # A slot pulled out of the body inline.
        "def f(body):\n    return C.model_validate(body.get('object'))\n",
        # The same, through a local name.
        "def f(body):\n    raw = body['object']\n    return C.model_validate(raw)\n",
        # The received evidence, by attribute or by JSON text.
        "def f(a):\n    return C.model_validate(a.received_evidence['object'])\n",
        "def f(a):\n    return C.model_validate_json(a.received_evidence_json)\n",
        # Loop, walrus and context-manager targets carry the taint too.
        "def f(body):\n    for item in body['items']:\n        C.model_validate(item)\n",
        "def f(body):\n    if (raw := body.get('object')):\n        C.model_validate(raw)\n",
        "def f(body):\n    with hold(body) as raw:\n        C.model_validate(raw)\n",
        "def f(body):\n    return [C.model_validate(x) for x in body['items']]\n",
        # The pre-#3922 adapter shape: stored on self in one method, read in another.
        "class A:\n    def __init__(self, body):\n        self._raw = body\n"
        "    def parse(self):\n        return C.model_validate(self._raw['object'])\n",
        # TypeAdapter spellings, and a constructor splat.
        "def f(body):\n    return TypeAdapter(C).validate_python(body['object'])\n",
        "def f(body):\n    return C(**body['object'])\n",
    ],
)
def test_detector_catches_every_raw_body_shape(source: str) -> None:
    """The ratchet is not vacuous: each known shape is caught."""
    assert _offending_calls(_corpus.parse_inline(source)) != []


@pytest.mark.parametrize(
    "source",
    [
        "def f(activity):\n"
        "    raw = dehydrate(activity.model_dump(by_alias=True))\n"
        "    return C.model_validate(raw)\n",
        # A raw-body *name* rebound to a parsed object's dump is not raw.
        "def f(activity):\n"
        "    payload = activity.model_dump(by_alias=True)\n"
        "    return C.model_validate(payload)\n",
    ],
)
def test_detector_allows_validating_a_parsed_object(source: str) -> None:
    """Validating something other than the raw body is not an offence."""
    assert _offending_calls(_corpus.parse_inline(source)) == []
