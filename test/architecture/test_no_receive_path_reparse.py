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

_VALIDATORS = frozenset({"model_validate", "model_validate_json"})

#: Local names that hold the raw request body, or a piece of it.
_RAW_BODY_NAMES = frozenset(
    {"body", "payload", "raw_body", "raw_obj", "request_body"}
)


def _is_raw(node: ast.AST, tainted: set[str]) -> bool:
    """Whether *node* reads the received evidence or a raw-body name."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and (
            sub.id in _RAW_BODY_NAMES
            or sub.id in tainted
            or "received_evidence" in sub.id
        ):
            return True
        if isinstance(sub, ast.Attribute) and "received_evidence" in sub.attr:
            return True
    return False


def _offending_calls(tree: ast.AST) -> list[int]:
    """Return the line of every ``model_validate`` fed from the raw body."""
    offenders: list[int] = []
    # The module itself (its top-level statements) and each function on its
    # own, so a name tainted in one function does not taint another's.
    scopes: list[ast.AST] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    for scope in scopes:
        tainted: set[str] = set()
        # ``ast.walk`` is breadth-first; sort by position so an assignment is
        # seen before the call that reads the name it binds.
        nodes = sorted(
            (n for n in ast.walk(scope) if hasattr(n, "lineno")),
            key=lambda n: (
                getattr(n, "lineno", 0),
                getattr(n, "col_offset", 0),
            ),
        )
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value:
                if _is_raw(node.value, tainted):
                    targets = (
                        node.targets
                        if isinstance(node, ast.Assign)
                        else [node.target]
                    )
                    for target in targets:
                        tainted.update(
                            n.id
                            for n in ast.walk(target)
                            if isinstance(n, ast.Name)
                        )
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _VALIDATORS
                and any(
                    _is_raw(arg, tainted)
                    for arg in [*node.args, *(k.value for k in node.keywords)]
                )
            ):
                offenders.append(node.lineno)
    return sorted(set(offenders))


@pytest.mark.spec("MV-11-005")
def test_receive_path_never_revalidates_the_raw_body() -> None:
    """No receive-path module re-parses an inline object from the raw body."""
    offenders: list[str] = []
    for root in _RECEIVE_PATH:
        for path, tree in _corpus.files_mentioning(*_VALIDATORS, under=root):
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
    ],
)
def test_detector_catches_every_raw_body_shape(source: str) -> None:
    """The ratchet is not vacuous: each known shape is caught."""
    assert _offending_calls(_corpus.parse_inline(source)) != []


def test_detector_allows_validating_a_parsed_object() -> None:
    """Validating something other than the raw body is not an offence."""
    source = (
        "def f(activity):\n"
        "    raw = dehydrate(activity.model_dump(by_alias=True))\n"
        "    return C.model_validate(raw)\n"
    )
    assert _offending_calls(_corpus.parse_inline(source)) == []
