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
that takes a ``ReceivedOutcome``, together with each function it is nested
in (a factory whose refusal the reader returns) and each function of the
same module that any of these calls by name.  An entry is ``path::qualified.name``, and it
counts the ``HandlerResult.refused(...)`` calls in that function's own body.

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

#: Readers whose refusals another issue removes, with the issue.
# owner: #6499
_MOVED_EXEMPTIONS: dict[str, str] = {
    "fault/responses.py::_unnamed_entry_refusal": "#6499",
    "fault/responses.py::_reseed_verdict.read": "#6499",
}


def _is_refused_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "refused"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "HandlerResult"
    )


_Function = ast.FunctionDef | ast.AsyncFunctionDef
_FUNCTION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _own_nodes(fn: _Function) -> Iterator[ast.AST]:
    """The nodes of *fn*'s body, not of a function or lambda nested in it."""
    nested = (*_FUNCTION_TYPES, ast.Lambda)
    stack: list[ast.AST] = [n for n in fn.body if not isinstance(n, nested)]
    while stack:
        node = stack.pop()
        yield node
        stack += [
            c for c in ast.iter_child_nodes(node) if not isinstance(c, nested)
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


def reader_refusals(tree: ast.AST, rel: str) -> dict[str, int]:
    """The refusal count of each reader of module *rel*, and its helpers."""
    functions = dict(_functions(tree))
    top_level = {name for name in functions if "." not in name}
    readers = [name for name, fn in functions.items() if _takes_outcome(fn)]
    # A reader nested in a factory may return a refusal the factory built.
    enclosing = {
        ".".join(parts[:i])
        for parts in (name.split(".") for name in readers)
        for i in range(1, len(parts))
    }
    reached = set(readers) | (enclosing & set(functions))
    pending = list(reached)
    while pending:
        for node in _own_nodes(functions[pending.pop()]):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in top_level
                and node.func.id not in reached
            ):
                reached.add(node.func.id)
                pending.append(node.func.id)
    found: dict[str, int] = {}
    for name in sorted(reached):
        count = sum(map(_is_refused_call, _own_nodes(functions[name])))
        if count:
            found[f"{rel}::{name}"] = count
    return found


def _received_reader_refusals() -> dict[str, int]:
    found: dict[str, int] = {}
    for path, tree in _corpus.files_mentioning(
        "ReceivedOutcome", under=RECEIVED_ROOT
    ):
        found |= reader_refusals(
            tree, path.relative_to(RECEIVED_ROOT).as_posix()
        )
    return found


@pytest.mark.spec("HP-01-003")
def test_received_readers_return_only_the_listed_refusals() -> None:
    """Every reader refusal is listed, and every listed one still exists."""
    found = {
        key: count
        for key, count in _received_reader_refusals().items()
        if key not in _MOVED_EXEMPTIONS
    }
    known = {key: count for key, (count, _) in KNOWN_READER_REFUSALS.items()}
    new = {k: v for k, v in found.items() if known.get(k) != v}
    gone = sorted(set(known) - set(found))
    assert not new, (
        "received readers returning HandlerResult.refused(...) after the"
        " run: make the failing guard declare the refusal"
        " (DeclaredRefusalMixin._refuse, ReportsRefusal) and delete the"
        " reader's arm (ADR-0195, #6494):\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(new.items()))
    )
    assert not gone, (
        "listed reader refusals that no longer exist; drop them from"
        f" KNOWN_READER_REFUSALS: {gone}"
    )


def test_the_moved_exemptions_are_still_reader_refusals() -> None:
    """An exemption another issue owns names a refusal the scan still finds."""
    found = _received_reader_refusals()
    stale = sorted(key for key in _MOVED_EXEMPTIONS if key not in found)
    assert not stale, f"drop these from _MOVED_EXEMPTIONS: {stale}"


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
