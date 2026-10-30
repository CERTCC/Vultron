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
"""No translation path open-codes a per-field reference collapse (ARCH-23-008).

The AS2 reference-typed fields are derived from the wire classes' annotations
(ARCH-23-004, ``object_ref_fields``). A path that collapses references by
walking its own literal list of field names (``("actor", "object",
"target")``) drifts from that derived set as soon as a class gains or narrows a
reference field.

The scan flags a literal tuple, list or set under ``vultron/wire/``,
``vultron/adapters/`` or ``vultron/core/`` that names three or more AS2
reference fields. ``vultron/demo/`` is out of scope: it renders reports and
translates nothing.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_ROOTS = tuple(
    _corpus.REPO_ROOT / "vultron" / layer
    for layer in ("wire", "adapters", "core")
)

#: AS2 reference field names, in both their core and wire spellings.
_REFERENCE_NAMES = frozenset(
    {
        "actor",
        "instrument",
        "object",
        "object_",
        "origin",
        "result",
        "target",
    }
)

#: Fewer than this many names in one literal is not a field list.
_THRESHOLD = 3


def _violations(path: Path, tree: ast.AST) -> list[str]:
    rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            continue
        names = {
            elt.value
            for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        }
        if len(names & _REFERENCE_NAMES) >= _THRESHOLD:
            found.append(f"{rel}:{node.lineno}")
    return found


@pytest.mark.spec("ARCH-23-008")
def test_no_translation_path_lists_reference_fields_by_hand() -> None:
    violations = [
        violation
        for root in _ROOTS
        for path, tree in _corpus.all_trees(root)
        for violation in _violations(path, tree)
    ]
    assert not violations, (
        "a hand-listed set of AS2 reference fields; use object_ref_fields() "
        "(ARCH-23-004, ARCH-23-008):\n" + "\n".join(violations)
    )


@pytest.mark.parametrize(
    ("source", "flagged"),
    [
        ("for k in ('actor', 'object', 'target'): pass\n", True),
        ("REFS = {'object_', 'origin', 'result'}\n", True),
        ("PAIR = ('actor', 'object')\n", False),
        ("NAMES = ['id', 'type', 'name']\n", False),
    ],
)
def test_detector_flags_a_hand_listed_reference_set(
    source: str, flagged: bool
) -> None:
    tree = _corpus.parse_inline(source)
    assert bool(_violations(_ROOTS[0] / "x.py", tree)) is flagged
