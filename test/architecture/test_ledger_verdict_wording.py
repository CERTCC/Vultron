"""Ratchet: the ledger verdict is *admitted*/*refused*, never accepted/rejected.

"Accept" and "Reject" name only the AS2 activities.  The CASE_MANAGER's verdict
on whether an assertion enters the ledger is *admitted* or *refused*
(CLP-02-012, glossary **Ledger Admission**).  The old wording made a
participant's ``Reject`` read like a refusal that the ledger leaves out, which
is how declines came to look unledgered (#3748).

This scans every authored word the project ships, not a list of pages, so a
page or module added later is covered the day it lands: ``specs/``,
``notes/``, ``docs/`` (decision records excluded: ADR bodies are history and
are not edited, ADR-0127) and ``vultron/`` (Python and the prose beside it).
The glossary's aliases-to-avoid cell for **Ledger Admission** is the one place
the phrases must appear, because it declares them.

See: GitHub issue #4477.
"""

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

import functools
import re
from pathlib import Path

import pytest

from test.architecture import _corpus

_ROOT = _corpus.REPO_ROOT

#: One piece of the gap between the two words: whitespace (a line wrap), a
#: ``#`` comment or ``>`` quote marker, Markdown emphasis or code marks (``*``,
#: ``_``, a backtick), the quotes and ``+`` of a Python string split across
#: lines, the ``f``/``r``/``b``/``u`` prefix of such a string's next piece, or
#: a hyphen.
_GAP_PIECE = r"""(?:[\s#>*_`"'+-]|[rRbBfFuU]{1,2}(?=["']))"""

#: The gap may not span a blank line or start a new list item: words in two
#: paragraphs or two bullets are not one phrase.
_GAP = rf"(?:(?!\n[ \t]*(?:\n|[-*+][ \t]|\d+\.[ \t])){_GAP_PIECE})+"

#: Letter lookarounds rather than ``\b``, so a word wrapped in ``_emphasis_``
#: still has a boundary.
_BANNED = re.compile(
    rf"(?<![a-z])(?:accepted{_GAP}assertions?|rejected{_GAP}assertions?"
    rf"|rejection{_GAP}outcomes?)(?![a-z])",
    re.IGNORECASE,
)

_GLOSSARY = "docs/reference/glossary.md"

#: The glossary row whose last cell lists the phrases as aliases to avoid.
_ALIAS_ROW_PREFIX = "| **Ledger Admission** |"

#: Decision records are history (ADR-0127), so their bodies keep their words.
_EXCLUDED_DOCS_PREFIX = "docs/adr/"


def _rel(path: Path) -> str:
    return path.relative_to(_ROOT).as_posix()


def _without_alias_cell(text: str) -> str:
    """Blank the aliases-to-avoid cell of the **Ledger Admission** row.

    Only that cell is exempt: the row's definition cell is still scanned.
    Raises if the row is missing or no longer has the cell, so the exemption
    cannot silently outlive the row it was written for.
    """
    lines = text.split("\n")
    rows = [
        i for i, line in enumerate(lines) if line.startswith(_ALIAS_ROW_PREFIX)
    ]
    if len(rows) != 1:
        raise AssertionError(
            f"{_GLOSSARY}: expected one '{_ALIAS_ROW_PREFIX}' row, "
            f"found {len(rows)}"
        )
    cells = lines[rows[0]].split("|")
    # A table row starts and ends with "|", so the aliases cell is cells[-2].
    if len(cells) < 4 or cells[-1].strip():
        raise AssertionError(
            f"{_GLOSSARY}: the '{_ALIAS_ROW_PREFIX}' row no longer ends in an "
            "aliases-to-avoid cell"
        )
    cells[-2] = " " * len(cells[-2])
    lines[rows[0]] = "|".join(cells)
    return "\n".join(lines)


@functools.cache
def _scanned() -> tuple[tuple[str, str], ...]:
    """Every in-scope file as ``(relative path, text)``, computed once."""
    files: list[tuple[str, str]] = []
    for path, text in _corpus.all_docs():
        rel = _rel(path)
        if rel.startswith(_EXCLUDED_DOCS_PREFIX):
            continue
        files.append(
            (rel, _without_alias_cell(text) if rel == _GLOSSARY else text)
        )
    for path, text in _corpus.all_prose():
        files.append((_rel(path), text))
    for path, text in _corpus.all_sources(_ROOT / "vultron"):
        files.append((_rel(path), text))
    return tuple(files)


#: Every banned phrase ends in "assertion" or "outcome".  Plain substring
#: search finds those cheaply, and the case-insensitive regex then runs only on
#: a short window ending at each hit (the TB-13-007 prefilter, for text).
#: Dropping the first letter covers lower and title case, and the upper-case
#: fragments cover all caps, so nothing is case-folded.
_PREFILTER = ("ssertion", "SSERTION", "utcome", "UTCOME")

#: How far before a hit the first word may start: "rejection" plus a gap as
#: wide as a Python string split across deeply indented lines.
_WINDOW_BEFORE = 80
_WINDOW_AFTER = len("ssertions")


def _matches(text: str) -> list[re.Match[str]]:
    found: dict[int, re.Match[str]] = {}
    for fragment in _PREFILTER:
        hit = text.find(fragment)
        while hit != -1:
            start = max(0, hit - _WINDOW_BEFORE)
            # One character past the word, so the lookahead sees what follows.
            end = hit + _WINDOW_AFTER + 1
            for m in _BANNED.finditer(text, start, end):
                found.setdefault(m.start(), m)
            hit = text.find(fragment, hit + 1)
    return [found[k] for k in sorted(found)]


def _offenders(rel: str, text: str) -> list[str]:
    return [
        f"  {rel}:{text.count(chr(10), 0, m.start()) + 1}: "
        f"{' '.join(m.group().split())}"
        for m in _matches(text)
    ]


@pytest.mark.spec("CLP-02-012")
@pytest.mark.spec("DF-09-002")
def test_ledger_verdict_is_admitted_or_refused_everywhere():
    scanned = _scanned()
    offenders = [
        line for rel, text in scanned for line in _offenders(rel, text)
    ]

    assert offenders == [], (
        "These files describe the CASE_MANAGER's ledger verdict with the "
        "words reserved for the Accept and Reject activities. Say 'admitted' "
        "or 'refused' (CLP-02-012, glossary 'Ledger Admission'); a "
        "participant's Reject is a case event and is ledgered:\n"
        + "\n".join(offenders)
    )


@pytest.mark.spec("DF-09-009")
@pytest.mark.parametrize("prefix", ["specs/", "notes/", "docs/", "vultron/"])
def test_every_scanned_tree_has_files(prefix: str):
    """An empty tree would let the ratchet pass while checking nothing."""
    count = sum(1 for rel, _ in _scanned() if rel.startswith(prefix))
    assert count > 10, (
        f"Only {count} files scanned under {prefix}; the corpus probably "
        "no longer reaches that tree (DF-09-009)."
    )


def test_adr_bodies_are_not_scanned():
    assert not any(rel.startswith("docs/adr/") for rel, _ in _scanned())


def test_glossary_aliases_cell_still_declares_the_phrases():
    """The exemption covers a cell that really lists the banned phrases."""
    text = dict(_corpus.all_docs())[_ROOT / _GLOSSARY]
    assert _BANNED.search(text)
    assert not _BANNED.search(_without_alias_cell(text))


@pytest.mark.parametrize(
    "sample",
    [
        "Rejected assertions do not use up an index",
        "a canonical accepted assertion",
        "Rejection outcomes are logged",
        "the rejected\n    assertion is logged",
        "the rejection\n    # outcome of a guard",
        "an Accepted Assertion",
        "AN ACCEPTED ASSERTION",
        "a **rejected** assertion",
        "an _accepted_ assertion",
        '"the rejected "\n    "assertion is logged"',
        "a rejected-assertion path",
        '"the accepted "\n        f"assertion {x}"',
    ],
)
def test_matcher_catches_wrapped_and_cased_forms(sample: str):
    assert _BANNED.search(sample)
    assert _offenders("sample.md", sample), "the prefilter skipped it"


@pytest.mark.parametrize(
    "sample",
    [
        "a refused assertion",
        "an admitted assertion",
        "the participant's Reject is ledgered",
        "a rejected invitation",
        "unaccepted assertions",
        "a rejected assertional claim",
        "accepted assertionsfoo",
        "items accepted\n- assertion is a new bullet",
        "items rejected\n\n- assertion: a new paragraph",
        "the list is accepted\n1. assertion one",
        "Accept or Reject: the outcome",
        "last_accepted_hash and rejected_entry",
    ],
)
def test_matcher_ignores_the_admitted_refused_vocabulary(sample: str):
    assert not _BANNED.search(sample)
    assert not _offenders("sample.md", sample)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("| **Other** | x | y |", id="row-absent"),
        pytest.param(
            f"{_ALIAS_ROW_PREFIX} a | b |\n{_ALIAS_ROW_PREFIX} c | d |",
            id="row-duplicated",
        ),
        pytest.param(f"{_ALIAS_ROW_PREFIX} a | b", id="no-trailing-cell"),
    ],
)
def test_alias_cell_exemption_raises_when_row_is_gone_or_malformed(text: str):
    with pytest.raises(AssertionError):
        _without_alias_cell(text)


def test_definition_cell_is_still_scanned():
    row = (
        f"{_ALIAS_ROW_PREFIX} a rejection outcome sneaks in here | "
        "Accepted assertion, rejected assertion, rejection outcome |"
    )
    assert _BANNED.search(_without_alias_cell(row))
