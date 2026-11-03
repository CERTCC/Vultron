"""Tests for vultron.metadata.specs.lint.driver: clean runs, the
verification_debt checks and CLI flags (MS-10-005..008), and the cited
story-page check it wires in (TRACE-03-001).
"""

import sys

import pytest

import vultron.metadata.specs.lint.driver as lint_module
import vultron.metadata.specs.verification.owners as verification_module
from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.conftest import spec_file_data
from test.metadata.specs.lint._helpers import (
    _make_adr_dir,
    _minimal_spec,
    _minimal_spec_no_stories,
    _write_dated_adr,
)
from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.schema import SpecKind

# ---------------------------------------------------------------------------
# Clean cases
# ---------------------------------------------------------------------------


def test_lint_clean_dir(tmp_path, capsys):
    write_yaml(tmp_path, _minimal_spec())
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_lint_empty_dir(tmp_path):
    result = lint(tmp_path)
    assert result == 0


# ---------------------------------------------------------------------------
# MS-10-005 .. MS-10-008: MUST-tier requirements and verification_debt markers
# ---------------------------------------------------------------------------


def _verification_corpus(items):
    """Rows with tags and a story, so only verification: is under test."""
    rows = [
        (
            spec_id,
            priority,
            kind,
            {"tags": ["testing"], "stories": ["story_2022_001"], **extra},
        )
        for spec_id, priority, kind, extra in items
    ]
    return spec_file_data(rows)


_MIXED_ITEMS = [
    ("TST-01-001", "MUST", "protocol", {"verification_debt": "#1"}),
    ("TST-01-002", "MUST_NOT", "protocol", {"verification_debt": "#1"}),
    ("TST-01-003", "MUST", "protocol", {"verification": "Checked by a test."}),
    ("TST-01-004", "MUST_NOT", "process", {"verification_debt": "#2"}),
    ("TST-01-005", "SHOULD", "process", {}),
    ("TST-01-006", "SHOULD_NOT", "architecture", {}),
    ("TST-01-007", "MAY", "project", {}),
]


_MIXED_OWNERS = {
    SpecKind.PROTOCOL: frozenset({"#1"}),
    SpecKind.PROCESS: frozenset({"#2"}),
}


def _summary_lines(out):
    return [ln for ln in out.splitlines() if "verification_debt kind=" in ln]


@pytest.mark.spec("MS-10-005")
@pytest.mark.spec("MS-10-019")
def test_lint_one_summary_line_per_kind_computed_from_markers(
    tmp_path, capsys
):
    """MUST and MUST_NOT both count; one line per kind, tallied by owner."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    result = lint(tmp_path, debt_owners=_MIXED_OWNERS)
    captured = capsys.readouterr()
    assert result == 0
    lines = _summary_lines(captured.out)
    assert len(lines) == 2
    protocol = next(ln for ln in lines if "kind=protocol" in ln)
    process = next(ln for ln in lines if "kind=process" in ln)
    assert "2 MUST-tier requirement(s)" in protocol
    assert "(#1: 2)" in protocol
    assert "1 MUST-tier requirement(s)" in process
    assert "(#2: 1)" in process


@pytest.mark.spec("MS-10-020")
def test_lint_default_output_has_no_per_item_unverified_lines(
    tmp_path, capsys
):
    """No per-ID lines unless asked for."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    lint(tmp_path, debt_owners=_MIXED_OWNERS)
    out = capsys.readouterr().out
    assert "TST-01-001" not in out
    assert "TST-01-002" not in out
    assert "TST-01-004" not in out


@pytest.mark.spec("MS-10-020")
def test_lint_list_unverified_prints_ids_under_their_kind(tmp_path, capsys):
    """The opt-in flag lists marked IDs; verified and SHOULD-tier ones stay out."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    lint(tmp_path, debt_owners=_MIXED_OWNERS, list_unverified=True)
    out = capsys.readouterr().out
    assert "TST-01-004" in out
    assert "TST-01-003" not in out  # verified
    assert "TST-01-005" not in out  # SHOULD tier
    assert "TST-01-006" not in out  # SHOULD tier
    assert "TST-01-007" not in out  # MAY
    # IDs sit under their kind's summary line, each with its marker.
    lines = out.splitlines()
    protocol_at = next(
        i for i, ln in enumerate(lines) if "kind=protocol" in ln
    )
    assert lines[protocol_at + 1].split() == ["TST-01-001", "#1"]
    assert lines[protocol_at + 2].split() == ["TST-01-002", "#1"]


@pytest.mark.spec("MS-10-005")
def test_lint_kind_with_owner_entry_prints_its_line_even_at_zero_markers(
    tmp_path, capsys
):
    """A kind with an owner entry but no markers still gets its line, so a
    finished backlog is visible; a kind with neither prints nothing."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    owners = {**_MIXED_OWNERS, SpecKind.ARCHITECTURE: frozenset({"#3"})}
    lint(tmp_path, debt_owners=owners)
    lines = _summary_lines(capsys.readouterr().out)
    assert any(
        "kind=architecture: 0 MUST-tier" in ln and "(#3: 0)" in ln
        for ln in lines
    )
    assert not any("kind=project" in ln for ln in lines)


@pytest.mark.parametrize("priority", ["SHOULD", "SHOULD_NOT", "MAY"])
def test_lint_should_tier_without_verification_is_clean(
    tmp_path, capsys, priority
):
    """Only the MUST tier owes a verification: field (MS-10-003)."""
    write_yaml(
        tmp_path,
        _verification_corpus([("TST-01-001", priority, "protocol", {})]),
    )
    result = lint(tmp_path, debt_owners={})
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err
    assert _summary_lines(captured.out) == []


@pytest.mark.spec("MS-10-006")
@pytest.mark.spec("MS-10-022")
@pytest.mark.parametrize("priority", ["MUST", "MUST_NOT"])
def test_lint_unmarked_unverified_must_tier_is_hard_error(
    tmp_path, capsys, priority
):
    """With an owner for the kind available, an item still fails until it
    carries either verification: or its own marker."""
    write_yaml(
        tmp_path,
        _verification_corpus([("TST-01-001", priority, "protocol", {})]),
    )
    result = lint(tmp_path, debt_owners=_MIXED_OWNERS)
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "MS-10-003" in captured.err


@pytest.mark.spec("MS-10-026")
@pytest.mark.parametrize("priority", ["MUST", "MUST_NOT"])
def test_lint_marker_on_a_kind_with_no_owner_entry_is_hard_error(
    tmp_path, capsys, priority
):
    """A kind whose backlog is finished has no owner entry; a marker on it is
    then a hard error, so the kind cannot regrow debt."""
    write_yaml(
        tmp_path,
        _verification_corpus(
            [("TST-01-001", priority, "protocol", {"verification_debt": "#1"})]
        ),
    )
    result = lint(tmp_path, debt_owners={})
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "MS-10-026" in captured.err


@pytest.mark.spec("MS-10-026")
def test_lint_verified_must_tier_passes_without_owner_entry(tmp_path, capsys):
    """Once a kind is finished, verified MUST-tier items are simply clean."""
    write_yaml(
        tmp_path,
        _verification_corpus(
            [
                (
                    "TST-01-001",
                    "MUST",
                    "protocol",
                    {"verification": "A test."},
                ),
                (
                    "TST-01-002",
                    "MUST_NOT",
                    "protocol",
                    {"verification": "A test."},
                ),
            ]
        ),
    )
    result = lint(tmp_path, debt_owners={})
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err
    assert _summary_lines(captured.out) == []


def test_lint_retired_must_without_verification_suppression_fails_to_load(
    tmp_path, capsys
):
    """The suppression code is retired (#4199): using it is a schema error."""
    write_yaml(
        tmp_path,
        _verification_corpus(
            [
                (
                    "TST-01-001",
                    "MUST",
                    "protocol",
                    {
                        "verification_debt": "#1",
                        "lint_suppress": ["must_without_verification"],
                    },
                )
            ]
        ),
    )
    assert lint(tmp_path, debt_owners=_MIXED_OWNERS) == 1
    err = capsys.readouterr().err
    assert "[FATAL] Registry load failed" in err
    assert "lint_suppress" in err


@pytest.mark.spec("MS-10-024")
def test_lint_check_debt_owners_fails_on_a_closed_owner(
    tmp_path, capsys, monkeypatch
):
    """The opt-in owner check reaches lint() and fails on a closed issue."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    states = {"#1": "OPEN", "#2": "CLOSED"}
    monkeypatch.setattr(
        verification_module, "gh_issue_state", lambda ref: states[ref]
    )
    assert lint(tmp_path, debt_owners=_MIXED_OWNERS) == 0
    capsys.readouterr()
    result = lint(tmp_path, debt_owners=_MIXED_OWNERS, check_debt_owners=True)
    err = capsys.readouterr().err
    assert result == 1
    assert "#2 is CLOSED" in err
    assert "#1" not in err


@pytest.mark.spec("MS-10-024")
@pytest.mark.spec("ARCH-18-004")
def test_lint_check_debt_owners_ignores_unrelated_lint_errors(
    tmp_path, capsys, monkeypatch
):
    """The owner check reports closed owners only: an unrelated lint error,
    here an ADR with an invalid status, is spec-check's failure (#4336)."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    adr_dir = _make_adr_dir(tmp_path)
    _write_dated_adr(adr_dir, "0099", "no-such-status", "2020-01-01")
    monkeypatch.setattr(
        verification_module, "gh_issue_state", lambda ref: "OPEN"
    )
    assert lint(tmp_path, adr_dir=adr_dir, debt_owners=_MIXED_OWNERS) == 1
    capsys.readouterr()
    result = lint(
        tmp_path,
        adr_dir=adr_dir,
        debt_owners=_MIXED_OWNERS,
        check_debt_owners=True,
    )
    assert result == 0
    assert "MS-14-001" not in capsys.readouterr().err


@pytest.mark.spec("MS-10-020")
def test_main_list_unverified_flag(tmp_path, capsys, monkeypatch):
    """`spec-lint <dir> --list-unverified` reaches lint() as the opt-in."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    monkeypatch.setattr(lint_module, "VERIFICATION_DEBT_OWNERS", _MIXED_OWNERS)
    monkeypatch.setattr(
        sys, "argv", ["spec-lint", str(tmp_path), "--list-unverified"]
    )
    with pytest.raises(SystemExit) as exc:
        lint_module.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "TST-01-001" in out
    assert "TST-01-004" in out


@pytest.mark.spec("MS-10-020")
def test_main_default_does_not_list_ids(tmp_path, capsys, monkeypatch):
    """Without the flag, `spec-lint <dir>` prints the summary only (SR-06-002
    runs it this way from the pre-commit hook)."""
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    monkeypatch.setattr(lint_module, "VERIFICATION_DEBT_OWNERS", _MIXED_OWNERS)
    monkeypatch.setattr(sys, "argv", ["spec-lint", str(tmp_path)])
    with pytest.raises(SystemExit) as exc:
        lint_module.main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert len(_summary_lines(out)) == 2
    assert "TST-01-001" not in out


@pytest.mark.spec("MS-10-023")
def test_lint_check_closing_pr_fails_a_pr_closing_an_owner_in_use(
    tmp_path, capsys, monkeypatch
):
    write_yaml(tmp_path, _verification_corpus(_MIXED_ITEMS))
    monkeypatch.setattr(
        verification_module, "gh_pr_closing_issues", lambda pr: {"#2"}
    )
    result = lint(tmp_path, debt_owners=_MIXED_OWNERS, closing_pr=7)
    assert result == 1
    assert "this PR closes #2" in capsys.readouterr().err


def test_main_check_closing_pr_flag_reaches_lint(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def fake_lint(spec_dir, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(lint_module, "lint", fake_lint)
    monkeypatch.setattr(
        sys, "argv", ["spec-lint", str(tmp_path), "--check-closing-pr", "7"]
    )
    with pytest.raises(SystemExit):
        lint_module.main()
    assert seen["closing_pr"] == 7


def test_main_check_debt_owners_flag_reaches_lint(monkeypatch, tmp_path):
    """`--check-debt-owners` is what CI passes; without it lint stays offline."""
    seen: dict[str, object] = {}

    def fake_lint(spec_dir, **kwargs):
        seen.update(kwargs)
        return 0

    monkeypatch.setattr(lint_module, "lint", fake_lint)
    for argv, expected in (
        (["spec-lint", str(tmp_path)], False),
        (["spec-lint", str(tmp_path), "--check-debt-owners"], True),
    ):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            lint_module.main()
        assert seen["check_debt_owners"] is expected


@pytest.mark.spec("MS-12-007")
def test_lint_prints_the_suppression_totals(tmp_path, capsys):
    """spec-lint prints each MS-12 suppression total, computed (#4315)."""
    data = _minimal_spec_no_stories(priority="SHOULD")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(tmp_path, data)
    assert lint(tmp_path) == 0
    out = capsys.readouterr().out
    assert (
        "[INFO] lint_suppress missing_story_reference: 1 spec(s) carry it"
        in out
    )
    assert (
        "[INFO] lint_suppress protocol_kind_with_code_reference: "
        "0 spec(s) carry it" in out
    )


# ---------------------------------------------------------------------------
# TRACE-03-001: a cited story page must exist
# ---------------------------------------------------------------------------


def _repo_with_story_catalog(tmp_path, *stories: str):
    """A checkout whose ``specs/`` is the lint target and whose story catalog
    holds *stories*. ``lint(spec_dir)`` reads the catalog through
    ``spec_dir.parent``, so the two must sit in one tree."""
    catalog = tmp_path / "docs" / "reference" / "user_stories"
    catalog.mkdir(parents=True)
    for story in stories:
        (catalog / f"{story}.md").write_text(
            "---\nstakeholder_type: [project-contributor]\n---\n\n"
            f"# User Story `{story.removeprefix('story_')}`\n",
            encoding="utf-8",
        )
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    return spec_dir


def _spec_citing(*stories: str):
    data = _minimal_spec_no_stories(priority="MUST")
    data["groups"][0]["specs"][0]["stories"] = list(stories)
    return data


@pytest.mark.spec("TRACE-03-001")
def test_a_cited_story_with_no_page_is_a_hard_error(tmp_path, capsys):
    """A `stories:` entry naming an absent page fails the linter."""
    spec_dir = _repo_with_story_catalog(tmp_path, "story_2022_001")
    write_yaml(spec_dir, _spec_citing("story_2022_999"))
    assert lint(spec_dir) == 1
    err = capsys.readouterr().err
    assert "TRACE-03-001" in err
    assert "story_2022_999" in err
    assert "TST-01-001" in err


@pytest.mark.spec("TRACE-03-001")
def test_an_absent_story_cited_twice_is_named_once(tmp_path, capsys):
    """`stories:` constrains each entry's shape, not the list's uniqueness.

    Naming the ID twice in one sentence reads as two distinct missing pages.
    `measure_story_coverage` counts a repeat once for the same reason.
    """
    spec_dir = _repo_with_story_catalog(tmp_path, "story_2022_001")
    write_yaml(spec_dir, _spec_citing("story_2022_999", "story_2022_999"))
    assert lint(spec_dir) == 1
    err = capsys.readouterr().err
    assert err.count("story_2022_999") == 1


@pytest.mark.spec("TRACE-03-001")
def test_a_cited_story_with_a_page_passes(tmp_path, capsys):
    """A `stories:` entry naming a page in the catalog is clean."""
    spec_dir = _repo_with_story_catalog(tmp_path, "story_2022_001")
    write_yaml(spec_dir, _spec_citing("story_2022_001"))
    assert lint(spec_dir) == 0
    assert "TRACE-03-001" not in capsys.readouterr().err


@pytest.mark.spec("TRACE-03-001")
def test_the_cited_story_page_check_is_not_suppressible(tmp_path, capsys):
    """No `lint_suppress` code silences the absent-page error."""
    spec_dir = _repo_with_story_catalog(tmp_path, "story_2022_001")
    data = _spec_citing("story_2022_999")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference",
        "phantom_path_ref",
    ]
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1
    assert "TRACE-03-001" in capsys.readouterr().err


@pytest.mark.spec("TRACE-03-001")
def test_every_absent_story_on_one_requirement_is_named(tmp_path, capsys):
    """One error per requirement, naming every absent ID (EH-07-001)."""
    spec_dir = _repo_with_story_catalog(tmp_path, "story_2022_001")
    write_yaml(spec_dir, _spec_citing("story_2022_998", "story_2022_999"))
    assert lint(spec_dir) == 1
    err = capsys.readouterr().err
    assert err.count("TRACE-03-001") == 1
    assert "story_2022_998" in err
    assert "story_2022_999" in err


@pytest.mark.spec("TRACE-03-001")
def test_the_cited_story_page_check_degrades_without_a_docs_tree(
    tmp_path, capsys
):
    """No story catalog means no verdict, not a verdict against every citer.

    `uv run docs-site --check` is what fails on a missing catalog; the linter
    runs on trees that hold `specs/` alone.
    """
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _spec_citing("story_2022_999"))
    assert lint(spec_dir) == 0
    assert "TRACE-03-001" not in capsys.readouterr().err
