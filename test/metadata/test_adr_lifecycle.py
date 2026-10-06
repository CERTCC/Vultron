"""Tests for the ADR lifecycle epochs and their checks (MS-14-007, MS-14-008)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pytest

from vultron.metadata.adr.lifecycle import (
    AdrEpoch,
    edit_faults,
    epoch_for,
    hardened_adrs,
    status_epoch_fault,
    verified_dependents,
)
from vultron.metadata.adr.schema import AdrFrontmatter

TODAY = dt.date(2026, 10, 20)


@dataclass
class _Spec:
    adr: list[str] | None
    verification: str | None


def _fm(status: str, updated: dt.date, **extra: object) -> AdrFrontmatter:
    return AdrFrontmatter.model_validate(
        {
            "status": status,
            "created": updated,
            "updated": updated,
            "revision": 1,
            **extra,
        }
    )


@pytest.mark.parametrize(
    "age_days, epoch",
    [
        (0, AdrEpoch.PROPOSED),
        (2, AdrEpoch.PROPOSED),
        (3, AdrEpoch.PROVISIONAL),
        (9, AdrEpoch.PROVISIONAL),
        (10, AdrEpoch.SETTLED),
        (400, AdrEpoch.SETTLED),
    ],
)
def test_epoch_boundaries(age_days: int, epoch: AdrEpoch) -> None:
    assert epoch_for(TODAY - dt.timedelta(days=age_days), TODAY) is epoch


@pytest.mark.parametrize(
    "status, age_days, faulty",
    [
        ("proposed", 1, False),
        ("proposed", 5, True),
        ("accepted-provisional", 5, False),
        ("accepted-provisional", 1, True),
        ("accepted", 10, False),
        ("accepted", 9, True),
        ("rejected", 0, False),
        ("deprecated", 0, False),
    ],
)
def test_status_must_agree_with_epoch(
    status: str, age_days: int, faulty: bool
) -> None:
    extra = {"superseded_by": "0001-x.md"} if status == "deprecated" else {}
    fm = _fm(status, TODAY - dt.timedelta(days=age_days), **extra)
    assert (status_epoch_fault("0001-x.md", fm, TODAY) is not None) is faulty


def test_status_override_lets_disagreement_stand() -> None:
    fm = _fm(
        "accepted",
        TODAY - dt.timedelta(days=1),
        status_override="a merged implementation hardened it",
    )
    assert status_epoch_fault("0001-x.md", fm, TODAY) is None


def test_lifecycle_fields_are_required() -> None:
    with pytest.raises(ValueError):
        AdrFrontmatter.model_validate({"status": "accepted"})


def test_updated_before_created_is_rejected() -> None:
    with pytest.raises(ValueError, match="before 'created'"):
        AdrFrontmatter.model_validate(
            {
                "status": "accepted",
                "created": "2026-01-02",
                "updated": "2026-01-01",
                "revision": 1,
            }
        )


def _adr(
    status: str,
    updated: str,
    outcome: str = "Chosen option: A.",
    options: str = "A or B.",
    extra_fm: str = "",
    tail: str = "",
) -> str:
    return (
        f"---\nstatus: {status}\ncreated: 2026-01-01\nupdated: {updated}\n"
        f"revision: 1\n{extra_fm}---\n# T\n\n## Considered Options\n\n"
        f"{options}\n\n## Decision Outcome\n\n{outcome}\n\n"
        f"## Consequences\n\nSome.\n{tail}"
    )


OLD = _adr("accepted", "2026-01-01")


def test_editing_a_decision_section_of_a_settled_adr_needs_amendment() -> None:
    new = _adr("accepted", "2026-01-01", outcome="Chosen option: B.")
    faults = edit_faults("0001-x.md", OLD, new, TODAY)
    assert len(faults) == 1
    assert "Decision Outcome" in faults[0]


def test_considered_options_edit_is_also_refused() -> None:
    new = _adr("accepted", "2026-01-01", options="A, B or C.")
    assert "Considered Options" in edit_faults("x", OLD, new, TODAY)[0]


def test_dated_amendment_permits_decision_section_edit() -> None:
    new = _adr(
        "accepted",
        "2026-01-01",
        outcome="Chosen option: A, with B.\n\n### Amendment 2026-10-20\n\nQuote.",
    )
    assert edit_faults("x", OLD, new, TODAY) == []


def test_undated_amendment_heading_does_not_count() -> None:
    new = _adr(
        "accepted",
        "2026-01-01",
        outcome="Chosen option: B.\n\n### Amendment\n\nNo date.",
    )
    assert len(edit_faults("x", OLD, new, TODAY)) == 1


def test_editorial_edit_elsewhere_is_allowed() -> None:
    new = _adr("accepted", "2026-01-01", tail="\nAn annotation.\n")
    assert edit_faults("x", OLD, new, TODAY) == []


def test_bumping_updated_outside_epoch_one_needs_override() -> None:
    new = _adr("accepted", "2026-10-20")
    faults = edit_faults("x", OLD, new, TODAY)
    assert len(faults) == 1
    assert "status_override" in faults[0]


def test_bumping_updated_with_override_is_allowed() -> None:
    new = _adr(
        "accepted",
        "2026-10-20",
        extra_fm="status_override: human reviewed the edit\n",
    )
    assert edit_faults("x", OLD, new, TODAY) == []


def test_bumping_updated_in_epoch_one_is_free() -> None:
    old = _adr("proposed", "2026-10-19")
    new = _adr("proposed", "2026-10-20", outcome="Chosen option: B.")
    assert edit_faults("x", old, new, TODAY) == []


def test_provisional_body_edit_without_bump_is_not_this_checks_concern() -> (
    None
):
    old = _adr("accepted-provisional", "2026-10-15")
    new = _adr("accepted-provisional", "2026-10-15", outcome="B.")
    assert edit_faults("x", old, new, TODAY) == []


def test_malformed_frontmatter_is_left_to_the_loader() -> None:
    assert edit_faults("x", OLD, "---\nstatus: nonsense\n---\n", TODAY) == []


def test_hardened_reports_unsettled_adr_with_tested_dependents() -> None:
    registry = {
        "docs/adr/0120-x.md": _fm("proposed", TODAY),
        "docs/adr/0121-y.md": _fm("accepted", TODAY - dt.timedelta(days=99)),
        "docs/adr/0122-z.md": _fm("proposed", TODAY),
    }
    out = hardened_adrs(
        registry, {"0120": ["A-01-001"], "0121": ["A-01-002"]}, TODAY
    )
    assert out == {"docs/adr/0120-x.md": ["A-01-001"]}


def test_verified_dependents_needs_an_existing_test_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_a.py").write_text("")
    specs = {
        "A-01-001": _Spec(
            adr=["ADR-0120"], verification="`test/test_a.py` checks it"
        ),
        "A-01-002": _Spec(
            adr=["ADR-0120"], verification="`test/test_missing.py` checks it"
        ),
        "A-01-003": _Spec(adr=["ADR-0120"], verification=None),
        "A-01-004": _Spec(adr=None, verification="`test/test_a.py`"),
    }
    assert verified_dependents(specs, tmp_path) == {"0120": ["A-01-001"]}
