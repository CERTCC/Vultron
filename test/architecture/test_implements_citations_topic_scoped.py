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
"""Architecture ratchet: spec citations under ``vultron/`` are topic-scoped.

Why resolution alone is not enough
----------------------------------
Every spec ID cited in a ``vultron/`` docstring resolves to *some* requirement,
so an existence-only traceability check cannot see a wrong-topic citation.
The trigger spec once carried the ``TB`` prefix; when it became ``TRIG`` the
Testability topic kept ``TB``, and the five trigger routers plus
``trigger_models.py`` went on citing ``TB-01-001`` ("the system MUST use
pytest") 236 times as the requirement they implement. Every one of those IDs
resolved, so a resolution check reported all 236 as green (#3354, #3829; see
``notes/spec-authoring-rules.md`` § "A Resolving Citation Is Not a Correct
Citation").

Two checks, both over the shared corpus (TB-13-001, TB-13-002):

1. **Topic scope.** ``TB`` (Testability) requirements govern tests. No line
   under ``vultron/`` — docstring, comment, or string literal — may carry a
   ``TB-NN-NNN`` token. A violation names ``file:line``.
2. **Resolution.** Every ID in an ``Implements:`` block under
   ``vultron/adapters/driving/fastapi/routers/`` resolves in the spec
   registry (``vultron.metadata.specs``), so a typo'd ``TRIG`` ID cannot
   quietly replace a wrong ``TB`` one. Check 1 without check 2 would let a
   repoint land on nothing. ``spec-lint`` (SR-04-008) already rejects an
   unknown spec-ID-shaped token anywhere under ``vultron/`` or ``test/``,
   which is what covers ``trigger_models.py`` (it has no ``Implements:``
   blocks); check 2 is the narrower, always-on guard over the routers'
   ``Implements:`` blocks, and it also fails when it finds no block at all.

Once the trigger registry rows carry ``spec_ids`` (ADR-0110), check 2 moves
from a docstring scan to an import-time assertion over the table.

Test-fixture strings in this file avoid writing an *unknown* spec-ID-shaped
token literally (the SR-04-008 scan would reject it); they assemble one at
runtime instead.

Spec: SR-04-011 (the rule these two checks enforce); TB-13-001, TB-13-002
(corpus); MS-04-001 (ID shape); TRIG-01 through TRIG-09 (the topic the
routers implement).
"""

import re
from collections.abc import Iterator

import pytest

from test.architecture import _corpus
from vultron.metadata.specs.schema import SPEC_ID_CITATION_RE

_VULTRON_ROOT = _corpus.REPO_ROOT / "vultron"
_ROUTERS_ROOT = _VULTRON_ROOT / "adapters" / "driving" / "fastapi" / "routers"
_SPEC_DIR = _corpus.REPO_ROOT / "specs"

#: The Testability topic's requirement-ID shape (MS-04-001: ``PREFIX-NN-NNN``).
#: ``\b`` before ``TB`` keeps a prefix that merely *ends* in ``TB`` from
#: matching.
_TB_CITATION_RE = re.compile(r"\bTB-\d{2}-\d{3}\b")

#: Any requirement ID (MS-04-001), shared with spec-lint's SR-04-008 scan.
#: Deliberately excludes ``ADR-NNNN`` — an ``Implements:`` block may name an
#: ADR alongside its requirements, and an ADR is not a spec-registry entry.
_SPEC_ID_RE = SPEC_ID_CITATION_RE

_IMPLEMENTS_MARKER = "Implements:"
_DOCSTRING_QUOTES = '"""'


def _tb_citations(source: str) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, token)`` for every ``TB-NN-NNN`` token in *source*."""
    for lineno, line in enumerate(source.splitlines(), start=1):
        for match in _TB_CITATION_RE.finditer(line):
            yield lineno, match.group(0)


def _implements_ids(source: str) -> Iterator[tuple[int, str]]:
    """Yield ``(lineno, spec_id)`` for every ID inside an ``Implements:`` block.

    A block starts on the line carrying ``Implements:`` and runs through the
    following lines until a blank line or the closing docstring quotes. IDs on
    the marker line itself count, so a one-line
    ``Implements: DEMOMA-07-001, TRIG-09-001.`` is read in full. The closing
    quotes may share a line with citations — on the marker line or on a
    continuation line — and the IDs before them are still read; the block
    closes after that line.
    """
    in_block = False
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _IMPLEMENTS_MARKER in line:
            in_block = True
            text = line.split(_IMPLEMENTS_MARKER, 1)[1]
        elif in_block:
            if not line.strip():
                in_block = False
                continue
            text = line
        else:
            continue
        if _DOCSTRING_QUOTES in text:
            text = text.split(_DOCSTRING_QUOTES, 1)[0]
            in_block = False
        for match in _SPEC_ID_RE.finditer(text):
            yield lineno, match.group(0)


@pytest.mark.spec("SR-04-011")
def test_no_testability_citations_under_vultron() -> None:
    """No ``TB-NN-NNN`` token may appear anywhere under ``vultron/``.

    ``TB`` is the Testability topic; its requirements govern tests, so an
    application module cannot implement one. A hit is a wrong-topic citation
    even though the ID resolves — repoint it to the TRIG requirement the code
    implements, or delete it when no TRIG counterpart exists.
    """
    violations: list[str] = []
    for path, source in _corpus.sources_mentioning("TB-", under=_VULTRON_ROOT):
        rel = path.relative_to(_corpus.REPO_ROOT)
        for lineno, token in _tb_citations(source):
            violations.append(f"  {rel}:{lineno}: {token}")

    assert violations == [], (
        "Modules under vultron/ cite Testability (TB-) requirements. These "
        "resolve, but they are the wrong topic: TB governs tests, and the "
        "trigger spec is TRIG (see notes/spec-authoring-rules.md § 'A "
        "Resolving Citation Is Not a Correct Citation').\n"
        + "\n".join(violations)
    )


@pytest.mark.spec_corpus
@pytest.mark.spec("SR-04-011")
def test_router_implements_citations_resolve() -> None:
    """Every ``Implements:`` ID under the FastAPI routers resolves in the registry.

    Pairs with :func:`test_no_testability_citations_under_vultron`: the
    topic-scope check forbids the wrong ID, this one forbids a made-up one.
    The routers are the modules whose citations #3829 repointed, so this is
    also a zero-target guard — the check fails if no ``Implements:`` block is
    found at all.
    """
    from vultron.metadata.specs.registry import load_registry

    registry = load_registry(_SPEC_DIR)
    known = registry.all_specs

    seen = 0
    unresolved: list[str] = []
    for path, source in _corpus.sources_mentioning(
        _IMPLEMENTS_MARKER, under=_ROUTERS_ROOT
    ):
        rel = path.relative_to(_corpus.REPO_ROOT)
        for lineno, spec_id in _implements_ids(source):
            seen += 1
            if spec_id not in known:
                unresolved.append(f"  {rel}:{lineno}: {spec_id}")

    assert seen > 0, (
        f"No Implements: citations found under {_ROUTERS_ROOT.relative_to(_corpus.REPO_ROOT)}; "
        "the ratchet has nothing to check, which is a failure, not a pass."
    )
    assert unresolved == [], (
        "Implements: citations under the FastAPI routers name IDs that are "
        "not in the spec registry (vultron.metadata.specs):\n"
        + "\n".join(unresolved)
    )


# ---------------------------------------------------------------------------
# Detector self-tests — the negative cases, asserted directly rather than
# inferred from a green run over the live tree.
# ---------------------------------------------------------------------------


def test_tb_detector_reports_comment_and_string_with_line_numbers() -> None:
    """A TB token in a comment, a docstring, or a string literal is found by line."""
    source = (
        '"""Module docstring citing TB-04-001."""\n'
        "\n"
        "X = 1  # implements TB-01-001\n"
        'DESC = "returns the activity (TB-04-001)"\n'
    )
    assert list(_tb_citations(source)) == [
        (1, "TB-04-001"),
        (3, "TB-01-001"),
        (4, "TB-04-001"),
    ]


def test_tb_detector_ignores_trig_and_longer_prefixes() -> None:
    """TRIG IDs and prefixes that merely end in TB are not TB citations."""
    # The longer-prefix token is assembled at runtime so spec-lint's SR-04-008
    # scan does not see an unknown spec ID written literally in this file.
    longer_prefix = "OU" + "TB-01-001"
    source = f"# TRIG-04-001, {longer_prefix}, TB-1-001, TB-01-01\n"
    assert list(_tb_citations(source)) == []


def test_implements_parser_reads_multiline_block_and_stops_at_blank() -> None:
    """IDs on the marker line and its continuation lines are read; the block ends at a blank line."""
    source = (
        '    """\n'
        "    Trigger something.\n"
        "\n"
        "    Implements: ADR-0026 (CM-16-006); TRIG-01-001,\n"
        "        TRIG-02-005, TRIG-03-001\n"
        "\n"
        "    Not a citation: HP-01-001\n"
        '    """\n'
    )
    assert list(_implements_ids(source)) == [
        (4, "CM-16-006"),
        (4, "TRIG-01-001"),
        (5, "TRIG-02-005"),
        (5, "TRIG-03-001"),
    ]


def test_implements_parser_stops_at_closing_quotes() -> None:
    """A block that runs to the docstring's closing quotes does not leak past them."""
    source = (
        '    """Do it.\n'
        "\n"
        "    Implements:\n"
        "        TRIG-09-001, TRIG-06-001\n"
        '    """\n'
        "    x = 'SL-01-001'\n"
    )
    assert list(_implements_ids(source)) == [
        (4, "TRIG-09-001"),
        (4, "TRIG-06-001"),
    ]


def test_implements_parser_reads_ids_before_closing_quotes_on_same_line() -> (
    None
):
    """IDs on a line that also closes the docstring are read; nothing after leaks in."""
    source = (
        '    """Do it.\n'
        "\n"
        "    Implements:\n"
        '        TRIG-09-001, TRIG-06-001"""\n'
        "    x = 'SL-01-001'\n"
        "    y = 'HP-01-001'\n"
    )
    assert list(_implements_ids(source)) == [
        (4, "TRIG-09-001"),
        (4, "TRIG-06-001"),
    ]


def test_implements_parser_marker_line_that_closes_docstring_ends_block() -> (
    None
):
    """A marker line carrying the closing quotes is read and closes the block."""
    source = (
        '    """Implements: DEMOMA-07-001, TRIG-09-001."""\n'
        "    x = 'SL-01-001'\n"
        "    y = 'HP-01-001'\n"
    )
    assert list(_implements_ids(source)) == [
        (1, "DEMOMA-07-001"),
        (1, "TRIG-09-001"),
    ]
