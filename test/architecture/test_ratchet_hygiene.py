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
"""Hygiene ratchets over the test suite's own gates.

**One corpus.** All architecture ratchets must route AST parsing through
``_corpus.parse_inline`` and file discovery through
``_corpus.files_mentioning``, ``_corpus.all_trees``, ``_corpus.all_sources``, or
``_corpus.sources_mentioning``.  Direct ``ast.parse(`` or ``.rglob(`` calls in
sibling files bypass the shared module-level corpus, re-read source files on
every test run, and risk blowing the per-test timeout budget.

**Every xfail is strict.** An ``xfail`` in this repo marks a *goal state* — a
requirement written before the code that satisfies it.  Under ``strict=False``
the day the code lands is reported as an XPASS in a tally nobody reads: the
marker stays, the assertion it guards stops being checked, and the gate has
gone inert.  ``strict=True`` turns that into a failure naming the test, which
is the signal that actually reaches a reader.

ARCH-21-008 states this, as a SHOULD scoped to an ARCH-21-005 backlog's
companion goal test.  This check generalises it to every ``xfail`` under
``test/``, which is where the repo already stands — the last non-strict one was
#3934 item 2 — and which the doctrine stated in
``test_validate_assignment_ratchet.py``, ``test_protocol_asks_specs.py`` and
``test/ci/README-case-log-ratchet.md`` asks for in its own words.  A genuine
exception goes in ``_NON_STRICT_XFAIL_EXEMPT`` with its reason, rather than
being spelled lax and left unexplained.

Spec: TB-13-003, TB-13-009, ARCH-21-008.
"""

import ast
from pathlib import Path

from test.architecture import _corpus

_ARCH_DIR = Path(__file__).parent

_TEST_ROOT = _corpus.REPO_ROOT / "test"

_FORBIDDEN = ("ast.parse(", ".rglob(")

_EXEMPT = {"_corpus.py"}


def test_no_raw_ast_parse_or_rglob_in_siblings():
    """No sibling file (except _corpus.py) may use ast.parse( or .rglob(.

    Spec: TB-13-003.
    """
    violations: list[str] = []
    for py_file in sorted(_ARCH_DIR.glob("*.py")):
        if py_file.name in _EXEMPT:
            continue
        if py_file.name == Path(__file__).name:
            continue
        source = py_file.read_text(encoding="utf-8")
        for fragment in _FORBIDDEN:
            if fragment in source:
                violations.append(f"{py_file.name}: contains {fragment!r}")

    assert violations == [], (
        "The following files bypass the shared corpus (TB-13-003).\n"
        "Replace ast.parse( with _corpus.parse_inline( and\n"
        ".rglob( with _corpus.files_mentioning / all_trees / all_sources:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


#: Files allowed a non-strict ``xfail``, each with the reason it needs one.
#: A pinned exemption set, not a ratchet (ARCH-18-005): there is no backlog
#: being worked down, only a doctrine with no exception today.
_NON_STRICT_XFAIL_EXEMPT: frozenset[str] = frozenset()


def _lax_xfail_lines(tree: ast.AST) -> list[int]:
    """Return the line of every ``mark.xfail`` call that is not ``strict=True``.

    Keyed on the marker call, not on the decorated function's name, so a
    rename loses no subjects (#5535).  A ``pytest.param(marks=...)`` entry is
    covered too: the call has the same shape wherever it sits.
    """
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).endswith("mark.xfail"):
            continue
        strict = next((k for k in node.keywords if k.arg == "strict"), None)
        if strict is None or ast.unparse(strict.value) != "True":
            lines.append(node.lineno)
    return sorted(lines)


def test_every_xfail_is_strict():
    """No ``xfail`` under test/ omits or disables ``strict``.

    Spec: ARCH-21-008.  See the module docstring for why, and for the sense in
    which this generalises that requirement.
    """
    violations = sorted(
        f"{rel}:{line}"
        for path, tree in _corpus.files_mentioning("xfail", under=_TEST_ROOT)
        if (rel := path.relative_to(_corpus.REPO_ROOT).as_posix())
        not in _NON_STRICT_XFAIL_EXEMPT
        for line in _lax_xfail_lines(tree)
    )

    assert violations == [], (
        "non-strict xfail (a goal state whose completion nobody is told"
        " about — add strict=True, or add the file to"
        " _NON_STRICT_XFAIL_EXEMPT with a reason):\n"
        + "\n".join(f"  + {v}" for v in violations)
    )


def test_the_xfail_matcher_can_see_a_violation():
    """``_lax_xfail_lines`` recognises both lax spellings and passes strict.

    An empty violation list is the expected state above, which is the shape
    that hides a scan looking for something it can never find.  This drives
    the same function the ratchet uses, not a copy of its logic (#5535).
    """
    tree = _corpus.parse_inline(
        "import pytest\n"
        "@pytest.mark.xfail(reason='strict omitted')\n"
        "def test_a(): pass\n"
        "@pytest.mark.xfail(strict=False, reason='explicitly lax')\n"
        "def test_b(): pass\n"
        "@pytest.mark.xfail(strict=True, reason='goal state')\n"
        "def test_c(): pass\n"
        "pytest.param('x', marks=pytest.mark.xfail(reason='in a param'))\n"
    )

    assert _lax_xfail_lines(tree) == [2, 4, 8]
