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
"""No received handler's post-run reader decides a refusal (ADR-0195, #6494).

A received use case hands its tree to the runner with an optional reader
(:data:`~vultron.core.behaviors.case.received_run.reading.OutcomeReader`), a
function of the finished run.  A reader that returns
``HandlerResult.refused(...)`` decides a verdict outside the tree.  A refused
run is the failing node's to declare instead
(:class:`~vultron.core.behaviors.idempotency.ReportsRefusal`), and the runner
reads that declaration (HP-01-003).

A *reader* here is any function under ``vultron/core/use_cases/received/``
that takes a ``ReceivedOutcome`` or is passed as ``reader=``, together with
the functions it is nested in (a factory whose refusal the reader returns)
and the same-module functions any of these calls.  An entry is
``path::qualified.name``, and it counts the refusals
(``HandlerResult.refused(...)``, or a ``HandlerResult`` built ``REFUSED``) in
that function's own body.  The shared readers in
``vultron/core/behaviors/case/received_run/readers.py`` are outside the scan.

The set is exact.  A new reader refusal fails, and so does a listed one that
is gone, so the list holds only the readings that still refuse.
"""

import ast
from collections.abc import Iterator

import pytest

from test.architecture import _corpus
from test.architecture._use_case_call_graph import RECEIVED_ROOT

#: Readings that stay, each for the reason its value gives (#6494 AC-1).
# permanent: #6494 (each reading refuses a run no node declaration can state)
KNOWN_READER_REFUSALS: dict[str, tuple[int, str]] = {
    "case_proposal/create.py::_admission_arm_reader.read": (
        2,
        "the decline arms succeed: they record the decline and queue its"
        " Reject, so no node fails, and a declared refusal is read only"
        " on a failed run",
    ),
    "embargo/invite.py::_fault_reader.read": (
        1,
        "the fault tree succeeds: it records the Invite and sends the"
        " fault as its effect, so there is no failed node to declare",
    ),
    "embargo/invite.py::_refusal_reader.read": (
        1,
        "adds to the shared P/X/A diversion reading whether a Reject was"
        " sent, which an effect inside the diversion decides",
    ),
    "sync/announce.py::_held_or_not_manager": (
        1,
        "rewords the composed sender guard's refusal with the announced"
        " entry; the guard is shared by every received tree and states"
        " its own reason",
    ),
    "unknown.py::UnresolvableObjectUseCase.execute": (
        1,
        "the dead-letter tree succeeds: storing the receiver's own"
        " diagnostic record is its whole work, so no node fails, and the"
        " activity it could not resolve is still refused (SE-04-007)",
    ),
}

#: Reader refusals another issue removes, with their counts.
# owner: #6499
_MOVED_EXEMPTIONS: dict[str, int] = {
    "fault/responses.py::_unnamed_entry_refusal": 1,
    "fault/responses.py::_reseed_verdict.read": 1,
}

_Function = ast.FunctionDef | ast.AsyncFunctionDef
_FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _result_names(tree: ast.AST) -> frozenset[str]:
    """The names ``HandlerResult`` goes by in *tree*, aliases included."""
    names = {"HandlerResult"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names |= {
                a.asname
                for a in node.names
                if a.name == "HandlerResult" and a.asname is not None
            }
    return frozenset(names)


def _is_refusal(node: ast.AST, names: frozenset[str]) -> bool:
    """A ``HandlerResult.refused(...)`` call, or a ``REFUSED`` construction."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "refused"
        and isinstance(func.value, ast.Name)
        and func.value.id in names
    ):
        return True
    return (
        isinstance(func, ast.Name)
        and func.id in names
        and any(
            isinstance(v, ast.Attribute) and v.attr == "REFUSED"
            for v in (*node.args, *(k.value for k in node.keywords))
        )
    )


def _own_nodes(fn: _Function) -> Iterator[ast.AST]:
    """The nodes of *fn*'s body, a lambda's included, not a nested def's."""
    stack: list[ast.AST] = [
        n for n in fn.body if not isinstance(n, _FUNCTION_TYPES)
    ]
    while stack:
        node = stack.pop()
        yield node
        stack += [
            c
            for c in ast.iter_child_nodes(node)
            if not isinstance(c, _FUNCTION_TYPES)
        ]


def _functions(tree: ast.AST) -> Iterator[tuple[str, _Function]]:
    """Every function in *tree*, with its dotted qualified name."""

    def walk(node: ast.AST, prefix: str) -> Iterator[tuple[str, _Function]]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, _FUNCTION_TYPES):
                name = f"{prefix}{child.name}"
                yield name, child
                yield from walk(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                yield from walk(child, f"{prefix}{child.name}.")

    yield from walk(tree, "")


def _takes_outcome(fn: _Function) -> bool:
    args = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
    return any(
        a.annotation is not None
        and "ReceivedOutcome" in ast.unparse(a.annotation)
        for a in args
    )


def _scope_of(name: str) -> str:
    return name.rpartition(".")[0]


def _resolve(called: str, caller: str, functions: set[str]) -> str | None:
    """The function *caller* names *called*: in its scopes, innermost first."""
    scope = caller
    while True:
        candidate = f"{scope}.{called}" if scope else called
        if candidate in functions:
            return candidate
        if not scope:
            return None
        scope = _scope_of(scope)


def _called(node: ast.Call, caller: str, functions: set[str]) -> str | None:
    """The same-module function *node* calls, by name or as ``self.x``."""
    func = node.func
    if isinstance(func, ast.Name):
        return _resolve(func.id, caller, functions)
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "self"
    ):
        # A method of the class the caller is defined in.
        scope = caller
        while scope:
            scope = _scope_of(scope)
            if f"{scope}.{func.attr}" in functions:
                return f"{scope}.{func.attr}"
    return None


def _passed_readers(
    name: str, fn: _Function, functions: set[str]
) -> Iterator[str]:
    """The functions *fn* passes as a ``reader=``, and itself for a lambda."""
    for node in _own_nodes(fn):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "reader":
                continue
            for part in ast.walk(kw.value):
                if isinstance(part, ast.Lambda):
                    yield name
                elif isinstance(part, ast.Name) and (
                    found := _resolve(part.id, name, functions)
                ):
                    yield found


def reader_refusals(tree: ast.AST, rel: str) -> dict[str, int]:
    """The refusal count of each reader of module *rel*, and its helpers.

    A reader takes a ``ReceivedOutcome`` or is passed as ``reader=``; a
    ``reader=`` lambda counts toward the function that holds it.  Each
    function a reader is nested in, every function nested in a reader
    factory passed as ``reader=``, and each same-module function any of
    these calls (by name or as ``self.x``) is reached too.
    """
    functions = dict(_functions(tree))
    known = set(functions)
    names = _result_names(tree)
    readers = {name for name, fn in functions.items() if _takes_outcome(fn)}
    for name, fn in functions.items():
        readers |= set(_passed_readers(name, fn, known))
    # A reader nested in a factory may return a refusal the factory built,
    # and a factory passed as reader= holds its reader nested in it.
    reached = set(readers)
    for name in readers:
        parts = name.split(".")
        reached |= {".".join(parts[:i]) for i in range(1, len(parts))} & known
        reached |= {f for f in known if f.startswith(f"{name}.")}
    pending = list(reached)
    while pending:
        caller = pending.pop()
        for node in _own_nodes(functions[caller]):
            if (
                isinstance(node, ast.Call)
                and (target := _called(node, caller, known)) is not None
                and target not in reached
            ):
                reached.add(target)
                pending.append(target)
    found: dict[str, int] = {}
    for name in sorted(reached):
        count = sum(_is_refusal(n, names) for n in _own_nodes(functions[name]))
        if count:
            found[f"{rel}::{name}"] = count
    return found


def _received_reader_refusals() -> dict[str, int]:
    found: dict[str, int] = {}
    for path, tree in _corpus.files_mentioning(
        "ReceivedOutcome", "reader=", under=RECEIVED_ROOT
    ):
        found |= reader_refusals(
            tree, path.relative_to(RECEIVED_ROOT).as_posix()
        )
    return found


@pytest.mark.spec("HP-01-003")
def test_received_readers_return_only_the_listed_refusals() -> None:
    """Every reader refusal is listed with its count, and every listed one
    still exists."""
    found = _received_reader_refusals()
    assert found, "corpus drifted: no received reader returns a refusal"
    expected = {k: count for k, (count, _) in KNOWN_READER_REFUSALS.items()}
    expected |= _MOVED_EXEMPTIONS
    new = {k: v for k, v in found.items() if k not in expected}
    changed = {
        k: (expected[k], v)
        for k, v in found.items()
        if k in expected and expected[k] != v
    }
    gone = sorted(set(expected) - set(found))
    assert not new, (
        "received readers returning a refusal after the run: make the"
        " failing guard declare it (DeclaredRefusalMixin._refuse,"
        " ReportsRefusal) and delete the reader's arm (ADR-0195, #6494):\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(new.items()))
    )
    assert not changed, (
        "listed reader refusals whose count changed (listed, found); a new"
        " refusal in a listed reader is a node's to declare, and one removed"
        " lowers the count:\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(changed.items()))
    )
    assert not gone, (
        "listed reader refusals that no longer exist; drop them from"
        f" KNOWN_READER_REFUSALS or _MOVED_EXEMPTIONS: {gone}"
    )


# ---------------------------------------------------------------------------
# Detector self-tests on synthetic sources
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "def read(outcome: ReceivedOutcome):\n"
            "    return HandlerResult.refused('x')\n",
            {"m.py::read": 1},
            id="reader-refuses",
        ),
        pytest.param(
            "def make() -> OutcomeReader:\n"
            "    def read(outcome: ReceivedOutcome) -> HandlerResult | None:\n"
            "        if outcome.succeeded:\n"
            "            return HandlerResult.refused('x')\n"
            "        return HandlerResult.refused('y')\n"
            "    return read\n",
            {"m.py::make.read": 2},
            id="nested-reader",
        ),
        pytest.param(
            "def _helper(tree):\n"
            "    return HandlerResult.refused('x')\n"
            "def read(outcome: ReceivedOutcome):\n"
            "    return _helper(outcome.tree)\n",
            {"m.py::_helper": 1},
            id="helper-the-reader-calls",
        ),
        pytest.param(
            "def _deeper():\n"
            "    return HandlerResult.refused('x')\n"
            "def _helper(tree):\n"
            "    return _deeper()\n"
            "def read(outcome: ReceivedOutcome):\n"
            "    return _helper(outcome.tree)\n",
            {"m.py::_deeper": 1},
            id="helper-of-a-helper",
        ),
        pytest.param(
            "def make() -> OutcomeReader:\n"
            "    no = HandlerResult.refused('x')\n"
            "    def read(outcome: ReceivedOutcome):\n"
            "        return no if outcome.succeeded else None\n"
            "    return read\n",
            {"m.py::make": 1},
            id="refusal-the-enclosing-factory-built",
        ),
        pytest.param(
            "def _read(outcome):\n"
            "    return HandlerResult.refused('x')\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        return run_received_tree(t, reader=_read)\n",
            {"m.py::_read": 1},
            id="unannotated-reader-passed-as-reader",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        return run_received_tree(\n"
            "            t, reader=lambda o: HandlerResult.refused('x')\n"
            "        )\n",
            {"m.py::UC.execute": 1},
            id="lambda-reader",
        ),
        pytest.param(
            "class UC:\n"
            "    def _no(self):\n"
            "        return HandlerResult.refused('x')\n"
            "    def execute(self):\n"
            "        def read(outcome: ReceivedOutcome):\n"
            "            return self._no()\n"
            "        return run_received_tree(t, reader=read)\n",
            {"m.py::UC._no": 1},
            id="self-method-helper",
        ),
        pytest.param(
            "from vultron.core.models.use_case_result import (\n"
            "    HandlerResult as HR,\n"
            ")\n"
            "def read(outcome: ReceivedOutcome):\n"
            "    return HR.refused('x')\n",
            {"m.py::read": 1},
            id="aliased-import",
        ),
        pytest.param(
            "def read(outcome: ReceivedOutcome):\n"
            "    return HandlerResult(\n"
            "        disposition=HandlerDisposition.REFUSED, reason='x'\n"
            "    )\n",
            {"m.py::read": 1},
            id="refused-construction",
        ),
        pytest.param(
            "def _unrelated():\n"
            "    return HandlerResult.refused('x')\n"
            "def read(outcome: ReceivedOutcome):\n"
            "    return HandlerResult.skipped('y')\n",
            {},
            id="refusal-outside-any-reader",
        ),
        pytest.param(
            "def read(outcome: ReceivedOutcome):\n"
            "    if outcome.succeeded:\n"
            "        return HandlerResult.skipped('y')\n"
            "    return None\n",
            {},
            id="reader-without-refusal",
        ),
    ],
)
def test_detector(source: str, expected: dict[str, int]) -> None:
    assert reader_refusals(_corpus.parse_inline(source), "m.py") == expected
