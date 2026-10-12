"""Architecture ratchet: every ``SEMANTIC_REGISTRY`` entry has one primary page.

The page is declared on the entry itself (``SemanticEntry.page``, ADR-0128),
so the hand-typed ``ROW_SPECS`` page column that this ratchet used to check is
gone; ``ROW_SPECS`` is now derived from the entries.  The ratchet checks the
entries directly: every entry outside the dispatcher fallbacks names a known
page and appears on it, and the fallbacks name none (MSM-06-002).

This is a hard assertion rather than a ratchet integer ceiling: an entry
without a page is always wrong, and ``SemanticEntry`` already refuses one at
construction (MSM-08-001).  The checks here pin the registry-wide facts that
construction cannot see.
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

import re
from pathlib import Path

import pytest

from vultron.core.models.events.base import MessageSemantics
from vultron.metadata.msm import occasions as gen
from vultron.metadata.msm._mapping import (
    EXEMPTED_SEMANTICS,
    PAGE_SLUGS,
    ROW_SPECS,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import SemanticEntry

_FRAGMENTS = Path(__file__).parents[2] / gen.FRAGMENT_DIR
_MESSAGES = _FRAGMENTS.parent

_PAGED: list[SemanticEntry] = [
    e for e in SEMANTIC_REGISTRY if e.semantics not in EXEMPTED_SEMANTICS
]


@pytest.mark.spec("MSM-06-002")
def test_registry_holds_every_message_semantics_once():
    """Each ``MessageSemantics`` value has exactly one registry entry."""
    names = [e.semantics for e in SEMANTIC_REGISTRY]
    assert sorted(names) == sorted(MessageSemantics)


@pytest.mark.spec("MSM-06-002")
def test_every_non_exempt_entry_names_a_known_page():
    unknown = [
        f"{e.semantics.name}: {e.page!r}"
        for e in _PAGED
        if e.page is None or e.page.value not in PAGE_SLUGS
    ]
    assert unknown == []


@pytest.mark.spec("MSM-06-002")
def test_exempt_entries_name_no_page():
    paged = [
        e.semantics.name
        for e in SEMANTIC_REGISTRY
        if e.semantics in EXEMPTED_SEMANTICS and e.page is not None
    ]
    assert paged == []


@pytest.mark.spec("MSM-06-002")
@pytest.mark.parametrize("entry", _PAGED, ids=lambda e: e.semantics.name)
def test_entry_appears_on_its_designated_page(entry: SemanticEntry):
    """The entry's page includes the section of each of its occasions."""
    assert entry.page is not None
    page = (_MESSAGES / f"{entry.page.value}.md").read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    for occasion in entry.occasions:
        section = _FRAGMENTS / "sections" / f"{occasion.anchor}.md"
        directive = (
            f'include-markdown "./{section.relative_to(_MESSAGES).as_posix()}"'
        )
        assert directive in text, occasion.anchor


@pytest.mark.spec("MSM-06-002")
def test_row_specs_are_one_row_per_paged_entry():
    """``ROW_SPECS`` is derived: one row per non-exempt entry, its own page."""
    rows = {row.semantics: row.page for row in ROW_SPECS}
    assert len(rows) == len(ROW_SPECS)
    expected = {
        e.semantics: e.page.value for e in _PAGED if e.page is not None
    }
    assert rows == expected
