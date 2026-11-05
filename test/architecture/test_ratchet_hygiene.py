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

TB-17-001 states this for every ``xfail`` under ``test/``.  It generalises
ARCH-21-008, which asks the same but only as a SHOULD and only of an
ARCH-21-005 backlog's companion goal test, and it writes down what
``notes/spec-authoring-rules.md``, ``test_validate_assignment_ratchet.py``,
``test_protocol_asks_specs.py`` and ``test/ci/README-case-log-ratchet.md``
already state in prose.  The tree complies in full; the last non-strict marker
was #3934 item 2.  A genuine exception goes in
``_NON_STRICT_XFAIL_EXEMPTIONS`` — a pinned exemption set, not a ratchet
(ARCH-18-010) — with its reason, rather than being spelled lax and left
unexplained.

``xfail_strict = true`` in ``pyproject.toml`` is the runtime half of the same
rule, and the two are not redundant: the ini fails a marker only once it
XPASSes, and only in a spelling pytest itself resolves, while this check fails
the marker the moment it is written.

Spec: TB-13-003, TB-13-009, TB-17-001.
"""

import ast
from pathlib import Path

import pytest

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
#: A pinned exemption set, not a ratchet (ARCH-18-005, ARCH-18-010): there is
#: no backlog being worked down, only a doctrine with no exception today, so
#: the empty set is its terminal value and ARCH-18-003 asks for no marker.
#: Named ``_EXEMPTIONS`` so that an entry added later is a baseline
#: ``test_ratchet_baselines_name_an_owner.py`` can see: its ``_FRAGMENTS``
#: match ``_EXEMPTIONS``, not ``_EXEMPT``, and ARCH-18-005 then requires a
#: ``# permanent:`` marker here.
_NON_STRICT_XFAIL_EXEMPTIONS: frozenset[str] = frozenset()


def _xfail_markers(tree: ast.AST) -> list[tuple[int, bool]]:
    """Return ``(line, is_strict)`` for every ``mark.xfail`` marker in *tree*.

    Keyed on the marker, not on the decorated function's name, so a rename
    loses no subjects (#5535).  A ``pytest.param(marks=...)`` entry is covered
    too: the marker has the same shape wherever it sits.

    Two spellings read as not-strict.  A call that omits ``strict`` or sets it
    to anything but a literal ``True``; and a *bare* ``mark.xfail`` with no
    call at all, whose strictness falls back to the ``xfail_strict`` ini.  A
    check blind to the bare form would be the very shape TB-17-001 exists to
    prevent, that being the laxest spelling of all.

    Loose reading: it can **invent** a violation, and it can **miss** one.  It
    invents on ``strict=SOME_TRUE_CONSTANT`` and on ``**{"strict": True}``,
    which do not unparse to ``True``, and on a bare ``pytest.mark.xfail`` that
    is referred to rather than applied.  It misses an indirection the source
    text does not spell — ``xf = pytest.mark.xfail`` then ``@xf(...)``, or
    ``getattr(pytest.mark, "xfail")`` — because the matcher reads names, not
    values.  The tree holds none of the five today, and ``xfail_strict = true``
    in ``pyproject.toml`` catches every missed form at run time.
    """
    called = {
        id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)
    }
    found: list[tuple[int, bool]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "xfail":
            if (
                ast.unparse(node).endswith("mark.xfail")
                and id(node) not in called
            ):
                found.append((node.lineno, False))
            continue
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).endswith("mark.xfail"):
            continue
        strict = next((k for k in node.keywords if k.arg == "strict"), None)
        found.append(
            (
                node.lineno,
                strict is not None and ast.unparse(strict.value) == "True",
            )
        )
    return sorted(found)


def _lax_xfail_lines(tree: ast.AST) -> list[int]:
    """Return the line of every ``mark.xfail`` marker that is not strict."""
    return [line for line, is_strict in _xfail_markers(tree) if not is_strict]


@pytest.mark.spec("TB-17-001")
def test_every_xfail_is_strict():
    """No ``xfail`` under test/ omits or disables ``strict``.

    Spec: TB-17-001, which states the rule this check enforces.  ARCH-21-008
    is the narrower SHOULD it generalises; see the module docstring for the
    sense in which it does.
    """
    violations = sorted(
        f"{rel}:{line}"
        for path, tree in _corpus.files_mentioning("xfail", under=_TEST_ROOT)
        if (rel := path.relative_to(_corpus.REPO_ROOT).as_posix())
        not in _NON_STRICT_XFAIL_EXEMPTIONS
        for line in _lax_xfail_lines(tree)
    )

    assert violations == [], (
        "non-strict xfail (a goal state whose completion nobody is told"
        " about — add strict=True, or add the file to"
        " _NON_STRICT_XFAIL_EXEMPTIONS with a reason; TB-17-001):\n"
        + "\n".join(f"  + {v}" for v in violations)
    )


def test_the_xfail_matcher_can_see_a_violation():
    """``_lax_xfail_lines`` recognises every lax spelling and passes strict.

    An empty violation list is the expected state above, which is the shape
    that hides a scan looking for something it can never find.  This drives
    the same function the ratchet uses, not a copy of its logic (#5535).

    Every lax spelling is here, including the bare marker with no call, which
    is lax by the ``xfail_strict`` default and the easiest one for a matcher
    keyed on calls to miss.
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
        "@pytest.mark.xfail\n"
        "def test_d(): pass\n"
        "pytest.param('y', marks=pytest.mark.xfail)\n"
        "@pytest.mark.skip(reason='not an xfail at all')\n"
        "def test_e(): pass\n"
    )

    assert _lax_xfail_lines(tree) == [2, 4, 8, 9, 11]
    # And the strict arm is read, not merely absent from the lax list.
    assert _xfail_markers(tree) == [
        (2, False),
        (4, False),
        (6, True),
        (8, False),
        (9, False),
        (11, False),
    ]


def test_the_xfail_scan_reaches_the_test_tree():
    """The corpus walk ``test_every_xfail_is_strict`` reads has subjects.

    That test passes on an empty violation list, which is also what a walk
    that found no files returns — so a wrong ``_TEST_ROOT`` or a moved corpus
    root would make it green while scanning nothing, and the matcher test
    above would still pass.  A floor on the markers found separates the two.
    Keyed on a count rather than a file name, so a rename loses no subjects
    (#5535); the tree holds 92 markers today, so the floor has wide room.
    """
    markers = [
        marker
        for _path, tree in _corpus.files_mentioning("xfail", under=_TEST_ROOT)
        for marker in _xfail_markers(tree)
    ]

    assert len(markers) > 20, (
        "the xfail scan found almost nothing, so test_every_xfail_is_strict"
        f" is passing vacuously: {len(markers)} markers under {_TEST_ROOT}"
    )
