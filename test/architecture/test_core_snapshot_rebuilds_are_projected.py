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

The scan flags each ``model_validate`` call under ``vultron/core/`` whose
argument reads a snapshot but is neither that projection nor a dict literal.
A dict literal builds a new value from chosen snapshot fields; it does not
rebuild the snapshot's object.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_PROJECTION = "project_wire_snapshot_to_core"


def _violations(path: Path, tree: ast.AST) -> list[str]:
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    found: list[str] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and _corpus.callee_name(node.func) == "model_validate"
            and node.args
        ):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Dict):
            continue
        if (
            isinstance(arg, ast.Call)
            and _corpus.callee_name(arg.func) == _PROJECTION
        ):
            continue
        if "snapshot" in ast.unparse(arg).lower():
            found.append(f"{rel}:{node.lineno}")
    return found


@pytest.mark.spec("ARCH-20-012")
def test_core_rebuilds_snapshots_only_through_the_projection() -> None:
    violations = [
        violation
        for path, tree in _corpus.files_mentioning(
            "model_validate", under=_CORE
        )
        for violation in _violations(path, tree)
    ]
    assert not violations, (
        f"core validates a snapshot without {_PROJECTION}() (ARCH-20-012):\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ("Note.model_validate(entry.payload_snapshot)\n", True),
        ("Note.model_validate(snapshot['object'])\n", True),
        (f"Note.model_validate({_PROJECTION}(Note, snapshot))\n", False),
        ("T.model_validate({'reason': snapshot.get('content')})\n", False),
        ("T.model_validate(data)\n", False),
    ],
)
def test_detector_flags_only_an_unprojected_snapshot(
    source: str, flagged: bool
) -> None:
    tree = _corpus.parse_inline(source)
    assert bool(_violations(_CORE / "x.py", tree)) is flagged
