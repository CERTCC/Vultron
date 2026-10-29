"""Tests for the ADR lifecycle epochs and their checks (MS-14-007 to MS-14-012)."""

from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from vultron.metadata.adr.lifecycle import (
    AdrEpoch,
    Dependents,
    _texts_at,
    check_change,
    check_paths,
    dependents_at,
    edit_faults,
    epoch_drift,
    epoch_for,
    main,
    status_behind_fault,
    status_epoch_fault,
    tree_dependents,
    unflipped_adrs,
    verified_dependents,
)
from vultron.metadata.adr.schema import AdrFrontmatter

TODAY = dt.date(2026, 10, 20)
NO_DEPENDENTS = Dependents(base={}, head={})


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
        (13, AdrEpoch.PROPOSED),
        (14, AdrEpoch.PROVISIONAL),
        (27, AdrEpoch.PROVISIONAL),
        (28, AdrEpoch.SETTLED),
        (400, AdrEpoch.SETTLED),
    ],
)
@pytest.mark.spec("MS-14-007")
def test_epoch_boundaries(age_days: int, epoch: AdrEpoch) -> None:
    assert epoch_for(TODAY - dt.timedelta(days=age_days), TODAY) is epoch


@pytest.mark.parametrize(
    "age_days, epoch",
    [
        (0, AdrEpoch.PROVISIONAL),
        (13, AdrEpoch.PROVISIONAL),
        (27, AdrEpoch.PROVISIONAL),
        (28, AdrEpoch.SETTLED),
    ],
)
@pytest.mark.spec("MS-14-007")
def test_tested_dependent_ends_epoch_one_whatever_the_date(
    age_days: int, epoch: AdrEpoch
) -> None:
    """Day 0 is the day a material edit restarts the timers: the dependency
    still holds the ADR in epoch 2."""
    updated = TODAY - dt.timedelta(days=age_days)
    assert epoch_for(updated, TODAY, tested=True) is epoch


@pytest.mark.parametrize(
    "status, age_days, faulty",
    [
        ("proposed", 1, False),
        ("proposed", 14, True),
        ("accepted-provisional", 14, False),
        ("accepted-provisional", 1, True),
        ("accepted", 28, False),
        ("accepted", 27, True),
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


@pytest.mark.parametrize(
    "status, age_days, tested, behind",
    [
        ("proposed", 13, False, False),
        ("proposed", 14, False, True),
        ("proposed", 0, True, True),
        ("accepted-provisional", 0, True, False),
        ("accepted-provisional", 0, False, False),  # ahead stands
        ("accepted", 0, False, False),  # ahead stands
        ("accepted-provisional", 28, False, True),
        ("rejected", 400, False, False),
    ],
)
@pytest.mark.spec("MS-14-012")
def test_drift_fault_is_one_sided(
    status: str, age_days: int, tested: bool, behind: bool
) -> None:
    fm = _fm(status, TODAY - dt.timedelta(days=age_days))
    fault = status_behind_fault("0001-x.md", fm, TODAY, tested=tested)
    assert (fault is not None) is behind


@pytest.mark.parametrize(
    "status, age_days, credited",
    [
        ("proposed", 0, True),  # the dependent ended epoch 1
        ("proposed", 14, False),  # the clock ended epoch 1 first
        ("accepted-provisional", 28, False),  # epoch 3 is the clock's alone
    ],
)
@pytest.mark.spec("MS-14-007")
def test_drift_report_credits_dependent_only_when_it_decided_the_epoch(
    status: str, age_days: int, credited: bool
) -> None:
    fm = _fm(status, TODAY - dt.timedelta(days=age_days))
    fault = status_behind_fault("0001-x.md", fm, TODAY, tested=True)
    assert fault is not None
    assert ("test-verified dependent" in fault) is credited


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
    assert len(faults) == 2  # the epoch rule and this rule both fire
    assert all("status_override" in f for f in faults)


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


@pytest.mark.spec("MS-14-010")
def test_unflipped_lists_proposed_adrs_with_dependents_and_no_override() -> (
    None
):
    registry = {
        "docs/adr/0120-x.md": _fm("proposed", TODAY),
        "docs/adr/0121-y.md": _fm("accepted-provisional", TODAY),
        "docs/adr/0122-z.md": _fm("proposed", TODAY),
        "docs/adr/0123-w.md": _fm("proposed", TODAY, status_override="held"),
    }
    deps = {"0120": ["A-01-001"], "0121": ["A-01-002"], "0123": ["A-01-003"]}
    assert unflipped_adrs(registry, deps) == {
        "docs/adr/0120-x.md": ["A-01-001"]
    }


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
    assert verified_dependents(
        specs, lambda rel: (tmp_path / rel).is_file()
    ) == {"0120": ["A-01-001"]}


def test_subsection_of_decision_outcome_is_protected() -> None:
    old = _adr("accepted", "2026-01-01", outcome="A.\n\n### Option 1\n\nX.")
    new = _adr("accepted", "2026-01-01", outcome="A.\n\n### Option 1\n\nY.")
    assert "Decision Outcome" in edit_faults("x", old, new, TODAY)[0]


def test_titled_variant_of_protected_section_is_protected() -> None:
    old = OLD.replace("## Considered Options", "## Considered options (x)")
    new = old.replace("A or B.", "A, B or C.")
    assert "Considered Options" in edit_faults("x", old, new, TODAY)[0]


def test_amendment_heading_inside_code_fence_does_not_count() -> None:
    new = _adr(
        "accepted",
        "2026-01-01",
        outcome="B.\n\n```\n### Amendment 2026-10-20\n```\n",
    )
    assert len(edit_faults("x", OLD, new, TODAY)) == 1


def test_amendment_text_itself_is_not_a_protected_change() -> None:
    first = _adr(
        "accepted",
        "2026-01-01",
        outcome="A.\n\n### Amendment 2026-10-01\n\nQ.",
    )
    second = _adr(
        "accepted",
        "2026-01-01",
        outcome="A.\n\n### Amendment 2026-10-01\n\nQ2.",
    )
    assert edit_faults("x", first, second, TODAY) == []


def test_material_edit_must_leave_status_matching_the_epoch() -> None:
    """A PR that moves `updated` owns the status on that date (MS-14-007)."""
    old = _adr("proposed", "2026-10-19")
    new = _adr("accepted-provisional", "2026-10-20")
    faults = edit_faults("x", old, new, TODAY)
    assert any("MS-14-007" in f and "epoch 1" in f for f in faults)


def test_material_edit_with_matching_status_is_clean() -> None:
    old = _adr("proposed", "2026-10-19")
    new = _adr("proposed", "2026-10-20")
    assert edit_faults("x", old, new, TODAY) == []


def test_new_adr_with_a_status_off_its_epoch_is_refused() -> None:
    assert edit_faults("x", None, _adr("accepted", "2026-10-20"), TODAY)
    assert edit_faults("x", None, _adr("proposed", "2026-10-20"), TODAY) == []


def test_material_edit_status_override_lets_disagreement_stand() -> None:
    old = _adr("accepted", "2026-01-01")
    new = _adr(
        "accepted", "2026-10-20", extra_fm="status_override: human call\n"
    )
    assert edit_faults("x", old, new, TODAY) == []


def test_untouched_updated_never_trips_the_epoch_rule() -> None:
    """Drift on an ADR whose `updated` did not move is the report's, not the
    merge gate's: a typo fix on a stale ADR must pass (#4340)."""
    old = _adr("proposed", "2026-10-01")
    new = _adr("proposed", "2026-10-01", tail="\nTypo fixed.\n")
    assert edit_faults("x", old, new, TODAY) == []


def test_epoch_drift_lists_every_stale_status_without_overrides(
    tmp_path: Path,
) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-stale.md").write_text(
        _adr("proposed", "2026-10-01"), encoding="utf-8"
    )
    (adr_dir / "0002-fine.md").write_text(
        _adr("proposed", "2026-10-20"), encoding="utf-8"
    )
    (adr_dir / "0003-held.md").write_text(
        _adr("proposed", "2026-10-01", extra_fm="status_override: held\n"),
        encoding="utf-8",
    )
    drift = epoch_drift(tmp_path, TODAY)
    assert len(drift) == 1
    assert drift[0].startswith("0001-stale.md")


def test_main_report_drift_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as settled:
        main(["--report-drift"])
    assert settled.value.code == 0
    (adr_dir / "0001-x.md").write_text(
        _adr("proposed", "2026-01-01"), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as drifted:
        main(["--report-drift"])
    assert drifted.value.code == 1
    assert "0001-x.md" in capsys.readouterr().err


def _run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose HEAD holds a settled ADR, with the cwd inside it."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(OLD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    vcs = "g" + "it"
    _run(vcs, "init", "-q")
    _run(vcs, "add", ".")
    _run(
        vcs,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "commit",
        "-q",
        "-m",
        "x",
    )
    return adr_dir


def test_check_paths_refuses_edit_and_skips_new_and_non_adr_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    edited = adr_dir / "0001-x.md"
    edited.write_text(
        _adr("accepted", "2026-01-01", outcome="B."), encoding="utf-8"
    )
    new_adr = adr_dir / "0002-new.md"
    new_adr.write_text(_adr("proposed", "2026-10-20"), encoding="utf-8")
    index = adr_dir / "index.md"
    index.write_text("changed", encoding="utf-8")
    missing = adr_dir / "0003-gone.md"

    paths = [edited, new_adr, index, adr_dir / "_t.md", missing]
    faults = check_paths(
        [p.relative_to(tmp_path) for p in paths], "HEAD", TODAY, NO_DEPENDENTS
    )
    assert len(faults) == 1
    assert faults[0].startswith("0001-x.md")


def test_check_paths_follows_a_rename_to_the_old_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    renamed = adr_dir / "0001-y.md"
    _run("g" + "it", "mv", "docs/adr/0001-x.md", "docs/adr/0001-y.md")
    renamed.write_text(
        _adr("accepted", "2026-01-01", outcome="B."), encoding="utf-8"
    )
    assert (
        len(
            check_paths(
                [renamed.relative_to(tmp_path)], "HEAD", TODAY, NO_DEPENDENTS
            )
        )
        == 1
    )


def test_bad_base_ref_is_an_error_not_a_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="not a commit"):
        check_change([adr_dir / "0001-x.md"], "no-such-ref", TODAY, tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(["--base", "no-such-ref", "docs/adr/0001-x.md"])
    assert exc.value.code == 2
    assert "not a commit" in capsys.readouterr().err


def test_main_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as clean:
        main(["docs/adr/0001-x.md"])
    assert clean.value.code == 0
    (adr_dir / "0001-x.md").write_text(
        _adr("accepted", "2026-01-01", outcome="B."), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as refused:
        main(["docs/adr/0001-x.md"])
    assert refused.value.code == 1
    assert "[ERROR]" in capsys.readouterr().err


# --- MS-14-007: the dependent counted in a material edit -------------------


@pytest.mark.spec("MS-14-007")
def test_material_edit_counts_the_dependent_on_the_head() -> None:
    old = _adr("proposed", "2026-10-19")
    still_proposed = _adr("proposed", "2026-10-20")
    flipped = _adr("accepted-provisional", "2026-10-20")
    faults = edit_faults("x", old, still_proposed, TODAY, tested_on_head=True)
    assert len(faults) == 1
    assert "test-verified dependent" in faults[0]
    assert "epoch 2" in faults[0]
    assert edit_faults("x", old, flipped, TODAY, tested_on_head=True) == []


@pytest.mark.spec("MS-14-007")
def test_new_adr_with_a_dependent_must_be_provisional() -> None:
    proposed = _adr("proposed", "2026-10-20")
    provisional = _adr("accepted-provisional", "2026-10-20")
    (fault,) = edit_faults("x", None, proposed, TODAY, tested_on_head=True)
    assert "MS-14-007" in fault
    assert (
        edit_faults("x", None, provisional, TODAY, tested_on_head=True) == []
    )


@pytest.mark.spec("MS-14-009")
def test_bumping_updated_on_a_tested_adr_needs_override() -> None:
    """A dependent on the base put the ADR past epoch 1 whatever its age."""
    old = _adr("accepted-provisional", "2026-10-19")
    new = _adr("accepted-provisional", "2026-10-20", outcome="B.")
    faults = edit_faults(
        "x", old, new, TODAY, tested_on_base=True, tested_on_head=True
    )
    assert len(faults) == 1
    assert "MS-14-009" in faults[0]


# --- MS-14-012: status only moves forward ----------------------------------


@pytest.mark.spec("MS-14-012")
def test_status_ahead_carried_on_the_base_passes_the_edit_check() -> None:
    old = _adr("accepted", "2026-10-15")
    new = _adr("accepted", "2026-10-15", tail="\nAn annotation.\n")
    assert edit_faults("x", old, new, TODAY) == []


@pytest.mark.spec("MS-14-012")
def test_promotion_ahead_of_the_epoch_needs_an_override() -> None:
    old = _adr("proposed", "2026-10-15")
    new = _adr("accepted-provisional", "2026-10-15")
    (fault,) = edit_faults("x", old, new, TODAY)
    assert "MS-14-012" in fault
    assert "ahead of epoch 1" in fault


@pytest.mark.spec("MS-14-012")
def test_override_already_on_the_base_does_not_cover_a_promotion() -> None:
    held = "status_override: an earlier reason\n"
    old = _adr("proposed", "2026-10-15", extra_fm=held)
    new = _adr("accepted", "2026-10-15", extra_fm=held)
    (fault,) = edit_faults("x", old, new, TODAY)
    assert "already on the base" in fault


@pytest.mark.spec("MS-14-012")
@pytest.mark.parametrize(
    "old_override", ["", "status_override: an earlier reason\n"]
)
def test_promotion_with_an_added_or_changed_override_passes(
    old_override: str,
) -> None:
    old = _adr("proposed", "2026-10-15", extra_fm=old_override)
    new = _adr(
        "accepted",
        "2026-10-15",
        extra_fm="status_override: the maintainer promoted it\n",
    )
    assert edit_faults("x", old, new, TODAY) == []


@pytest.mark.spec("MS-14-012")
def test_promotion_onto_the_epoch_needs_no_override() -> None:
    by_clock = _adr("proposed", "2026-10-01")  # 19 days: epoch 2
    by_dependent = _adr("proposed", "2026-10-15")
    assert (
        edit_faults(
            "x",
            by_clock,
            _adr("accepted-provisional", "2026-10-01"),
            TODAY,
        )
        == []
    )
    assert (
        edit_faults(
            "x",
            by_dependent,
            _adr("accepted-provisional", "2026-10-15"),
            TODAY,
            tested_on_head=True,
        )
        == []
    )


@pytest.mark.spec("MS-14-012")
def test_moving_a_status_back_is_refused_even_with_an_override() -> None:
    old = _adr("accepted-provisional", "2026-10-01")
    new = _adr("proposed", "2026-10-01")
    (fault,) = edit_faults("x", old, new, TODAY)
    assert "moved back" in fault
    reopened = _adr(
        "proposed", "2026-10-01", extra_fm="status_override: reopened\n"
    )
    (fault,) = edit_faults("x", old, reopened, TODAY)
    assert "moved back" in fault


@pytest.mark.spec("MS-14-012")
@pytest.mark.parametrize(
    "retired, extra_fm",
    [("rejected", ""), ("deprecated", "superseded_by: 0002-y.md\n")],
)
def test_a_retired_status_revived_ahead_of_its_epoch_needs_an_override(
    retired: str, extra_fm: str
) -> None:
    old = _adr(retired, "2026-10-15", extra_fm=extra_fm)
    (fault,) = edit_faults("x", old, _adr("accepted", "2026-10-15"), TODAY)
    assert "ahead of epoch 1" in fault
    revived = _adr(
        "accepted",
        "2026-10-15",
        extra_fm="status_override: the maintainer revived it\n",
    )
    assert edit_faults("x", old, revived, TODAY) == []
    assert edit_faults("x", old, _adr("proposed", "2026-10-15"), TODAY) == []


# --- MS-14-010: the first test-verified dependent flips the status ---------


def _spec_yaml(*specs: tuple[str, str | None, str | None]) -> str:
    """Raw spec YAML holding ``(id, adr, verification)`` requirements."""
    lines = ["id: T", "groups:", "- id: T-01", "  specs:"]
    for spec_id, adr, verification in specs:
        lines.append(f"  - id: {spec_id}")
        if adr:
            lines.append(f"    adr: [{adr}]")
        if verification:
            lines.append(f"    verification: '{verification}'")
    return "\n".join(lines) + "\n"


_CHECKS = "`test/test_t.py` checks it"


def _dep_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: str = "proposed",
    spec: tuple[str, str | None, str | None] = ("T-01-001", None, None),
    test_file: bool = True,
    extra_fm: str = "",
) -> Path:
    """A repository whose HEAD holds ADR 0001, one spec and a test file."""
    adr_dir = _repo(tmp_path, monkeypatch)
    (adr_dir / "0001-x.md").write_text(
        _adr(status, "2026-10-19", extra_fm=extra_fm), encoding="utf-8"
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "t.yaml").write_text(
        _spec_yaml(spec), encoding="utf-8"
    )
    if test_file:
        (tmp_path / "test").mkdir()
        (tmp_path / "test" / "test_t.py").write_text("", encoding="utf-8")
    vcs = "g" + "it"
    _run(vcs, "add", ".")
    _run(
        vcs,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "commit",
        "-q",
        "-m",
        "base",
    )
    return adr_dir


def _set_spec(tmp_path: Path, *specs: tuple[str, str | None, str | None]):
    (tmp_path / "specs" / "t.yaml").write_text(
        _spec_yaml(*specs), encoding="utf-8"
    )


def test_one_batch_reads_every_path_at_the_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dep_repo(tmp_path, monkeypatch, spec=("T-01-001", "ADR-0001", _CHECKS))
    _set_spec(tmp_path, ("T-01-002", None, None))
    texts = _texts_at(
        "HEAD",
        ["specs/t.yaml", "specs/absent.yaml", "specs", "docs/adr/0001-x.md"],
    )

    assert list(texts) == [
        "specs/t.yaml",
        "specs/absent.yaml",
        "specs",
        "docs/adr/0001-x.md",
    ]
    assert "T-01-001" in texts["specs/t.yaml"]
    assert "T-01-002" not in texts["specs/t.yaml"]
    assert texts["specs/absent.yaml"] == texts["specs"] == ""
    assert texts["docs/adr/0001-x.md"].startswith("---")


@pytest.mark.spec("MS-14-010")
def test_dependents_are_read_from_the_base_and_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dep_repo(tmp_path, monkeypatch)
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    assert dependents_at("HEAD") == {}
    assert tree_dependents(tmp_path) == {"0001": ["T-01-001"]}


@pytest.mark.spec("MS-14-010")
def test_adding_a_requirement_that_tests_a_proposed_adr_needs_the_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_dir = _dep_repo(tmp_path, monkeypatch)
    _set_spec(
        tmp_path,
        ("T-01-001", None, None),
        ("T-01-002", "ADR-0001", _CHECKS),
    )
    (fault,) = check_change([], "HEAD", TODAY, tmp_path)
    assert fault.startswith("0001-x.md")
    assert "MS-14-010" in fault
    assert "T-01-002" in fault

    adr = adr_dir / "0001-x.md"
    adr.write_text(
        _adr("accepted-provisional", "2026-10-19"), encoding="utf-8"
    )
    assert (
        check_change([adr.relative_to(tmp_path)], "HEAD", TODAY, tmp_path)
        == []
    )


@pytest.mark.spec("MS-14-010")
@pytest.mark.parametrize(
    "spec_on_base",
    [
        ("T-01-001", None, _CHECKS),  # the change adds adr:
        ("T-01-001", "ADR-0001", None),  # the change adds the verification
    ],
)
def test_editing_a_requirement_into_a_dependent_needs_the_flip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_on_base: tuple[str, str | None, str | None],
) -> None:
    _dep_repo(tmp_path, monkeypatch, spec=spec_on_base)
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    (fault,) = check_change([], "HEAD", TODAY, tmp_path)
    assert "MS-14-010" in fault


@pytest.mark.spec("MS-14-010")
def test_adding_the_named_test_file_needs_the_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dep_repo(
        tmp_path,
        monkeypatch,
        spec=("T-01-001", "ADR-0001", _CHECKS),
        test_file=False,
    )
    assert check_change([], "HEAD", TODAY, tmp_path) == []
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_t.py").write_text("", encoding="utf-8")
    # An untracked file is not yet part of the change, as it is not in CI.
    assert check_change([], "HEAD", TODAY, tmp_path) == []
    _run("g" + "it", "add", "test/test_t.py")
    (fault,) = check_change([], "HEAD", TODAY, tmp_path)
    assert "MS-14-010" in fault


@pytest.mark.spec("MS-14-010")
@pytest.mark.parametrize(
    "status, extra_fm",
    [
        ("accepted-provisional", ""),
        ("accepted", ""),
    ],
)
def test_a_dependent_of_an_adr_past_epoch_one_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    extra_fm: str,
) -> None:
    _dep_repo(tmp_path, monkeypatch, status=status, extra_fm=extra_fm)
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    assert check_change([], "HEAD", TODAY, tmp_path) == []


@pytest.mark.spec("MS-14-010")
def test_only_an_override_the_change_adds_holds_back_the_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An override already on the base was written for another reason."""
    held = "status_override: an earlier reason\n"
    adr_dir = _dep_repo(tmp_path, monkeypatch, extra_fm=held)
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    (fault,) = check_change([], "HEAD", TODAY, tmp_path)
    assert "MS-14-010" in fault
    adr = adr_dir / "0001-x.md"
    adr.write_text(
        _adr(
            "proposed",
            "2026-10-19",
            extra_fm="status_override: the maintainer holds it\n",
        ),
        encoding="utf-8",
    )
    assert (
        check_change([adr.relative_to(tmp_path)], "HEAD", TODAY, tmp_path)
        == []
    )


@pytest.mark.spec("MS-14-010")
def test_a_new_adr_with_a_dependent_is_reported_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new ADR is held to its epoch by the edit rule, not the flip rule."""
    adr_dir = _dep_repo(tmp_path, monkeypatch)
    new = adr_dir / "0002-new.md"
    new.write_text(_adr("proposed", "2026-10-20"), encoding="utf-8")
    _set_spec(tmp_path, ("T-01-001", "ADR-0002", _CHECKS))
    (fault,) = check_change(
        [new.relative_to(tmp_path)], "HEAD", TODAY, tmp_path
    )
    assert fault.startswith("0002-new.md")
    assert "MS-14-007" in fault


@pytest.mark.spec("MS-14-010")
def test_a_bumped_adr_left_off_its_epoch_is_reported_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The material-edit rule already names the missing flip."""
    adr_dir = _dep_repo(tmp_path, monkeypatch)
    adr = adr_dir / "0001-x.md"
    adr.write_text(_adr("proposed", "2026-10-20"), encoding="utf-8")
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    (fault,) = check_change(
        [adr.relative_to(tmp_path)], "HEAD", TODAY, tmp_path
    )
    assert "MS-14-007" in fault


@pytest.mark.spec("MS-14-010")
def test_a_bump_under_a_base_override_still_needs_the_flip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    held = "status_override: an earlier reason\n"
    adr_dir = _dep_repo(tmp_path, monkeypatch, extra_fm=held)
    adr = adr_dir / "0001-x.md"
    adr.write_text(
        _adr("proposed", "2026-10-20", extra_fm=held), encoding="utf-8"
    )
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    (fault,) = check_change(
        [adr.relative_to(tmp_path)], "HEAD", TODAY, tmp_path
    )
    assert "MS-14-010" in fault


@pytest.mark.spec("MS-14-010")
def test_an_untracked_spec_file_is_not_part_of_the_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dep_repo(tmp_path, monkeypatch)
    (tmp_path / "specs" / "u.yaml").write_text(
        _spec_yaml(("U-01-001", "ADR-0001", _CHECKS)), encoding="utf-8"
    )
    assert check_change([], "HEAD", TODAY, tmp_path) == []
    _run("g" + "it", "add", "specs/u.yaml")
    (fault,) = check_change([], "HEAD", TODAY, tmp_path)
    assert "U-01-001" in fault


@pytest.mark.spec("MS-14-010")
def test_a_malformed_spec_names_its_file_and_exits_2(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _dep_repo(tmp_path, monkeypatch)
    (tmp_path / "specs" / "t.yaml").write_text(
        "groups:\n- specs:\n  - id: T-01-001\n    adr: ADR-0001\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        main(["--base", "HEAD"])
    assert exc.value.code == 2
    assert "t.yaml" in capsys.readouterr().err


@pytest.mark.spec("MS-14-010")
def test_a_dependent_already_on_the_base_is_not_the_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The change that created the dependent owned the flip, not this one."""
    _dep_repo(tmp_path, monkeypatch, spec=("T-01-001", "ADR-0001", _CHECKS))
    _set_spec(
        tmp_path,
        ("T-01-001", "ADR-0001", _CHECKS),
        ("T-01-002", "ADR-0001", _CHECKS),
    )
    assert check_change([], "HEAD", TODAY, tmp_path) == []


@pytest.mark.spec("MS-14-010")
def test_main_fails_a_first_dependent_with_no_adr_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _dep_repo(tmp_path, monkeypatch)
    _set_spec(tmp_path, ("T-01-001", "ADR-0001", _CHECKS))
    with pytest.raises(SystemExit) as exc:
        main(["--base", "HEAD"])
    assert exc.value.code == 1
    assert "MS-14-010" in capsys.readouterr().err


@pytest.mark.spec("MS-14-007")
def test_epoch_drift_counts_dependents_in_the_tree(tmp_path: Path) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        _adr("proposed", "2026-10-19"), encoding="utf-8"
    )
    assert epoch_drift(tmp_path, TODAY) == []
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "t.yaml").write_text(
        _spec_yaml(("T-01-001", "ADR-0001", _CHECKS)), encoding="utf-8"
    )
    (tmp_path / "test").mkdir()
    (tmp_path / "test" / "test_t.py").write_text("", encoding="utf-8")
    (fault,) = epoch_drift(tmp_path, TODAY)
    assert fault.startswith("0001-x.md")


@pytest.mark.spec("MS-14-012")
def test_epoch_drift_never_lists_a_status_ahead_of_its_epoch(
    tmp_path: Path,
) -> None:
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        _adr("accepted", "2026-10-19"), encoding="utf-8"
    )
    assert epoch_drift(tmp_path, TODAY) == []


@pytest.mark.spec("MS-14-009")
def test_an_override_holding_a_status_back_keeps_its_epoch_for_the_tiers() -> (
    None
):
    """A proposed ADR held past day 28 is not frozen as if epoch 3."""
    held = "status_override: the maintainer holds it\n"
    old = _adr("proposed", "2026-01-01", extra_fm=held)
    new = _adr("proposed", "2026-01-01", outcome="B.", extra_fm=held)
    assert edit_faults("x", old, new, TODAY) == []


@pytest.mark.spec("MS-14-009")
def test_an_accepted_adr_is_frozen_however_recently_updated() -> None:
    """A status ahead of the clock stands, so its edit tier does too."""
    old = _adr("accepted", "2026-10-15")
    new = _adr("accepted", "2026-10-15", outcome="B.")
    (fault,) = edit_faults("x", old, new, TODAY)
    assert "Decision Outcome" in fault


@pytest.mark.spec("MS-14-012")
def test_a_material_promotion_ahead_reports_both_faults() -> None:
    """Every violation is reported, not only the first (EH-07-001)."""
    old = _adr("proposed", "2026-10-19")
    new = _adr("accepted", "2026-10-20")
    faults = edit_faults("x", old, new, TODAY)
    assert any("MS-14-007" in f for f in faults)
    assert any("MS-14-012" in f for f in faults)
