"""Ratchet: MUST-tier requirements with no ``verification:``, pinned per kind.

MS-10-006 pins each kind's live count — ``MUST`` and ``MUST_NOT`` alike,
suppressed items included — to a ceiling equal to that count, so a backfill
must lower the ceiling and a new unverified requirement fails at once. Each
non-zero ceiling names the issue driving it to zero, and an entry at zero is
deleted so MS-10-007's hard error takes over.

The table lives in ``vultron/metadata/specs/verification.py``; ``spec-lint``
prints the same numbers (MS-10-005). To see which IDs a kind is counting::

    uv run spec-lint --list-unverified

Requirements: specs/meta-specifications.yaml MS-10-006, MS-10-007, MS-10-008.
"""

from __future__ import annotations

import re

import pytest

from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecFile, SpecKind
from vultron.metadata.specs.verification import (
    VERIFICATION_CEILINGS,
    VerificationCeiling,
    ceiling_mismatches,
    ownerless_ceilings,
    unverified_by_kind,
    zero_ceilings,
)

# ---------------------------------------------------------------------------
# The live corpus against the live table
# ---------------------------------------------------------------------------


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-10-006")
def test_live_unverified_counts_equal_their_ceilings(real_registry):
    """Both directions fail: above means a new unverified MUST-tier
    requirement (or an MS-10-008 relabel without its ``verification:``);
    below means a backfill that did not lower the ceiling."""
    problems = ceiling_mismatches(
        unverified_by_kind(real_registry), VERIFICATION_CEILINGS
    )
    assert problems == [], (
        "VERIFICATION_CEILINGS in vultron/metadata/specs/verification.py "
        "must equal the live count for every kind (MS-10-006). "
        "Run `uv run spec-lint --list-unverified` to see the IDs.\n"
        + "\n".join(problems)
    )


@pytest.mark.spec("MS-10-006")
def test_every_nonzero_ceiling_names_its_owner():
    problems = ownerless_ceilings(VERIFICATION_CEILINGS)
    assert problems == [], (
        "A non-zero ceiling needs the issue that owns driving it to zero "
        "(MS-10-006):\n" + "\n".join(problems)
    )


@pytest.mark.spec("MS-10-007")
def test_no_ceiling_entry_sits_at_zero():
    problems = zero_ceilings(VERIFICATION_CEILINGS)
    assert problems == [], "\n".join(problems)


def test_owner_references_are_github_issue_numbers():
    for entry in VERIFICATION_CEILINGS.values():
        for owner in entry.owners:
            assert re.fullmatch(r"#\d+", owner), owner


# ---------------------------------------------------------------------------
# Fixture corpora: prove each failure mode fires
# ---------------------------------------------------------------------------


def _registry(items) -> SpecRegistry:
    """A registry of ``(id, priority, kind, extra)`` items in one group."""
    return SpecRegistry(files=[SpecFile.model_validate(spec_file_data(items))])


_BASE_ITEMS = [
    ("TST-01-001", "MUST", "protocol", {}),
    ("TST-01-002", "MUST_NOT", "protocol", {}),
    ("TST-01-003", "MUST", "protocol", {"verification": "A test checks it."}),
    ("TST-01-004", "SHOULD_NOT", "protocol", {}),
    ("TST-01-005", "MUST_NOT", "process", {}),
]

_BASE_CEILINGS = {
    SpecKind.PROTOCOL: VerificationCeiling(2, ("#1",)),
    SpecKind.PROCESS: VerificationCeiling(1, ("#2",)),
}


@pytest.mark.spec("MS-10-006")
def test_count_covers_must_and_must_not_but_not_the_should_tier():
    reports = unverified_by_kind(_registry(_BASE_ITEMS))
    assert reports[SpecKind.PROTOCOL].ids == ["TST-01-001", "TST-01-002"]
    assert reports[SpecKind.PROCESS].ids == ["TST-01-005"]
    assert reports[SpecKind.ARCHITECTURE].count == 0
    assert reports[SpecKind.PROJECT].count == 0
    assert ceiling_mismatches(reports, _BASE_CEILINGS) == []


@pytest.mark.spec("MS-10-006")
def test_suppressed_item_is_still_counted():
    items = [
        *_BASE_ITEMS,
        (
            "TST-01-006",
            "MUST",
            "protocol",
            {"lint_suppress": ["must_without_verification"]},
        ),
    ]
    report = unverified_by_kind(_registry(items))[SpecKind.PROTOCOL]
    assert report.count == 3
    assert report.suppressed == frozenset({"TST-01-006"})
    problems = ceiling_mismatches(
        unverified_by_kind(_registry(items)), _BASE_CEILINGS
    )
    assert any("kind=protocol" in p and "above" in p for p in problems)


@pytest.mark.spec("MS-10-006")
def test_adding_an_unverified_must_raises_the_count_and_fails_the_ratchet():
    """The summary cannot hide a new one: the count rises and the pin trips."""
    before = unverified_by_kind(_registry(_BASE_ITEMS))
    assert ceiling_mismatches(before, _BASE_CEILINGS) == []
    after = unverified_by_kind(
        _registry([*_BASE_ITEMS, ("TST-01-006", "MUST_NOT", "process", {})])
    )
    assert after[SpecKind.PROCESS].count == before[SpecKind.PROCESS].count + 1
    problems = ceiling_mismatches(after, _BASE_CEILINGS)
    assert problems == [
        "kind=process: live count 2 is above the ceiling 1; set the ceiling "
        "to 2 (MS-10-006 pins it to the live count in either direction)"
    ]


@pytest.mark.spec("MS-10-006")
def test_backfill_without_lowering_the_ceiling_fails_the_ratchet():
    items = list(_BASE_ITEMS)
    items[1] = (
        "TST-01-002",
        "MUST_NOT",
        "protocol",
        {"verification": "Now checked."},
    )
    problems = ceiling_mismatches(
        unverified_by_kind(_registry(items)), _BASE_CEILINGS
    )
    assert len(problems) == 1
    assert "kind=protocol: live count 1 is below the ceiling 2" in problems[0]


@pytest.mark.spec("MS-10-007")
def test_unverified_items_in_a_kind_with_no_entry_are_reported():
    """A kind that reached zero and lost its entry cannot silently regrow."""
    ceilings = {SpecKind.PROTOCOL: VerificationCeiling(2, ("#1",))}
    problems = ceiling_mismatches(
        unverified_by_kind(_registry(_BASE_ITEMS)), ceilings
    )
    assert len(problems) == 1
    assert "kind=process: 1 unverified" in problems[0]
    assert "no ceiling entry" in problems[0]


@pytest.mark.spec("MS-10-006")
def test_ownerless_nonzero_ceiling_is_reported():
    ceilings = {SpecKind.PROTOCOL: VerificationCeiling(2)}
    assert ownerless_ceilings(ceilings) == [
        "kind=protocol: ceiling 2 names no owning issue"
    ]
    assert (
        ownerless_ceilings({SpecKind.PROTOCOL: VerificationCeiling(0)}) == []
    )


@pytest.mark.spec("MS-10-007")
def test_zero_ceiling_is_reported_for_deletion():
    problems = zero_ceilings(
        {SpecKind.PROJECT: VerificationCeiling(0, ("#9",))}
    )
    assert len(problems) == 1
    assert "kind=project" in problems[0]
    assert "MS-10-007" in problems[0]


@pytest.mark.spec("MS-10-008")
def test_relabel_without_verification_fails_the_destination_kind():
    """Moving an unverified MUST between kinds raises the destination's count
    above its ceiling (and drops the source below), so the relabel must carry
    its verification: with it."""
    items = list(_BASE_ITEMS)
    items[0] = ("TST-01-001", "MUST", "process", {})
    problems = ceiling_mismatches(
        unverified_by_kind(_registry(items)), _BASE_CEILINGS
    )
    assert any(
        "kind=process: live count 2 is above the ceiling 1" in p
        for p in problems
    )
    assert any(
        "kind=protocol: live count 1 is below the ceiling 2" in p
        for p in problems
    )
