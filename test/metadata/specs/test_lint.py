"""Tests for vultron.metadata.specs.lint (SR.2.4).

Covers: hard-error checks (duplicate IDs, dangling relationships, prefix
mismatch) and advisory warnings (testable_without_steps, rationale_too_long,
missing_tags) including lint_suppress suppression.
"""

import sys

import pytest

import vultron.metadata.specs.lint as lint_module
import vultron.metadata.specs.verification as verification_module
from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.conftest import spec_file_data
from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.schema import RFC2119Priority, SpecKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


#: MS-10-003: a MUST-tier fixture carries this so the per-item verification
#: check stays out of tests about other rules.
_VERIFIED = "A unit test checks it."


def _minimal_spec(spec_id="TST-01-001", priority="MUST", extra=None):
    spec = {
        "id": spec_id,
        "priority": priority,
        "kind": "protocol",
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
        "stories": ["story_2022_001"],
    }
    if RFC2119Priority(priority).is_must_tier:
        # MS-10-003: keep the per-item verification check out of the way.
        spec["verification"] = _VERIFIED
    if extra:
        spec.update(extra)
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [spec],
            }
        ],
    }


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
# Hard errors
# ---------------------------------------------------------------------------


def test_lint_duplicate_spec_ids(tmp_path):
    data = _minimal_spec("DUP-01-001")
    data["id"] = "DUP"
    data["groups"][0]["id"] = "DUP-01"
    data["groups"][0]["specs"][0]["statement"] = "DUP-01-001 MUST be unique"
    write_yaml(tmp_path, data, "file1.yaml")
    write_yaml(tmp_path, data, "file2.yaml")
    result = lint(tmp_path)
    assert result == 1


def test_lint_dangling_relationship(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "relationships": [
                {"rel_type": "depends_on", "spec_id": "XX-99-999"}
            ]
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-999" in captured.err


def test_lint_prefix_mismatch(tmp_path, capsys):
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Prefix mismatch test",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTHER-01",  # prefix "OTHER" != file id "TST"
                "title": "Wrong Group",
                "specs": [
                    {
                        "id": "OTHER-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "OTHER-01-001 MUST be consistent",
                        "rationale": "Consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "OTHER-01" in captured.err


# ---------------------------------------------------------------------------
# Advisory warnings (non-blocking — return 0)
# ---------------------------------------------------------------------------


def test_lint_advisory_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(extra={"testable": False})
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "testable=false" in captured.out


def test_lint_advisory_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(extra={"rationale": "x" * 501})
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "rationale" in captured.out


def test_lint_advisory_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "tags" in captured.out


# ---------------------------------------------------------------------------
# lint_suppress suppression
# ---------------------------------------------------------------------------


def test_lint_suppress_testable_without_steps(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "testable": False,
            "lint_suppress": ["testable_without_steps"],
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "testable=false" not in captured.out


def test_lint_suppress_rationale_too_long(tmp_path, capsys):
    data = _minimal_spec(
        extra={
            "rationale": "x" * 501,
            "lint_suppress": ["rationale_too_long"],
        }
    )
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "rationale exceeds" not in captured.out


def test_lint_suppress_missing_tags(tmp_path, capsys):
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["tags"]
    data["groups"][0]["specs"][0]["lint_suppress"] = ["missing_tags"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "no tags" not in captured.out


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


@pytest.mark.spec("MS-10-005")
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


@pytest.mark.spec("MS-10-005")
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


@pytest.mark.spec("MS-10-007")
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
    assert "MS-10-007" in captured.err


@pytest.mark.spec("MS-10-007")
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


@pytest.mark.spec("MS-10-006")
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


@pytest.mark.spec("MS-10-005")
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


@pytest.mark.spec("MS-10-005")
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


@pytest.mark.spec("MS-10-006")
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


# ---------------------------------------------------------------------------
# Spec ID vs group prefix check (MS-04-004)
# ---------------------------------------------------------------------------


def test_lint_spec_id_prefix_mismatch(tmp_path, capsys):
    """A spec with ID TST-01-001 living in group TST-02 must be a hard error."""
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Spec ID prefix mismatch test",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-02",
                "title": "Group Two",
                "specs": [
                    {
                        "id": "TST-01-001",  # prefix TST-01 != group TST-02
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST be in group TST-01",
                        "rationale": "Prefix consistency",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "TST-01-001" in captured.err
    assert "TST-02" in captured.err


def test_lint_spec_id_prefix_match_passes(tmp_path, capsys):
    """A spec ID whose prefix matches its group must not produce an error."""
    data = _minimal_spec("TST-01-001")  # lives in group TST-01 — correct
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "TST-01-001" not in captured.err


# ---------------------------------------------------------------------------
# ADR reference check (dangling_adr_ref) — advisory, non-blocking
# ---------------------------------------------------------------------------


def _make_adr_dir(tmp_path, adr_numbers=None):
    """Create a fake docs/adr/ directory with stub ADR files."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    for num in adr_numbers or []:
        # Valid status frontmatter so the MS-14-001 status check (which runs
        # over every ADR in the dir) does not flag these reference stubs.
        (adr_dir / f"{num}-stub.md").write_text(
            f"---\nstatus: accepted\n---\n# ADR-{num}\n"
        )
    return adr_dir


def test_lint_adr_ref_missing_emits_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 that has no file emits a [WARN]."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory only, not a hard error
    assert "[WARN]" in captured.out
    assert "ADR-0099" in captured.out


def test_lint_adr_ref_present_no_warn(tmp_path, capsys):
    """A rationale referencing ADR-0099 when the file exists emits no warning."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_adr_dir_skips_check(tmp_path, capsys):
    """When adr_dir does not exist the check is silently skipped."""
    data = _minimal_spec(extra={"rationale": "Derived from ADR-0099."})
    write_yaml(tmp_path, data)
    nonexistent = tmp_path / "nonexistent" / "adr"
    result = lint(tmp_path, adr_dir=nonexistent)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_suppress(tmp_path, capsys):
    """dangling_adr_ref can be suppressed via lint_suppress."""
    data = _minimal_spec(
        extra={
            "rationale": "Derived from ADR-0099.",
            "lint_suppress": ["dangling_adr_ref"],
        }
    )
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-0099" not in captured.out


def test_lint_adr_ref_no_rationale_no_warn(tmp_path, capsys):
    """A spec without a rationale field produces no ADR warning."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["rationale"]
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "ADR-" not in captured.out


# ---------------------------------------------------------------------------
# Missing item-level kind is a hard error
# ---------------------------------------------------------------------------


def test_lint_missing_item_kind_is_hard_error(tmp_path):
    """A spec item missing kind: is a hard error (exit 1)."""
    data = _minimal_spec()
    del data["groups"][0]["specs"][0]["kind"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    assert result == 1


# ---------------------------------------------------------------------------
# scenario_start group must contain a BehavioralSpec with steps (MS-13-004)
# ---------------------------------------------------------------------------


def _scenario_start_group(with_behavioral_spec: bool):
    """Return a minimal spec file with one scenario_start group.

    When ``with_behavioral_spec`` is True the group contains a BehavioralSpec
    item with steps; otherwise it contains only a StatementSpec item.
    """
    if with_behavioral_spec:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST execute the scenario workflow",
            "rationale": "ECA required",
            "verification": _VERIFIED,
            "tags": ["demo"],
            "preconditions": [{"description": "Actors running"}],
            "steps": [
                {"order": 1, "actor": "finder", "action": "Submit report"}
            ],
            "postconditions": [{"description": "Case created"}],
        }
    else:
        workflow_item = {
            "id": "SCN-01-002",
            "priority": "MUST",
            "kind": "project",
            "statement": "SCN-01-002 MUST reach final state VFDPxa",
            "rationale": "Terminal state required",
            "verification": _VERIFIED,
            "tags": ["demo"],
        }

    return {
        "id": "SCN",
        "title": "Scenario Spec",
        "description": "Scenario spec file",
        "scope": ["prototype"],
        "groups": [
            {
                "id": "SCN-01",
                "title": "FV Scenario",
                "trigger": {"type": "scenario_start", "value": "fv"},
                "specs": [
                    {
                        "id": "SCN-01-001",
                        "priority": "MUST",
                        "kind": "project",
                        "statement": "SCN-01-001 MUST reach VFDPxa",
                        "rationale": "Terminal state",
                        "verification": _VERIFIED,
                        "tags": ["demo"],
                    },
                    workflow_item,
                ],
            }
        ],
    }


def test_scenario_start_with_behavioral_spec_passes(tmp_path, capsys):
    """scenario_start group with a BehavioralSpec+steps item must pass."""
    write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=True))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err


def test_scenario_start_without_behavioral_spec_fails(tmp_path, capsys):
    """scenario_start group with only StatementSpec items must be a hard error."""
    write_yaml(tmp_path, _scenario_start_group(with_behavioral_spec=False))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SCN-01" in captured.err
    assert "MS-13-004" in captured.err


def test_non_scenario_start_group_not_checked(tmp_path, capsys):
    """Groups without a scenario_start trigger are not subject to MS-13-004."""
    data = _minimal_spec()  # no trigger on group TST-01
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-13-004" not in captured.err


# ---------------------------------------------------------------------------
# ADR status frontmatter (MS-14-001 hard, MS-14-002 advisory) — ADR-0041
# ---------------------------------------------------------------------------


def _write_adr(adr_dir, num, status=None, body=""):
    """Write an ADR file; omit the status line entirely when status is None."""
    fm = (
        f"---\nstatus: {status}\n---\n" if status is not None else "---\n---\n"
    )
    (adr_dir / f"{num}-stub.md").write_text(f"{fm}# ADR-{num}\n{body}\n")


def test_lint_adr_missing_status_is_hard_error(tmp_path, capsys):
    """An ADR with no status frontmatter is a hard error (MS-14-001)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status=None)
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err
    assert "0099" in captured.err


def test_lint_adr_invalid_status_is_hard_error(tmp_path, capsys):
    """An ADR with an unknown status value is a hard error (MS-14-001)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(adr_dir, "0099", status="kinda-accepted")
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-14-001" in captured.err


def test_lint_adr_superseded_status_ok(tmp_path):
    """A superseded ADR with a resolvable superseded_by target is valid."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path, ["0100"])  # replacement exists
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_inline_form_ok(tmp_path):
    """The inline 'superseded by <link>' MADR form is accepted and resolved."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path, ["0100"])
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded by 0100-stub.md\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_superseded_without_target_is_hard_error(tmp_path, capsys):
    """A retired ADR missing superseded_by is a hard error (MS-14-004)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: superseded\n---\n# x\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "superseded_by" in captured.err


def test_lint_adr_accepted_with_provisional_prose_warns(tmp_path, capsys):
    """status: accepted + provisional prose is an advisory warning (MS-14-002)."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0  # advisory, not a hard error
    assert "MS-14-002" in captured.out
    assert "[WARN]" in captured.out


def test_lint_adr_accepted_provisional_status_no_warn(tmp_path, capsys):
    """accepted-provisional + provisional prose is consistent — no warning."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    _write_adr(
        adr_dir,
        "0099",
        status="accepted-provisional",
        body="This design is formed in sand.",
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-002" not in captured.out


# ---------------------------------------------------------------------------
# Structured adr: field references (SR-02-020) — hard error on dangling target
# ---------------------------------------------------------------------------


def test_lint_structured_adr_ref_missing_is_hard_error(tmp_path, capsys):
    """A structured adr: target with no ADR file is a hard error."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)  # no 0099 file
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "ADR-0099" in captured.err


def test_lint_structured_adr_ref_present_ok(tmp_path, capsys):
    """A structured adr: target that resolves to a file is clean."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path, ["0099"])
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_structured_adr_ref_resolves_to_archived(tmp_path):
    """A structured adr: target in docs/adr/archived/ resolves (no error)."""
    data = _minimal_spec(extra={"adr": ["ADR-0099"]})
    write_yaml(tmp_path, data)
    adr_dir = _make_adr_dir(tmp_path)
    archived = adr_dir / "archived"
    archived.mkdir()
    (archived / "0099-stub.md").write_text(
        "---\nstatus: deprecated\nsuperseded_by: 0100-stub.md\n---\n# x\n"
    )
    (adr_dir / "0100-stub.md").write_text("---\nstatus: accepted\n---\n# x\n")
    result = lint(tmp_path, adr_dir=adr_dir)
    assert result == 0


def test_lint_adr_status_prose_suppress(tmp_path, capsys):
    """lint_suppress: [status_prose_contradiction] silences the MS-14-002 warn."""
    write_yaml(tmp_path, _minimal_spec())
    adr_dir = _make_adr_dir(tmp_path)
    (adr_dir / "0099-stub.md").write_text(
        "---\nstatus: accepted\n"
        "lint_suppress: [status_prose_contradiction]\n---\n"
        "# ADR-0099\nThis ADR is formed in sand.\n"
    )
    result = lint(tmp_path, adr_dir=adr_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-14-002" not in captured.out


# ---------------------------------------------------------------------------
# MS-15-001: phantom path references in spec statements
# ---------------------------------------------------------------------------


def _repo_with_specs(tmp_path):
    """Return (repo_root, spec_dir) — lint() treats spec_dir.parent as the root.

    Creates the top-level directories the phantom-path tests reference, so a
    match is exercised against the existence check rather than being skipped as
    a package-relative illustration.
    """
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    for name in ("vultron", "test", ".claude", "docs"):
        (tmp_path / name).mkdir()
    return tmp_path, spec_dir


def test_lint_phantom_path_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent repo-relative path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The harness MUST be registered in `vultron/nope.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_existing_file_passes(tmp_path):
    """A statement naming a path that exists is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The thing MUST live in `vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_exempt(tmp_path):
    """Placeholder path forms describe a shape, not a file, and are exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each scenario MUST have a `test/ci/invariants/test_XXX_invariants.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_without_placeholder_token_fails(tmp_path):
    """The same path minus the placeholder token is checked and fails.

    Guards the exemption above against becoming vacuous: `test/` exists in the
    fixture repo, so this path reaches the existence check.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each scenario MUST have a `test/ci/invariants/test_fv_invariants.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_placeholder_basename_exempt(tmp_path):
    """Placeholder basenames are exempt, but only as a whole path segment."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "A new note MUST be created at `notes/new-topic.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_placeholder_basename_not_a_substring(tmp_path):
    """A real path merely *starting* with a placeholder name is still checked."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "notes").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The workflow MUST be documented in `notes/new-topic-workflow.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_dot_directory_is_checked(tmp_path, capsys):
    """Dot-directories such as `.claude/` are enforced, not silently skipped."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert ".claude/skills/format-markdown/SKILL.md" in captured.err


def test_lint_phantom_path_dot_directory_existing_passes(tmp_path):
    """A dot-directory path that does exist is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    skill = repo / ".claude" / "skills" / "format-markdown"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# skill\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Linting MUST run via `.claude/skills/format-markdown/SKILL.md`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_resolves_as_suffix(tmp_path):
    """A package-relative illustration resolves against a real file's suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    pkg = repo / "vultron" / "wire" / "received"
    pkg.mkdir(parents=True)
    (pkg / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_package_relative_unresolvable_fails(tmp_path):
    """A package-relative path matching nothing in the tree is still an error."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_mistyped_leading_segment_fails(tmp_path, capsys):
    """A mistyped first segment does not escape via the suffix path.

    `tests/` (plural) is not a top-level dir, so the match is resolved as a
    suffix — and no file ends with `tests/ci/common.py`, so it errors.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    real = repo / "test" / "ci"
    real.mkdir(parents=True)
    (real / "common.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Checks MUST live in `tests/ci/common.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "tests/ci/common.py" in captured.err


def test_lint_phantom_path_suffix_ignores_build_artifacts(tmp_path):
    """A path satisfied only inside `.venv/` or `__pycache__/` is not resolved."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    vendored = repo / ".venv" / "lib" / "received"
    vendored.mkdir(parents=True)
    (vendored / "sync.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be defined in `received/sync.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_path_absolute_rejected(tmp_path, capsys):
    """An absolute path is rejected outright, not exempted."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Config MUST be read from `/etc/vultron/settings.yaml`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_parent_traversal_rejected(tmp_path, capsys):
    """A `..` segment is rejected even when it resolves on the filesystem."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The thing MUST live in `test/../vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "not a valid repo-relative path" in captured.err


def test_lint_phantom_path_rationale_not_scanned(tmp_path):
    """rationale narrates history and may cite paths that no longer exist."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["rationale"] = (
        "`vultron/old_config.py` has been converted to a package."
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] allows a deliberate forward reference."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "A new module MUST be created at `vultron/planned.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


def test_lint_phantom_path_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `vultron/nope.py` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_verification_existing_passes(tmp_path):
    """A verification field naming an existing path is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `vultron/real.py` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_verification_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in verification."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["verification"] = (
        "A test at `vultron/future.py` will assert this."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-001" not in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: directory reference checks
# ---------------------------------------------------------------------------


def test_lint_phantom_dir_is_hard_error(tmp_path, capsys):
    """A statement naming a non-existent multi-segment directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/missing/`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing/" in captured.err


def test_lint_phantom_dir_existing_passes(tmp_path):
    """A statement naming an existing directory passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/real/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_single_segment_not_checked(tmp_path):
    """A single-segment directory ref is not checked — high false-positive risk."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Output MUST be written to the `devlogs/` directory"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_exempt(tmp_path):
    """A directory ref containing a placeholder token is exempt."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each run MUST write to `plan/history/YYMM/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_placeholder_negative(tmp_path):
    """The same path without the placeholder token fails.

    Guards the exemption above against becoming vacuous: the directory
    `plan/history/2601/` is expected to not exist in the fixture tree.
    """
    _, spec_dir = _repo_with_specs(tmp_path)
    (tmp_path / "plan").mkdir()
    (tmp_path / "plan" / "history").mkdir()
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Each run MUST write to `plan/history/2601/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_package_relative_resolves(tmp_path):
    """A package-relative directory resolves against a real directory suffix."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "wire" / "received").mkdir(parents=True)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Handlers MUST live in `wire/received/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_package_relative_fails(tmp_path):
    """A package-relative directory matching nothing in the tree fails."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Handlers MUST live in `wire/received/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 1


def test_lint_phantom_dir_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom directory refs."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_path_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "Helpers MUST live in `vultron/planned/`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_dir_in_verification_is_hard_error(tmp_path, capsys):
    """A verification field naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "Assert via `test/ci/invariants/` that the invariant holds."
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "test/ci/invariants/" in captured.err


# ---------------------------------------------------------------------------
# MS-15-001: behavioral step / precondition / postcondition scanning
# ---------------------------------------------------------------------------


def _minimal_behavioral_spec_data(
    step_action="Execute workflow",
    precondition_desc="System is ready",
    postcondition_desc="Workflow complete",
):
    """Return a minimal spec file containing one BehavioralSpec item."""
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute the workflow",
        "rationale": "ECA required",
        "verification": _VERIFIED,
        "tags": ["testing"],
        "stories": ["story_2022_001"],
        "preconditions": [{"description": precondition_desc}],
        "steps": [{"order": 1, "actor": "finder", "action": step_action}],
        "postconditions": [{"description": postcondition_desc}],
    }
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": [spec]}],
    }


def test_lint_phantom_dir_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent directory fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Write output to `vultron/output/`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/output/" in captured.err


def test_lint_phantom_path_in_behavioral_step_is_hard_error(tmp_path, capsys):
    """A behavioral step action naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/nope.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/nope.py" in captured.err


def test_lint_phantom_path_in_behavioral_step_existing_passes(tmp_path):
    """A behavioral step action naming an existing file passes."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "real.py").write_text("x = 1\n")
    data = _minimal_behavioral_spec_data(
        step_action="Register via `vultron/real.py`"
    )
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


def test_lint_phantom_path_in_precondition_is_hard_error(tmp_path, capsys):
    """A precondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        precondition_desc="File `vultron/missing.py` is loaded"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_in_postcondition_is_hard_error(tmp_path, capsys):
    """A postcondition description naming a non-existent path fails (MS-15-001)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_behavioral_spec_data(
        postcondition_desc="Result written to `vultron/missing.py`"
    )
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-001" in captured.err
    assert "vultron/missing.py" in captured.err


def test_lint_phantom_path_behavioral_step_suppress(tmp_path):
    """lint_suppress: [phantom_path_ref] exempts phantom paths in behavioral fields."""
    _, spec_dir = _repo_with_specs(tmp_path)
    spec = {
        "id": "TST-01-001",
        "priority": "MUST",
        "kind": "protocol",
        "statement": "TST-01-001 MUST execute",
        "rationale": "Required",
        "verification": _VERIFIED,
        "tags": ["testing"],
        "stories": ["story_2022_001"],
        "preconditions": [{"description": "System ready"}],
        "steps": [
            {
                "order": 1,
                "actor": "system",
                "action": "Create `vultron/future.py`",
            }
        ],
        "postconditions": [{"description": "Complete"}],
        "lint_suppress": ["phantom_path_ref"],
    }
    data = {
        "id": "TST",
        "title": "T",
        "description": "T",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "G", "specs": [spec]}],
    }
    write_yaml(spec_dir, data)
    assert lint(spec_dir) == 0


# ---------------------------------------------------------------------------
# _check_phantom_spec_id_citations (SR-04-008)
# ---------------------------------------------------------------------------


def test_phantom_spec_id_unknown_in_vultron_is_hard_error(tmp_path, capsys):
    """A .py file under vultron/ citing an unknown spec ID is a hard error."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text('"""Spec: XX-99-001."""\n')

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-001" in captured.err


def test_phantom_spec_id_known_id_no_error(tmp_path, capsys):
    """A .py file under vultron/ citing a known spec ID returns 0."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text(
        '"""Spec: TST-01-001 MUST do the thing."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_phantom_spec_id_allowlisted_dir_no_error(tmp_path, capsys):
    """Files under test/metadata/specs/ citing synthetic IDs are not flagged."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    allowlist_dir = tmp_path / "test" / "metadata" / "specs"
    allowlist_dir.mkdir(parents=True)
    (allowlist_dir / "test_fixture.py").write_text(
        '"""Uses synthetic IDs like XX-99-001."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "[ERROR]" not in captured.err


def test_phantom_spec_id_no_ids_in_file_no_error(tmp_path):
    """A .py file with no spec ID tokens returns 0."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    vultron_dir = tmp_path / "vultron"
    vultron_dir.mkdir()
    (vultron_dir / "module.py").write_text("def hello():\n    return 42\n")

    assert lint(spec_dir) == 0


def test_phantom_spec_id_unknown_in_test_dir_is_hard_error(tmp_path, capsys):
    """A .py file under a non-allowlisted test/ subdir citing an unknown spec ID is a hard error."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    write_yaml(spec_dir, _minimal_spec())
    test_core_dir = tmp_path / "test" / "core"
    test_core_dir.mkdir(parents=True)
    (test_core_dir / "test_something.py").write_text(
        '"""Spec: XX-99-001."""\n'
    )

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "XX-99-001" in captured.err


# ---------------------------------------------------------------------------
# MS-15-004 / MS-15-005: phantom symbol references in spec statements
# ---------------------------------------------------------------------------


def test_lint_phantom_symbol_is_hard_error(tmp_path, capsys):
    """A statement naming a SCREAMING_SNAKE symbol absent from the tree fails."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Every pattern MUST be registered in `RETIRED_PATTERN_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "MS-15-004" in captured.err
    assert "RETIRED_PATTERN_TABLE" in captured.err


def test_lint_phantom_symbol_existing_symbol_passes(tmp_path):
    """A statement naming a symbol defined under vultron/ is accepted."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "vultron" / "registry.py").write_text(
        "LIVE_PATTERN_TABLE: dict = {}\n"
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Every pattern MUST be registered in `LIVE_PATTERN_TABLE`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_resolves_from_test_tree(tmp_path):
    """A symbol that only exists under test/ still resolves (MS-15-004)."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "test" / "test_thing.py").write_text("KNOWN_VIOLATIONS = ()\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The ratchet MUST enumerate exemptions in `KNOWN_VIOLATIONS`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_in_verification_is_hard_error(tmp_path, capsys):
    """The verification field is scanned for phantom symbols too."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["verification"] = (
        "A unit test asserts `GONE_REGISTRY` has one entry per semantic."
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "GONE_REGISTRY" in captured.err


def test_lint_phantom_symbol_rationale_not_scanned(tmp_path):
    """rationale narrates history and may name a removed symbol."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["rationale"] = (
        "`GONE_REGISTRY` was replaced during the registry move."
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_suppress(tmp_path, capsys):
    """lint_suppress: [phantom_symbol_ref] allows a deliberate mention (MS-15-005)."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec(extra={"lint_suppress": ["phantom_symbol_ref"]})
    data["groups"][0]["specs"][0]["statement"] = (
        "The `REMOVED_SEMANTIC_TABLE` table has been removed; use the registry."
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-15-004" not in captured.err


def test_lint_phantom_symbol_linter_own_source_excluded_from_corpus(
    tmp_path, capsys
):
    """A symbol appearing only under `vultron/metadata/specs/` is not live.

    The linter's own modules quote retired symbol names in docstrings and error
    messages. Counting those as corpus entries would make the check resolve the
    very tokens it exists to reject.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    linter_dir = repo / "vultron" / "metadata" / "specs"
    linter_dir.mkdir(parents=True)
    (linter_dir / "lint.py").write_text(
        '"""Catches references to `RETIRED_TABLE`."""\n'
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be registered in `RETIRED_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "RETIRED_TABLE" in captured.err


def test_lint_phantom_symbol_linter_sibling_still_in_corpus(tmp_path):
    """A symbol defined only in a sibling of lint.py (e.g. schema.py) resolves.

    The corpus exclusion is scoped to ``lint.py`` itself, not the whole
    ``vultron/metadata/specs/`` package: ``schema.py`` defines symbols the specs
    legitimately cite (``RFC2119Priority`` members such as ``SHOULD_NOT``), so
    excluding the package would reject real references. This pins that scoping
    decision — the mirror of
    :func:`test_lint_phantom_symbol_linter_own_source_excluded_from_corpus`.
    """
    repo, spec_dir = _repo_with_specs(tmp_path)
    linter_dir = repo / "vultron" / "metadata" / "specs"
    linter_dir.mkdir(parents=True)
    (linter_dir / "schema.py").write_text("SHOULD_NOT = 'should_not'\n")
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The priority MUST NOT be `SHOULD_NOT`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_test_fixture_dir_excluded_from_corpus(
    tmp_path, capsys
):
    """Symbol names invented by the linter's own tests are not live either."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    fixture_dir = repo / "test" / "metadata" / "specs"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "test_lint.py").write_text(
        'STATEMENT = "MUST be in `INVENTED_TABLE`"\n'
    )
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Patterns MUST be registered in `INVENTED_TABLE`"
    )
    write_yaml(spec_dir, data)

    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert "INVENTED_TABLE" in captured.err


def test_lint_phantom_symbol_single_word_token_not_checked(tmp_path):
    """Underscore-free tokens (`MUST`, `RS`, `SIGNATORY`) are not symbols."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "Shorthand `RS` MUST leave the participant `SIGNATORY`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


def test_lint_phantom_symbol_dotted_reference_not_checked(tmp_path):
    """A dotted member reference is not a bare SCREAMING_SNAKE token."""
    _, spec_dir = _repo_with_specs(tmp_path)
    data = _minimal_spec()
    data["groups"][0]["specs"][0]["statement"] = (
        "The fallback MUST be `MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT`"
    )
    write_yaml(spec_dir, data)

    assert lint(spec_dir) == 0


# ---------------------------------------------------------------------------
# SR-11: missing_story_reference — hard error (MUST) and advisory (SHOULD/MAY)
# ---------------------------------------------------------------------------


def _minimal_spec_no_stories(priority="MUST", kind="protocol"):
    """Return a minimal spec file with NO stories: field."""
    spec = {
        "id": "TST-01-001",
        "priority": priority,
        "kind": kind,
        "statement": "TST-01-001 MUST do the thing",
        "rationale": "Because testing",
        "tags": ["testing"],
    }
    if RFC2119Priority(priority).is_must_tier:
        spec["verification"] = _VERIFIED
    return {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": [spec]}],
    }


def test_protocol_must_no_stories_is_hard_error(tmp_path, capsys):
    """kind=protocol + priority=MUST + no stories: is a hard error (SR-11-003)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MUST"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 1
    assert "SR-11-003" in captured.err
    assert "missing_story_reference" in captured.err


def test_protocol_must_with_stories_passes(tmp_path, capsys):
    """kind=protocol + priority=MUST with a stories: entry does not hard-error."""
    data = _minimal_spec_no_stories(priority="MUST")
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


def test_protocol_must_suppress_missing_story_reference(tmp_path, capsys):
    """lint_suppress: [missing_story_reference] silences the SR-11-003 hard error."""
    data = _minimal_spec_no_stories(priority="MUST")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


def test_non_protocol_must_no_stories_no_hard_error(tmp_path, capsys):
    """kind=architecture + priority=MUST with no stories does NOT hard-error."""
    write_yaml(
        tmp_path,
        _minimal_spec_no_stories(priority="MUST", kind="architecture"),
    )
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "SR-11-003" not in captured.err


def test_protocol_should_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=SHOULD + no stories emits advisory [WARN] (SR-11-004)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="SHOULD"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out


def test_protocol_may_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=MAY + no stories emits advisory [WARN] (SR-11-004)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MAY"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out


@pytest.mark.spec("SR-11-004")
def test_protocol_should_not_no_stories_is_advisory(tmp_path, capsys):
    """kind=protocol + priority=SHOULD_NOT + no stories emits advisory [WARN]
    (SR-11-004 — SHOULD_NOT is the SHOULD tier, MS-02-003)."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="SHOULD_NOT"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "[WARN]" in captured.out
    assert "missing_story_reference" in captured.out
    assert "priority=SHOULD_NOT" in captured.out


@pytest.mark.spec("SR-11-003")
def test_protocol_must_not_no_stories_is_not_a_hard_error(tmp_path, capsys):
    """SR-11-003 is MUST-only for now — the recorded MS-02-003 exception —
    so a story-less protocol MUST_NOT neither hard-errors nor warns."""
    write_yaml(tmp_path, _minimal_spec_no_stories(priority="MUST_NOT"))
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in captured.err
    assert "missing_story_reference" not in captured.out


def test_protocol_should_with_stories_no_story_warn(tmp_path, capsys):
    """kind=protocol + priority=SHOULD with stories: does not emit advisory."""
    data = _minimal_spec_no_stories(priority="SHOULD")
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_042"]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in captured.out


def test_protocol_should_suppress_advisory_story_warn(tmp_path, capsys):
    """lint_suppress: [missing_story_reference] silences the SHOULD advisory."""
    data = _minimal_spec_no_stories(priority="SHOULD")
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(tmp_path, data)
    result = lint(tmp_path)
    captured = capsys.readouterr()
    assert result == 0
    assert "missing_story_reference" not in captured.out


# ---------------------------------------------------------------------------
# MS-12-006: protocol_kind_with_code_reference — hard error, story-bearing
# exemption, suppression path, and the tiers SR-11-003 does not reach
# ---------------------------------------------------------------------------


def _protocol_spec_naming_code(
    tmp_path,
    *,
    field="verification",
    text=None,
    priority="MUST",
    kind="protocol",
):
    """Return (spec_dir, data): a story-less spec whose *field* names a real
    ``test/`` file inside the fake repo, so only MS-12-006 can fire on it."""
    repo, spec_dir = _repo_with_specs(tmp_path)
    (repo / "test" / "test_thing.py").write_text("")
    data = _minimal_spec_no_stories(priority=priority, kind=kind)
    data["groups"][0]["specs"][0][field] = (
        text or "Covered by `test/test_thing.py`, which drives the transition."
    )
    return spec_dir, data


def _ms12_lines(captured_err: str) -> list[str]:
    return [line for line in captured_err.splitlines() if "MS-12-006" in line]


def test_protocol_no_stories_code_reference_is_hard_error(tmp_path, capsys):
    """kind=protocol, no stories:, verification names test/…py → exit 1 (MS-12-006)."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    lines = _ms12_lines(captured.err)
    assert len(lines) == 1
    assert "TST-01-001" in lines[0]
    assert "verification" in lines[0]
    assert "test/test_thing.py" in lines[0]
    assert "protocol_kind_with_code_reference" in lines[0]


def test_protocol_code_reference_message_names_the_tree_not_a_kind(
    tmp_path, capsys
):
    """The message directs to MS-12-001 → MS-12-005 and prescribes no kind (MS-12-005).

    ``pytest``, ``test/`` and ``scripts/`` land in territory MS-12-001 claims
    for ``process``, so a message that said "use kind: project" would misroute
    them; the remedy is the ordered tree.
    """
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    lint(spec_dir)
    (line,) = _ms12_lines(capsys.readouterr().err)
    assert "MS-12-001" in line and "MS-12-005" in line
    for kind in ("project", "process", "architecture"):
        assert f"kind: {kind}" not in line
        assert f"kind={kind}" not in line


def test_protocol_with_stories_and_code_reference_passes(tmp_path, capsys):
    """A story-bearing protocol spec is exempt by construction (MS-12-006)."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["stories"] = ["story_2022_001"]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


def test_protocol_code_reference_suppressed(tmp_path, capsys):
    """lint_suppress: [protocol_kind_with_code_reference] silences MS-12-006."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path)
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference",
        "protocol_kind_with_code_reference",
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


def test_non_protocol_kind_with_code_reference_not_flagged(tmp_path, capsys):
    """A kind=project spec naming code is the tree's correct outcome, not a fault."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path, kind="project")
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 0
    assert "MS-12-006" not in captured.err


@pytest.mark.parametrize(
    "priority", ["MUST_NOT", "SHOULD", "SHOULD_NOT", "MAY"]
)
def test_protocol_code_reference_is_not_priority_scoped(
    tmp_path, capsys, priority
):
    """MS-12-006 fires on every tier; SR-11-003's MUST-only gate never reached these."""
    spec_dir, data = _protocol_spec_naming_code(tmp_path, priority=priority)
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    captured = capsys.readouterr()
    assert result == 1
    assert len(_ms12_lines(captured.err)) == 1


def test_protocol_code_reference_in_statement_is_hard_error(tmp_path, capsys):
    """A token in the statement is caught too; the field is named in the message."""
    spec_dir, data = _protocol_spec_naming_code(
        tmp_path,
        field="statement",
        text="The tree MUST be built from `py_trees` composites",
    )
    data["groups"][0]["specs"][0]["lint_suppress"] = [
        "missing_story_reference"
    ]
    write_yaml(spec_dir, data)
    result = lint(spec_dir)
    (line,) = _ms12_lines(capsys.readouterr().err)
    assert result == 1
    assert "its statement" in line
    assert "'py_trees'" in line
