"""Per-requirement ``verification_debt`` markers (MS-10-003, MS-10-005..008).

Every MUST-tier requirement with no ``verification:`` carries a marker naming
the issue that owns verifying it. Each rule here is judged one requirement at
a time, so no committed count exists for concurrent PRs to race on (#3984).

The owner table lives in ``vultron/metadata/specs/verification.py``. To see the
marked IDs::

    uv run spec-lint --list-unverified
"""

from __future__ import annotations

import json
import subprocess

import pytest
import yaml
from pydantic import TypeAdapter, ValidationError

import vultron.metadata.specs.verification as verification_module
from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    IssueRefStr,
    SpecFile,
    SpecKind,
    StatementSpec,
)
from vultron.metadata.specs.verification import (
    VERIFICATION_DEBT_OWNERS,
    check_closing_pr,
    check_verification_coverage,
    closed_debt_owners,
    closing_pr_problems,
    debt_by_kind,
    debt_owner_refs,
    gh_issue_state,
    gh_pr_closing_issues,
    idle_owners,
    issue_number,
    verification_problems,
)

_ISSUE_REF: TypeAdapter[str] = TypeAdapter(IssueRefStr)

# ---------------------------------------------------------------------------
# The live corpus against the live table
# ---------------------------------------------------------------------------


@pytest.mark.spec_corpus
@pytest.mark.spec("MS-10-006")
def test_live_corpus_has_no_per_item_verification_failure(real_registry):
    problems = verification_problems(real_registry, VERIFICATION_DEBT_OWNERS)
    assert problems == [], (
        "Each MUST-tier requirement needs a verification: field or a "
        "verification_debt marker naming an owner of its kind (MS-10-006):\n"
        + "\n".join(problems)
    )


def test_owner_table_entries_are_non_empty_issue_references():
    """Validated with the same type the schema uses for a marker."""
    for kind, owners in VERIFICATION_DEBT_OWNERS.items():
        assert owners, f"kind={kind.value}: delete an empty entry (MS-10-007)"
        for owner in owners:
            _ISSUE_REF.validate_python(owner)


# ---------------------------------------------------------------------------
# Fixture corpora: prove each failure mode fires
# ---------------------------------------------------------------------------


def _registry(items) -> SpecRegistry:
    """A registry of ``(id, priority, kind, extra)`` items in one group."""
    return SpecRegistry(files=[SpecFile.model_validate(spec_file_data(items))])


_OWNERS = {
    SpecKind.PROTOCOL: frozenset({"#1"}),
    SpecKind.PROCESS: frozenset({"#2", "#3"}),
}

_CLEAN_ITEMS = [
    ("TST-01-001", "MUST", "protocol", {"verification_debt": "#1"}),
    ("TST-01-002", "MUST_NOT", "protocol", {"verification_debt": "#1"}),
    ("TST-01-003", "MUST", "protocol", {"verification": "A test checks it."}),
    ("TST-01-004", "SHOULD_NOT", "protocol", {}),
    ("TST-01-005", "MUST_NOT", "process", {"verification_debt": "#3"}),
    ("TST-01-006", "MAY", "architecture", {}),
]


@pytest.mark.spec("MS-10-006")
def test_clean_fixture_has_no_problems():
    assert verification_problems(_registry(_CLEAN_ITEMS), _OWNERS) == []


@pytest.mark.spec("MS-10-003")
@pytest.mark.spec("MS-10-006")
@pytest.mark.parametrize("priority", ["MUST", "MUST_NOT"])
def test_must_tier_with_neither_field_fails(priority):
    problems = verification_problems(
        _registry([("TST-01-001", priority, "protocol", {})]), _OWNERS
    )
    assert len(problems) == 1
    assert problems[0].startswith("TST-01-001: priority")
    assert "MS-10-003" in problems[0]


@pytest.mark.spec("MS-10-006")
def test_must_tier_with_both_fields_fails_as_stale():
    """A sibling PR verified it; the marker is now a lie."""
    items = [
        (
            "TST-01-001",
            "MUST",
            "protocol",
            {"verification": "Now checked.", "verification_debt": "#1"},
        )
    ]
    problems = verification_problems(_registry(items), _OWNERS)
    assert len(problems) == 1
    assert "stale" in problems[0]
    assert "TST-01-001" in problems[0]


@pytest.mark.spec("MS-10-006")
@pytest.mark.parametrize("priority", ["SHOULD", "SHOULD_NOT", "MAY"])
def test_marker_below_the_must_tier_fails(priority):
    items = [("TST-01-001", priority, "protocol", {"verification_debt": "#1"})]
    problems = verification_problems(_registry(items), _OWNERS)
    assert len(problems) == 1
    assert "below the MUST tier" in problems[0]


@pytest.mark.spec("MS-10-008")
def test_relabel_that_keeps_the_old_kinds_marker_fails():
    """TST-01-001 moved from protocol to process but still names #1."""
    items = [("TST-01-001", "MUST", "process", {"verification_debt": "#1"})]
    problems = verification_problems(_registry(items), _OWNERS)
    assert len(problems) == 1
    assert "does not own kind=process" in problems[0]
    assert "#2, #3" in problems[0]
    assert "MS-10-008" in problems[0]


@pytest.mark.spec("MS-10-007")
@pytest.mark.parametrize("priority", ["MUST", "MUST_NOT"])
def test_marker_on_a_kind_with_no_owner_entry_fails(priority):
    items = [
        ("TST-01-001", priority, "architecture", {"verification_debt": "#1"})
    ]
    problems = verification_problems(_registry(items), _OWNERS)
    assert len(problems) == 1
    assert "kind=architecture has no verification backlog left" in problems[0]
    assert "MS-10-007" in problems[0]


@pytest.mark.spec("MS-10-007")
def test_verified_items_of_a_finished_kind_pass():
    items = [
        ("TST-01-001", "MUST", "architecture", {"verification": "A test."}),
        (
            "TST-01-002",
            "MUST_NOT",
            "architecture",
            {"verification": "A test."},
        ),
    ]
    assert verification_problems(_registry(items), _OWNERS) == []


def test_every_problem_on_one_item_is_reported():
    """A stale marker that also names the wrong owner reports both (EH-07-001)."""
    items = [
        (
            "TST-01-001",
            "MUST",
            "process",
            {"verification": "Checked.", "verification_debt": "#1"},
        )
    ]
    problems = verification_problems(_registry(items), _OWNERS)
    assert len(problems) == 2


# ---------------------------------------------------------------------------
# Schema: the marker's form
# ---------------------------------------------------------------------------


def _statement(**extra) -> StatementSpec:
    return StatementSpec.model_validate(
        {
            "id": "TST-01-001",
            "priority": "MUST",
            "kind": "protocol",
            "statement": "TST-01-001 MUST do it",
            **extra,
        }
    )


@pytest.mark.parametrize("bad", ["12", "#", "#0", "#01", "#12, #13", "GH-12"])
def test_marker_must_be_one_issue_reference(bad):
    with pytest.raises(ValidationError):
        _statement(verification_debt=bad)


def test_unquoted_marker_is_a_yaml_comment_and_fails_the_item():
    """``verification_debt: #12`` loads as null, so the item reads as having
    neither field — loud, not silently accepted."""
    loaded = yaml.safe_load("verification_debt: #12\n")
    assert loaded == {"verification_debt": None}
    spec = _statement(**loaded)
    registry = _registry([("TST-01-001", "MUST", "protocol", loaded)])
    assert spec.verification_debt is None
    assert "MS-10-003" in verification_problems(registry, _OWNERS)[0]


def test_marker_is_separate_from_tracking_issue():
    spec = _statement(verification_debt="#12", tracking_issue="#99")
    assert (spec.verification_debt, spec.tracking_issue) == ("#12", "#99")


# ---------------------------------------------------------------------------
# Summary (MS-10-005)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MS-10-005")
def test_debt_by_kind_groups_markers_and_tallies_owners():
    items = [
        *_CLEAN_ITEMS,
        ("TST-01-007", "MUST", "process", {"verification_debt": "#2"}),
        ("TST-01-008", "MUST", "process", {"verification_debt": "#3"}),
    ]
    reports = debt_by_kind(_registry(items))
    assert set(reports) == set(SpecKind)
    assert list(reports[SpecKind.PROTOCOL].markers) == [
        "TST-01-001",
        "TST-01-002",
    ]
    assert reports[SpecKind.PROCESS].by_owner == {"#2": 1, "#3": 2}
    assert reports[SpecKind.ARCHITECTURE].count == 0


@pytest.mark.spec("MS-10-005")
def test_summary_names_every_owner_including_those_at_zero():
    _, lines = check_verification_coverage(_registry(_CLEAN_ITEMS), _OWNERS)
    process = next(ln for ln in lines if "kind=process" in ln)
    assert "1 MUST-tier requirement(s)" in process
    assert "(#2: 0, #3: 1)" in process
    assert not any("kind=architecture" in ln for ln in lines)


@pytest.mark.spec("MS-10-005")
def test_listing_is_opt_in_and_names_each_marker():
    registry = _registry(_CLEAN_ITEMS)
    _, default = check_verification_coverage(registry, _OWNERS)
    _, listed = check_verification_coverage(
        registry, _OWNERS, list_unverified=True
    )
    assert not any("TST-01-001" in ln for ln in default)
    assert "    TST-01-001  #1" in listed
    assert "    TST-01-005  #3" in listed


@pytest.mark.spec("MS-10-005")
def test_summary_does_not_depend_on_any_committed_count():
    """Verifying one item lowers the printed number with no other edit."""
    registry = _registry(_CLEAN_ITEMS)
    _, before = check_verification_coverage(registry, _OWNERS)
    items = list(_CLEAN_ITEMS)
    items[0] = ("TST-01-001", "MUST", "protocol", {"verification": "Now."})
    errors, after = check_verification_coverage(_registry(items), _OWNERS)
    assert errors == []
    assert any("kind=protocol: 2 MUST-tier" in ln for ln in before)
    assert any("kind=protocol: 1 MUST-tier" in ln for ln in after)


@pytest.mark.spec("MS-10-007")
def test_owner_no_marker_names_is_reported_not_failed():
    """#2 owns process but no marker names it: a warning, never an error, so
    two PRs finishing one owner's backlog cannot turn main red merged."""
    errors, lines = check_verification_coverage(
        _registry(_CLEAN_ITEMS), _OWNERS
    )
    assert errors == []
    warnings = [ln for ln in lines if ln.startswith("[WARN]")]
    assert len(warnings) == 1
    assert "no marker names owner #2" in warnings[0]
    assert "MS-10-007" in warnings[0]


def test_idle_owners_lists_every_unnamed_owner_in_issue_order():
    reports = debt_by_kind(_registry(_CLEAN_ITEMS))
    owners = {SpecKind.PROJECT: frozenset({"#10", "#9"})}
    lines = idle_owners(reports, owners)
    assert len(lines) == 2
    assert "owner #9;" in lines[0]
    assert "owner #10;" in lines[1]


def test_issue_number_reads_the_reference():
    assert issue_number("#3612") == 3612


# ---------------------------------------------------------------------------
# Open-owner check (MS-10-006, CI)
# ---------------------------------------------------------------------------


def test_debt_owner_refs_covers_markers_and_table_entries():
    items = [("TST-01-001", "MUST", "process", {"verification_debt": "#7"})]
    assert debt_owner_refs(_registry(items), _OWNERS) == {
        "#1",
        "#2",
        "#3",
        "#7",
    }


@pytest.mark.spec("MS-10-006")
def test_closed_owner_fails_and_open_owner_passes():
    states = {"#1": "OPEN", "#2": "CLOSED", "#10": "OPEN"}
    errors = closed_debt_owners(states, states.__getitem__)
    assert errors == [
        "verification_debt owner #2 is CLOSED: an unverified requirement "
        "must name an open owning issue (MS-10-006); verify the items that "
        "cite it, or re-point them and the owner table at the issue that "
        "took the work over"
    ]


@pytest.mark.spec("MS-10-006")
@pytest.mark.parametrize(
    "exc",
    [
        FileNotFoundError("gh"),
        subprocess.CalledProcessError(1, ["gh"]),
        KeyError("state"),
    ],
)
def test_lookup_failure_is_an_error_not_a_pass(exc):
    def broken(ref: str) -> str:
        raise exc

    errors = closed_debt_owners({"#4"}, broken)
    assert len(errors) == 1
    assert errors[0].startswith("verification_debt owner #4: could not read")


def test_closed_debt_owners_defaults_to_the_gh_lookup(monkeypatch):
    monkeypatch.setattr(
        verification_module, "gh_issue_state", lambda ref: "CLOSED"
    )
    assert "#5 is CLOSED" in closed_debt_owners({"#5"})[0]


def test_gh_issue_state_asks_gh_for_the_issue_number(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps({"state": "OPEN"}), stderr=""
        )

    monkeypatch.setattr(verification_module.subprocess, "run", fake_run)
    assert gh_issue_state("#3612") == "OPEN"
    assert calls == [["gh", "issue", "view", "3612", "--json", "state"]]


# ---------------------------------------------------------------------------
# Closing-PR check (MS-10-006, MS-10-007)
# ---------------------------------------------------------------------------


@pytest.mark.spec("MS-10-006")
def test_pr_closing_an_owner_that_markers_still_name_fails():
    errors = closing_pr_problems(_registry(_CLEAN_ITEMS), _OWNERS, {"#1"})
    assert len(errors) == 1
    assert errors[0].startswith("this PR closes #1, but 2 requirement(s)")


@pytest.mark.spec("MS-10-007")
def test_pr_closing_an_idle_owner_must_also_remove_it_from_the_table():
    """#2 owns process but no marker names it: closing it is fine only once
    the table entry goes in the same PR."""
    errors = closing_pr_problems(_registry(_CLEAN_ITEMS), _OWNERS, {"#2"})
    assert errors == [
        "this PR closes #2, which no marker names any more; remove it from "
        "VERIFICATION_DEBT_OWNERS in this PR (MS-10-007)"
    ]
    finished = {**_OWNERS, SpecKind.PROCESS: frozenset({"#3"})}
    assert closing_pr_problems(_registry(_CLEAN_ITEMS), finished, {"#2"}) == []


def test_pr_closing_unrelated_issues_passes():
    registry = _registry(_CLEAN_ITEMS)
    assert closing_pr_problems(registry, _OWNERS, {"#99", "#100"}) == []
    assert closing_pr_problems(registry, _OWNERS, set()) == []


@pytest.mark.spec("MS-10-006")
@pytest.mark.parametrize(
    "exc",
    [FileNotFoundError("gh"), subprocess.CalledProcessError(1, ["gh"])],
)
def test_closing_pr_lookup_failure_is_an_error(exc):
    def broken(pr: int) -> set[str]:
        raise exc

    errors = check_closing_pr(_registry(_CLEAN_ITEMS), _OWNERS, 42, broken)
    assert len(errors) == 1
    assert errors[0].startswith("could not read the issues PR #42 closes")


def test_check_closing_pr_defaults_to_the_gh_lookup(monkeypatch):
    monkeypatch.setattr(
        verification_module, "gh_pr_closing_issues", lambda pr: {"#1"}
    )
    errors = check_closing_pr(_registry(_CLEAN_ITEMS), _OWNERS, 42)
    assert "this PR closes #1" in errors[0]


def test_gh_pr_closing_issues_reads_closing_references(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        payload = {"closingIssuesReferences": [{"number": 7}, {"number": 12}]}
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(verification_module.subprocess, "run", fake_run)
    assert gh_pr_closing_issues(42) == {"#7", "#12"}
    assert calls == [
        ["gh", "pr", "view", "42", "--json", "closingIssuesReferences"]
    ]
