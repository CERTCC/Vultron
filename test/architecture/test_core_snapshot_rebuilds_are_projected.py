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
flags every rebuild under ``vultron/core/`` whose value is neither that
projection nor a dict literal: a ``model_validate``, ``model_validate_json``,
``validate_python`` or ``validate_json`` call, and a class called with a
``**`` spread. A dict literal builds a new value from chosen fields; it does
not rebuild a stored object. One that spreads another mapping (``{**snap}``)
carries that mapping's keys, so it counts as the mapping. A call that
validates something other than a snapshot is listed in
:data:`_NOT_A_SNAPSHOT_EXEMPTIONS` with its reason, and an entry no call needs
fails the check (ARCH-18-005).
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_PROJECTION = "project_wire_snapshot_to_core"

#: ``(module, function)`` pairs whose rebuild reads no snapshot.
#: Pinned exemption set: each entry is a recorded decision, not a debt.
# permanent: ARCH-20-012 (each entry validates a value that is not a snapshot)
_NOT_A_SNAPSHOT_EXEMPTIONS: dict[tuple[str, str], str] = {
    (
        "vultron/core/models/embargo_event.py",
        "with_subject",
    ): "revalidates this object's own dump with a new subject",
    (
        "vultron/core/models/embargo_consent.py",
        "for_actor",
    ): "revalidates this row's own dump with its attribution set",
    (
        "vultron/core/models/embargo_register.py",
        "_entry_after",
    ): "revalidates this entry's own dump with the change applied",
    (
        "vultron/core/models/case_ledger.py",
        "_compute_entry_hash",
    ): (
        "reads the one `received_at` timestamp the hash input needs, with the"
        " adapter the field itself uses, so the hash accepts exactly the"
        " spellings the field accepts (CS-13-007)"
    ),
    (
        "vultron/core/behaviors/case/nodes/case_setup.py",
        "update",
    ): "spreads the endpoints this node hosts for its own CaseActor",
    (
        "vultron/core/use_cases/triggers/_base.py",
        "_build_result",
    ): "spreads the fields of the activity this trigger captured",
    (
        "vultron/core/use_cases/triggers/case/create.py",
        "_build_result",
    ): "spreads the fields of the activity this trigger captured",
    (
        "vultron/core/use_cases/triggers/note.py",
        "_build_result",
    ): "spreads the fields of the activity this trigger captured",
}


_VALIDATORS = frozenset(
    {
        "model_validate",
        "model_validate_json",
        "validate_python",
        "validate_json",
    }
)


def _validated_value(node: ast.Call) -> ast.expr | None:
    """The value a rebuild call validates, or ``None`` when it is no rebuild."""
    name = _corpus.callee_name(node.func) or ""
    if name in _VALIDATORS:
        if node.args:
            return node.args[0]
        return next(
            (k.value for k in node.keywords if k.arg in {"obj", "json_data"}),
            None,
        )
    if name[:1].isupper():
        return next((k.value for k in node.keywords if k.arg is None), None)
    return None


def _is_projected(value: ast.expr) -> bool:
    """True for the projection or a dict literal spreading no other mapping."""
    if isinstance(value, ast.Dict):
        return None not in value.keys
    return (
        isinstance(value, ast.Call)
        and _corpus.callee_name(value.func) == _PROJECTION
    )


def _unprojected_calls(
    path: Path, tree: ast.AST
) -> list[tuple[str, str, int]]:
    """``(module, function, line)`` of each unprojected rebuild."""
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    found: list[tuple[str, str, int]] = []

    def visit(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, child.name)
                continue
            if isinstance(child, ast.Call):
                value = _validated_value(child)
                if value is not None and not _is_projected(value):
                    found.append((rel, function, _corpus.node_line(child)))
            visit(child, function)

    visit(tree, "<module>")
    return found


def _core_calls() -> list[tuple[str, str, int]]:
    return [
        call
        for path, tree in _corpus.files_mentioning(
            "validate_", "**", under=_CORE
        )
        for call in _unprojected_calls(path, tree)
    ]


@pytest.mark.spec("ARCH-20-012")
def test_core_rebuilds_snapshots_only_through_the_projection() -> None:
    violations = [
        f"{module}:{line} in {function}()"
        for module, function, line in _core_calls()
        if (module, function) not in _NOT_A_SNAPSHOT_EXEMPTIONS
    ]
    assert not violations, (
        f"core validates a value without {_PROJECTION}() (ARCH-20-012). "
        "Project a snapshot through it, or list a non-snapshot call in "
        "_NOT_A_SNAPSHOT_EXEMPTIONS with its reason:\n" + "\n".join(violations)
    )


def test_every_exemption_is_still_used() -> None:
    used = {(module, function) for module, function, _ in _core_calls()}
    stale = sorted(set(_NOT_A_SNAPSHOT_EXEMPTIONS) - used)
    assert not stale, (
        f"remove these _NOT_A_SNAPSHOT_EXEMPTIONS entries: {stale}"
    )


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
        ("Note.model_validate({**entry.payload_snapshot})\n", True),
        ("Note.model_validate({**snap, 'id': x})\n", True),
        ("Note.model_validate_json(raw)\n", True),
        ("TypeAdapter(Note).validate_python(snap)\n", True),
        ("TypeAdapter(Note).validate_json(raw)\n", True),
        ("Note(**entry.payload_snapshot)\n", True),
        ("Note(**{'content': text})\n", False),
        (f"Note(**{_PROJECTION}(Note, data))\n", False),
        ("note(**kwargs)\n", False),
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
