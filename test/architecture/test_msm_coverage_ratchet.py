"""Architecture ratchet: every ``SEMANTIC_REGISTRY`` entry has exactly one
primary page in the MSM mapping table.

AC-5: a ratchet test asserts every ``SEMANTIC_REGISTRY`` entry that is not
in ``EXEMPTED_SEMANTICS`` appears exactly once in ``ROW_SPECS``.

This test is intentionally a *hard* assertion (not a ratchet integer ceiling)
because the mapping table is maintained alongside the registry: adding a new
``SemanticEntry`` without a corresponding ``RowSpec`` is always wrong.
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

from collections import Counter

import pytest

from vultron.core.models.events.base import MessageSemantics
from vultron.metadata.msm._mapping import (
    EXEMPTED_SEMANTICS,
    ROW_SPECS,
    PAGE_SLUGS,
)
from vultron.semantic_registry import SEMANTIC_REGISTRY

# ---------------------------------------------------------------------------
# Pre-compute the coverage map once at module level (fast; no fixture needed).
# ---------------------------------------------------------------------------

_ALL_SEMANTICS: frozenset[MessageSemantics] = frozenset(MessageSemantics)
_REQUIRED_SEMANTICS: frozenset[MessageSemantics] = (
    _ALL_SEMANTICS - EXEMPTED_SEMANTICS
)
_ROW_SEMANTICS: list[MessageSemantics] = [row.semantics for row in ROW_SPECS]
_ROW_SEMANTICS_COUNTER: Counter = Counter(_ROW_SEMANTICS)
_ROW_SEMANTICS_SET: frozenset[MessageSemantics] = frozenset(_ROW_SEMANTICS)


@pytest.mark.spec("MSM-06-002")
def test_every_required_semantics_has_a_row():
    """Every non-exempted ``MessageSemantics`` value has at least one
    ``RowSpec`` in ``ROW_SPECS``.

    Failure here means a new ``SemanticEntry`` was added to
    ``SEMANTIC_REGISTRY`` without a corresponding entry in
    ``vultron/metadata/msm/_mapping.py``.
    """
    missing = sorted(
        s.name for s in _REQUIRED_SEMANTICS if s not in _ROW_SEMANTICS_SET
    )
    assert missing == [], (
        f"{len(missing)} MessageSemantics value(s) are in SEMANTIC_REGISTRY "
        f"but have no RowSpec:\n  " + "\n  ".join(missing)
    )


@pytest.mark.spec("MSM-06-002")
def test_every_row_semantics_is_a_known_value():
    """Every ``RowSpec.semantics`` is a valid ``MessageSemantics`` member.

    Failure means a typo or stale enum value in ``_mapping.py``.
    """
    for row in ROW_SPECS:
        assert (
            row.semantics in _ALL_SEMANTICS
        ), f"RowSpec references unknown semantics: {row.semantics!r}"


@pytest.mark.spec("MSM-06-002")
def test_every_row_page_is_a_known_slug():
    """Every ``RowSpec.page`` is one of the eight canonical page slugs."""
    for row in ROW_SPECS:
        assert (
            row.page in PAGE_SLUGS
        ), f"RowSpec for {row.semantics.name!r} has unknown page {row.page!r}"


@pytest.mark.spec("MSM-06-002")
def test_each_semantics_has_exactly_one_primary_page():
    """Each ``MessageSemantics`` value appears on at most one page.

    Multiple ``RowSpec`` entries for the same semantics are allowed (that is
    how expansion is expressed), but they MUST all share the same ``page``
    value — a semantics value cannot have two different primary pages.
    """
    page_for: dict[MessageSemantics, set[str]] = {}
    for row in ROW_SPECS:
        page_for.setdefault(row.semantics, set()).add(row.page)

    violations = [
        f"{sem.name}: pages={sorted(pages)}"
        for sem, pages in page_for.items()
        if len(pages) > 1
    ]
    assert violations == [], (
        "Some semantics values appear on more than one primary page:\n  "
        + "\n  ".join(violations)
    )


@pytest.mark.spec("MSM-06-002")
def test_registry_and_mapping_have_same_semantics_set():
    """The set of semantics in ``SEMANTIC_REGISTRY`` equals the set in
    ``ROW_SPECS`` union ``EXEMPTED_SEMANTICS``.

    This cross-check catches any drift between the two files: a new registry
    entry without a row, or a stale row for a deleted semantics value.
    """
    registry_semantics = frozenset(e.semantics for e in SEMANTIC_REGISTRY)
    mapping_semantics = _ROW_SEMANTICS_SET | EXEMPTED_SEMANTICS

    in_registry_not_mapping = sorted(
        s.name for s in registry_semantics - mapping_semantics
    )
    in_mapping_not_registry = sorted(
        s.name for s in mapping_semantics - registry_semantics
    )

    assert in_registry_not_mapping == [], (
        "In SEMANTIC_REGISTRY but not in ROW_SPECS (or EXEMPTED_SEMANTICS):\n  "
        + "\n  ".join(in_registry_not_mapping)
    )
    assert in_mapping_not_registry == [], (
        "In ROW_SPECS (or EXEMPTED_SEMANTICS) but not in SEMANTIC_REGISTRY:\n  "
        + "\n  ".join(in_mapping_not_registry)
    )
