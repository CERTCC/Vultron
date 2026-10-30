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
"""Core rebuilds an object from a snapshot only through the projection (ARCH-20-012).

A ledger ``payloadSnapshot`` holds objects in wire shape, so a core class
validating one directly either rejects its camelCase keys or stamps this
replica's clock over an absent time. ``project_wire_snapshot_to_core`` is the
one seam that renames the keys and reads an absent time as absent.

Which value is a snapshot cannot be read off a variable's name, so the scan
flags every ``model_validate`` call under ``vultron/core/`` whose argument is
neither that projection nor a dict literal. A dict literal builds a new value
from chosen fields; it does not rebuild a stored object. A call that validates
something other than a snapshot is listed in :data:`_NOT_A_SNAPSHOT` with its
reason, and an entry no call needs fails the check (ARCH-18-005).
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_PROJECTION = "project_wire_snapshot_to_core"

#: ``(module, function)`` pairs whose ``model_validate`` reads no snapshot.
#: Pinned exemption set: each entry is a recorded decision, not a debt.
_NOT_A_SNAPSHOT: dict[tuple[str, str], str] = {
    (
        "vultron/core/models/embargo_event.py",
        "with_subject",
    ): "revalidates this object's own dump with a new subject",
}


def _validated_value(node: ast.Call) -> ast.expr | None:
    if node.args:
        return node.args[0]
    return next((k.value for k in node.keywords if k.arg == "obj"), None)


def _unprojected_calls(
    path: Path, tree: ast.AST
) -> list[tuple[str, str, int]]:
    """``(module, function, line)`` of each unprojected ``model_validate``."""
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    found: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, child.name)
                continue
            if (
                isinstance(child, ast.Call)
                and _corpus.callee_name(child.func) == "model_validate"
            ):
                arg = _validated_value(child)
                if arg is not None and not (
                    isinstance(arg, ast.Dict)
                    or (
                        isinstance(arg, ast.Call)
                        and _corpus.callee_name(arg.func) == _PROJECTION
                    )
                ):
                    found.append((rel, function, _corpus.node_line(child)))
            visit(child, function)

    visit(tree, "<module>")
    return found


def _core_calls() -> list[tuple[str, str, int]]:
    return [
        call
        for path, tree in _corpus.files_mentioning(
            "model_validate", under=_CORE
        )
        for call in _unprojected_calls(path, tree)
    ]


@pytest.mark.spec("ARCH-20-012")
def test_core_rebuilds_snapshots_only_through_the_projection() -> None:
    violations = [
        f"{module}:{line} in {function}()"
        for module, function, line in _core_calls()
        if (module, function) not in _NOT_A_SNAPSHOT
    ]
    assert not violations, (
        f"core validates a value without {_PROJECTION}() (ARCH-20-012). "
        "Project a snapshot through it, or list a non-snapshot call in "
        "_NOT_A_SNAPSHOT with its reason:\n" + "\n".join(violations)
    )


def test_every_exemption_is_still_used() -> None:
    used = {(module, function) for module, function, _ in _core_calls()}
    stale = sorted(set(_NOT_A_SNAPSHOT) - used)
    assert not stale, f"remove these _NOT_A_SNAPSHOT entries: {stale}"


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ("Note.model_validate(entry.payload_snapshot)\n", True),
        ("Note.model_validate(status_data)\n", True),
        ("Note.model_validate(obj=data)\n", True),
        ("def f():\n    return Note.model_validate(data)\n", True),
        (f"Note.model_validate({_PROJECTION}(Note, data))\n", False),
        (f"Note.model_validate(obj={_PROJECTION}(Note, data))\n", False),
        ("T.model_validate({'reason': snapshot.get('content')})\n", False),
    ],
)
def test_detector_flags_every_unprojected_value(
    source: str, flagged: bool
) -> None:
    tree = _corpus.parse_inline(source)
    assert bool(_unprojected_calls(_CORE / "x.py", tree)) is flagged


def test_detector_names_the_enclosing_function() -> None:
    tree = _corpus.parse_inline(
        "class C:\n    def with_subject(self):\n"
        "        return C.model_validate(self.model_dump())\n"
    )
    assert _unprojected_calls(_CORE / "x.py", tree) == [
        ("vultron/core/x.py", "with_subject", 3)
    ]
