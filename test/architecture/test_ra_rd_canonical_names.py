"""Regression: RA and RD must use 'Report/Case Accepted' / 'Report/Case Deferred' in key reference docs.

The spec entries MSM-01-004 and MSM-01-005 use the case-qualified names because
engaging/deferring is a case-participation decision (`Join`/`Ignore` VulnerabilityCase),
not a report-validity judgment.  Every key reference page must agree.

See: GitHub issue #3467.
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

from pathlib import Path

import pytest

from test.architecture import _corpus

_REPO = Path(__file__).parents[2]

_KEY_REFS = [
    _REPO / "docs/reference/formal_protocol/messages.md",
    _REPO / "docs/reference/quick_reference.md",
    _REPO / "docs/reference/glossary.md",
    _REPO / "docs/_acronyms/index.md",
]


@pytest.mark.parametrize("path", _KEY_REFS, ids=lambda p: p.name)
def test_ra_name_is_report_case_accepted(path: Path) -> None:
    assert "Report/Case Accepted" in path.read_text(), (
        f"{path.relative_to(_REPO)}: RA must be named 'Report/Case Accepted' "
        "(MSM-01-005 — acceptance is a case-participation decision)"
    )


@pytest.mark.parametrize("path", _KEY_REFS, ids=lambda p: p.name)
def test_rd_name_is_report_case_deferred(path: Path) -> None:
    assert "Report/Case Deferred" in path.read_text(), (
        f"{path.relative_to(_REPO)}: RD must be named 'Report/Case Deferred' "
        "(MSM-01-004 — deferral is a case-participation decision)"
    )


#: Pages allowed to contain the bare alias, and why.  The glossary *declares*
#: the aliases to avoid, so the strings have to appear there.
_ALIAS_DECLARED_IN = {
    "docs/reference/glossary.md": "the 'Aliases to avoid' column"
}

#: Trees outside the style guide's scope (DF-09-001) or frozen by definition.
_EXEMPT_PREFIXES = ("docs/adr/archived/",)


def _docs_pages() -> list[tuple[str, str]]:
    """Every in-scope ``docs/`` page as ``(relative path, text)``.

    Routed through the shared corpus rather than globbing, so this ratchet uses
    the same import-time cache as its siblings (TB-13-003).
    """
    return [
        (str(path.relative_to(_corpus.REPO_ROOT)), text)
        for path, text in _corpus.all_docs()
        if not str(path.relative_to(_corpus.REPO_ROOT)).startswith(
            _EXEMPT_PREFIXES
        )
    ]


def test_bare_ra_rd_aliases_appear_nowhere_in_docs():
    """The deprecated alias must not reappear anywhere under ``docs/``.

    The four presence checks above only assert the canonical name is *present*
    on four reference pages. They cannot see a page that uses the bare alias and
    is not on the list — which is exactly what happened in #3458: a how-to guide
    introduced "Report Accepted (RA)" in the same window #3467 was deprecating
    it, `git` merged the two cleanly because they touched different files, and
    nothing failed. The glossary would then have listed the alias as one to avoid
    while a guide used it (DF-09-002).

    Presence on a list is the weaker assertion; absence across the corpus is the
    one that holds. Scanning the tree rather than a list means a page added later
    is covered the day it lands.
    """
    offenders: list[str] = []
    pages = _docs_pages()
    for rel, text in pages:
        if rel in _ALIAS_DECLARED_IN:
            continue
        for lineno, line in enumerate(text.split("\n"), 1):
            # "Report/Case Accepted" contains "Case Accepted", never
            # "Report Accepted", so a plain substring test is unambiguous.
            for alias in ("Report Accepted", "Report Deferred"):
                if alias in line:
                    offenders.append(f"  {rel}:{lineno}: {alias}")

    assert offenders == [], (
        "These pages use a deprecated RA/RD alias. The canonical names are "
        "'Report/Case Accepted' and 'Report/Case Deferred' (MSM-01-004, "
        "MSM-01-005); the glossary lists the bare forms under 'Aliases to "
        "avoid':\n" + "\n".join(offenders)
    )
    assert len(pages) > 100, (
        f"Only {len(pages)} docs pages scanned, so this gate is checking almost "
        "nothing. The docs/ tree layout has probably changed (DF-09-009)."
    )
