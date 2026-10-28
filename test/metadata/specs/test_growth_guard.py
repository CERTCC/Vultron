"""Tests for vultron.metadata.specs.growth_guard (SR-05-005, MS-12-007, MS-10-014,
MS-10-016).

Each test builds a throwaway git repository whose ``origin/main`` ref is the
base, edits the working tree, and runs a real guard extractor through
:func:`added_since_base`: the marker-coverage guard over ``protocol`` and
``foundation`` specs (:func:`uncovered_implementer_ids`), the
``missing_story_reference`` guard (:func:`missing_story_suppression_carriers`),
the missing-rationale guard (:func:`missing_rationale_ids`), and the
``verification_debt`` guard (:func:`verification_debt_items`).
"""

import logging
import os
import subprocess
from pathlib import Path

import pytest
import yaml

from vultron.metadata.specs.coverage import (
    kinds_and_markers,
    markers_dropped_by_kind_change,
    uncovered_implementer_ids,
)
from vultron.metadata.specs.growth_guard import (
    BASE_REF_ENV,
    CI_ENV,
    DEFAULT_BASE_REF,
    BaseExtractionError,
    BaseUnavailableError,
    ChangedFiles,
    GrowthCheck,
    added_since_base,
    base_ref_name,
    changed_files,
    compare_changed_with_base,
    compare_with_base,
    running_in_ci,
)
from vultron.metadata.specs.kind_classification import (
    missing_story_suppression_carriers,
)
from vultron.metadata.specs.rationale import missing_rationale_ids
from vultron.metadata.specs.verification import verification_debt_items

_SUPPRESS = ["missing_story_reference"]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _spec(spec_id: str, kind: str = "protocol", **extra) -> dict:
    return {
        "id": spec_id,
        "priority": "MUST",
        "kind": kind,
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
        **extra,
    }


def _write_specs(repo: Path, *specs: dict) -> None:
    (repo / "specs").mkdir(exist_ok=True)
    data = {
        "id": "TST",
        "title": "Test File",
        "description": "Test spec file",
        "scope": ["production"],
        "groups": [{"id": "TST-01", "title": "Group", "specs": list(specs)}],
    }
    (repo / "specs" / "tst.yaml").write_text(yaml.dump(data))


def _write_markers(repo: Path, *spec_ids: str) -> None:
    (repo / "test").mkdir(exist_ok=True)
    body = "".join(
        f'@pytest.mark.spec("{sid}")\ndef test_{i}():\n    pass\n\n'
        for i, sid in enumerate(spec_ids)
    )
    (repo / "test" / "test_x.py").write_text("import pytest\n\n" + body)


def _repo(tmp_path: Path, specs: list[dict], markers: list[str]) -> Path:
    """A repository whose committed tree is the base, at ``origin/main``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _write_specs(repo, *specs)
    _write_markers(repo, *markers)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def _coverage(repo: Path):
    return added_since_base(
        uncovered_implementer_ids, repo_root=repo, paths=("specs", "test")
    )


def _suppressions(repo: Path):
    return added_since_base(
        missing_story_suppression_carriers, repo_root=repo, paths=("specs",)
    )


@pytest.fixture(autouse=True)
def _no_ci_base_ref(monkeypatch):
    """Run as a local checkout would, even when the suite runs in CI."""
    monkeypatch.delenv(BASE_REF_ENV, raising=False)
    monkeypatch.delenv(CI_ENV, raising=False)


def _kind_change_drops(repo: Path) -> frozenset[str] | None:
    seen = compare_with_base(
        kinds_and_markers, repo_root=repo, paths=("specs", "test")
    )
    if seen.base_value is None:
        return None
    return markers_dropped_by_kind_change(seen.base_value, seen.head_value)


# --- implementer-coverage guard (SR-05-005) ---------------------------------


@pytest.fixture
def coverage_repo(tmp_path):
    """Base: TST-01-001 covered, TST-01-002 uncovered, TST-01-003 project."""
    return _repo(
        tmp_path,
        [
            _spec("TST-01-001"),
            _spec("TST-01-002"),
            _spec("TST-01-003", "project"),
        ],
        ["TST-01-001"],
    )


@pytest.mark.spec("SR-05-005")
def test_coverage_unchanged_adds_nothing(coverage_repo):
    check = _coverage(coverage_repo)
    assert check.skipped is None
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("SR-05-005")
def test_coverage_new_protocol_spec_without_marker_is_added(coverage_repo):
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
        _spec("TST-01-004"),
    )
    assert _coverage(coverage_repo).added == {"TST-01-004"}


@pytest.mark.spec("SR-05-005")
def test_coverage_removing_last_marker_is_added(coverage_repo):
    _write_markers(coverage_repo)
    assert _coverage(coverage_repo).added == {"TST-01-001"}


@pytest.mark.spec("SR-05-005")
def test_coverage_new_marker_is_not_an_addition(coverage_repo):
    _write_markers(coverage_repo, "TST-01-001", "TST-01-002")
    check = _coverage(coverage_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("SR-05-005")
def test_coverage_relabel_into_protocol_without_marker_is_added(coverage_repo):
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "protocol"),
    )
    assert _coverage(coverage_repo).added == {"TST-01-003"}


@pytest.mark.spec("SR-05-005")
def test_coverage_relabel_out_of_protocol_is_not_an_addition(coverage_repo):
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002", "project"),
        _spec("TST-01-003", "project"),
    )
    check = _coverage(coverage_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("SR-05-005")
def test_coverage_new_foundation_spec_without_marker_is_added(coverage_repo):
    """foundation is guarded with protocol (ADR-0134)."""
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
        _spec("TST-01-004", "foundation", tags=["http"]),
    )
    assert _coverage(coverage_repo).added == {"TST-01-004"}


@pytest.mark.spec("SR-05-005")
def test_coverage_relabel_protocol_to_foundation_keeps_its_marker(
    coverage_repo,
):
    """A covered protocol spec relabeled to foundation stays covered."""
    _write_specs(
        coverage_repo,
        _spec("TST-01-001", "foundation", tags=["as2"]),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    check = _coverage(coverage_repo)
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("SR-05-005")
def test_coverage_relabel_uncovered_protocol_to_foundation_is_not_an_addition(
    coverage_repo,
):
    """An uncovered protocol spec relabeled to foundation was already owed."""
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002", "foundation", tags=["activitypub"]),
        _spec("TST-01-003", "project"),
    )
    check = _coverage(coverage_repo)
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("SR-05-005")
def test_coverage_retired_spec_is_not_an_addition(coverage_repo):
    _write_specs(
        coverage_repo, _spec("TST-01-001"), _spec("TST-01-003", "project")
    )
    assert _coverage(coverage_repo).added == frozenset()


@pytest.mark.spec("SR-05-005")
def test_coverage_committed_change_is_compared_from_merge_base(coverage_repo):
    """A committed branch change is caught, not only an uncommitted one."""
    _git(coverage_repo, "checkout", "-q", "-b", "feature")
    _write_markers(coverage_repo)
    _git(coverage_repo, "commit", "-qam", "drop marker")
    assert _coverage(coverage_repo).added == {"TST-01-001"}


@pytest.mark.spec("SR-05-005")
def test_coverage_without_base_ref_skips_with_logged_reason(
    coverage_repo, caplog
):
    _git(coverage_repo, "update-ref", "-d", "refs/remotes/origin/main")
    _write_markers(coverage_repo)
    with caplog.at_level(logging.WARNING):
        check = _coverage(coverage_repo)
    assert check.skipped is not None
    assert "origin/main" in check.skipped
    assert check.added == frozenset()
    assert check.skipped in caplog.text


# --- kind-change marker guard (MS-12-011) -----------------------------------


@pytest.mark.spec("MS-12-011")
def test_kind_change_dropping_its_marker_is_reported(coverage_repo):
    """protocol -> project still keeps the marker it had."""
    _write_specs(
        coverage_repo,
        _spec("TST-01-001", "project"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    _write_markers(coverage_repo)
    assert _kind_change_drops(coverage_repo) == {"TST-01-001"}


@pytest.mark.spec("MS-12-011")
def test_kind_change_keeping_its_marker_is_not_reported(coverage_repo):
    _write_specs(
        coverage_repo,
        _spec("TST-01-001", "project"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    assert _kind_change_drops(coverage_repo) == frozenset()


@pytest.mark.spec("MS-12-011")
def test_marker_dropped_without_kind_change_is_not_this_guards(tmp_path):
    """Dropping a project spec's marker with no relabel is not MS-12-011."""
    repo = _repo(tmp_path, [_spec("TST-01-001", "project")], ["TST-01-001"])
    _write_markers(repo)
    assert _kind_change_drops(repo) == frozenset()


@pytest.mark.spec("MS-12-011")
def test_kind_change_of_unmarked_spec_is_not_reported(coverage_repo):
    _write_specs(
        coverage_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002", "project"),
        _spec("TST-01-003", "project"),
    )
    assert _kind_change_drops(coverage_repo) == frozenset()


@pytest.mark.spec("MS-12-011")
def test_retired_marked_spec_is_not_a_kind_change(coverage_repo):
    _write_specs(
        coverage_repo, _spec("TST-01-002"), _spec("TST-01-003", "project")
    )
    _write_markers(coverage_repo)
    assert _kind_change_drops(coverage_repo) == frozenset()


@pytest.mark.spec("MS-12-011")
def test_kind_change_guard_without_base_ref_skips(coverage_repo):
    _git(coverage_repo, "update-ref", "-d", "refs/remotes/origin/main")
    assert _kind_change_drops(coverage_repo) is None


# --- missing_story_reference guard (MS-12-007) -------------------------------


@pytest.fixture
def suppression_repo(tmp_path):
    """Base: TST-01-001 carries the suppression, TST-01-002 and -003 do not."""
    return _repo(
        tmp_path,
        [
            _spec("TST-01-001", lint_suppress=_SUPPRESS),
            _spec("TST-01-002"),
            _spec("TST-01-003", "project"),
        ],
        [],
    )


@pytest.mark.spec("MS-12-007")
def test_suppression_unchanged_adds_nothing(suppression_repo):
    check = _suppressions(suppression_repo)
    assert check.skipped is None
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-12-007")
def test_suppression_gained_is_added(suppression_repo):
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002", lint_suppress=_SUPPRESS),
        _spec("TST-01-003", "project"),
    )
    assert _suppressions(suppression_repo).added == {"TST-01-002"}


@pytest.mark.spec("MS-12-007")
def test_suppression_on_new_spec_is_added(suppression_repo):
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
        _spec("TST-01-004", lint_suppress=_SUPPRESS),
    )
    assert _suppressions(suppression_repo).added == {"TST-01-004"}


@pytest.mark.spec("MS-12-007")
def test_suppression_removed_is_not_an_addition(suppression_repo):
    _write_specs(
        suppression_repo,
        _spec("TST-01-001"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    check = _suppressions(suppression_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("MS-12-007")
def test_suppression_relabel_in_with_suppression_is_added(suppression_repo):
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002"),
        _spec("TST-01-003", "protocol", lint_suppress=_SUPPRESS),
    )
    assert _suppressions(suppression_repo).added == {"TST-01-003"}


@pytest.mark.spec("MS-12-007")
def test_suppression_relabel_out_is_not_an_addition(suppression_repo):
    """``relabel_spec_kinds.py`` strips the suppression with the old kind."""
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", "project"),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    assert _suppressions(suppression_repo).added == frozenset()


@pytest.mark.spec("MS-12-007")
def test_suppression_kept_through_relabel_in_is_not_an_addition(
    suppression_repo,
):
    """A carrier that already had the code is not new because its kind is."""
    _git(suppression_repo, "checkout", "-q", "-b", "base-project")
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project", lint_suppress=_SUPPRESS),
    )
    _git(suppression_repo, "commit", "-qam", "project carrier")
    _git(suppression_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002"),
        _spec("TST-01-003", "protocol", lint_suppress=_SUPPRESS),
    )
    check = _suppressions(suppression_repo)
    assert check.added == frozenset()
    assert check.head_total == 2


@pytest.mark.spec("MS-12-007")
def test_suppression_kept_through_relabel_out_is_not_an_addition(
    suppression_repo,
):
    """A carrier relabelled out of protocol still counts, and is not new."""
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", "project", lint_suppress=_SUPPRESS),
        _spec("TST-01-002"),
        _spec("TST-01-003", "project"),
    )
    check = _suppressions(suppression_repo)
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-12-007")
def test_suppression_without_base_ref_skips_with_logged_reason(
    suppression_repo, caplog
):
    _git(suppression_repo, "update-ref", "-d", "refs/remotes/origin/main")
    _write_specs(
        suppression_repo, _spec("TST-01-001", lint_suppress=_SUPPRESS)
    )
    with caplog.at_level(logging.WARNING):
        check = _suppressions(suppression_repo)
    assert check.skipped is not None
    assert check.added == frozenset()
    assert check.skipped in caplog.text


# --- missing-rationale guard (MS-10-014) ------------------------------------


def _no_rationale(spec_id: str, kind: str = "project") -> dict:
    spec = _spec(spec_id, kind)
    del spec["rationale"]
    return spec


def _rationales(repo: Path):
    return added_since_base(
        missing_rationale_ids, repo_root=repo, paths=("specs",)
    )


@pytest.fixture
def rationale_repo(tmp_path):
    """Base: TST-01-001 has a rationale, TST-01-002 already lacks one."""
    return _repo(
        tmp_path, [_spec("TST-01-001"), _no_rationale("TST-01-002")], []
    )


@pytest.mark.spec("MS-10-014")
def test_rationale_unchanged_adds_nothing(rationale_repo):
    check = _rationales(rationale_repo)
    assert check.skipped is None
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-10-014")
def test_rationale_new_requirement_without_one_is_added(rationale_repo):
    _write_specs(
        rationale_repo,
        _spec("TST-01-001"),
        _no_rationale("TST-01-002"),
        _no_rationale("TST-01-003"),
    )
    assert _rationales(rationale_repo).added == {"TST-01-003"}


@pytest.mark.spec("MS-10-014")
def test_rationale_dropped_from_existing_requirement_is_added(rationale_repo):
    _write_specs(
        rationale_repo,
        _no_rationale("TST-01-001"),
        _no_rationale("TST-01-002"),
    )
    assert _rationales(rationale_repo).added == {"TST-01-001"}


@pytest.mark.spec("MS-10-014")
def test_rationale_existing_gap_is_not_flagged(rationale_repo):
    """A requirement missing one at the base stays the backfill's, even edited."""
    edited = _no_rationale("TST-01-002")
    edited["statement"] = "TST-01-002 MUST do another thing"
    _write_specs(rationale_repo, _spec("TST-01-001"), edited)
    check = _rationales(rationale_repo)
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-10-014")
def test_rationale_backfilled_is_not_an_addition(rationale_repo):
    _write_specs(rationale_repo, _spec("TST-01-001"), _spec("TST-01-002"))
    check = _rationales(rationale_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("MS-10-014")
def test_rationale_retired_is_not_an_addition(rationale_repo):
    _write_specs(rationale_repo, _spec("TST-01-001"))
    check = _rationales(rationale_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("MS-10-014")
def test_rationale_without_base_ref_skips_with_logged_reason(
    rationale_repo, caplog
):
    _git(rationale_repo, "update-ref", "-d", "refs/remotes/origin/main")
    _write_specs(rationale_repo, _no_rationale("TST-01-001"))
    with caplog.at_level(logging.WARNING):
        check = _rationales(rationale_repo)
    assert check.skipped is not None
    assert check.added == frozenset()
    assert check.skipped in caplog.text


# --- verification_debt guard (MS-10-016) ------------------------------------


def _marked(spec_id: str, marker: str = "#1", kind: str = "project") -> dict:
    return _spec(spec_id, kind, verification_debt=marker)


def _verified(spec_id: str, kind: str = "project") -> dict:
    return _spec(spec_id, kind, verification="A test proves it.")


def _debt(repo: Path):
    return added_since_base(
        verification_debt_items, repo_root=repo, paths=("specs",)
    )


@pytest.fixture
def debt_repo(tmp_path):
    """Base: TST-01-001 carries a marker, TST-01-002 is verified."""
    return _repo(
        tmp_path, [_marked("TST-01-001"), _verified("TST-01-002")], []
    )


@pytest.mark.spec("MS-10-016")
def test_debt_unchanged_adds_nothing(debt_repo):
    check = _debt(debt_repo)
    assert check.skipped is None
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-10-016")
def test_debt_marker_on_new_requirement_is_added(debt_repo):
    _write_specs(
        debt_repo,
        _marked("TST-01-001"),
        _verified("TST-01-002"),
        _marked("TST-01-003"),
    )
    assert _debt(debt_repo).added == {"TST-01-003 verification_debt: '#1'"}


@pytest.mark.spec("MS-10-016")
def test_debt_marker_replacing_verification_is_added(debt_repo):
    _write_specs(debt_repo, _marked("TST-01-001"), _marked("TST-01-002"))
    assert _debt(debt_repo).added == {"TST-01-002 verification_debt: '#1'"}


@pytest.mark.spec("MS-10-016")
def test_debt_marker_removed_is_not_an_addition(debt_repo):
    _write_specs(debt_repo, _verified("TST-01-001"), _verified("TST-01-002"))
    check = _debt(debt_repo)
    assert check.added == frozenset()
    assert check.head_total == 0


@pytest.mark.spec("MS-10-016")
def test_debt_marked_requirement_edited_is_not_an_addition(debt_repo):
    """Rewording a marked requirement keeps the debt the base already had."""
    edited = _marked("TST-01-001")
    edited["statement"] = "TST-01-001 MUST do another thing"
    _write_specs(debt_repo, edited, _verified("TST-01-002"))
    assert _debt(debt_repo).added == frozenset()


@pytest.mark.spec("MS-10-016")
def test_debt_marker_moved_to_another_file_is_not_an_addition(debt_repo):
    """A marker that moves with its requirement is the same item."""
    _write_specs(debt_repo, _verified("TST-01-002"))
    moved = {
        "id": "OTH",
        "title": "Other File",
        "description": "Other spec file",
        "scope": ["production"],
        "groups": [
            {
                "id": "OTH-01",
                "title": "Group",
                "specs": [_marked("TST-01-001")],
            }
        ],
    }
    (debt_repo / "specs" / "oth.yaml").write_text(yaml.dump(moved))
    check = _debt(debt_repo)
    assert check.added == frozenset()
    assert check.head_total == 1


@pytest.mark.spec("MS-10-016")
def test_debt_marked_requirement_renamed_is_added(debt_repo):
    """A new ID is a new requirement, so its marker is new debt."""
    _write_specs(debt_repo, _marked("TST-01-003"), _verified("TST-01-002"))
    assert _debt(debt_repo).added == {"TST-01-003 verification_debt: '#1'"}


@pytest.mark.spec("MS-10-016")
def test_debt_relabel_keeping_its_marker_is_not_an_addition(debt_repo):
    """spec-lint, not this guard, fails a marker its new kind does not own."""
    _write_specs(
        debt_repo,
        _marked("TST-01-001", kind="architecture"),
        _verified("TST-01-002"),
    )
    assert _debt(debt_repo).added == frozenset()


@pytest.mark.spec("MS-10-016")
def test_debt_relabel_repointing_its_marker_is_added(debt_repo):
    """Swapping in the destination kind's owner adds debt to its backlog."""
    _write_specs(
        debt_repo,
        _marked("TST-01-001", marker="#2", kind="architecture"),
        _verified("TST-01-002"),
    )
    assert _debt(debt_repo).added == {"TST-01-001 verification_debt: '#2'"}


@pytest.mark.spec("MS-10-016")
def test_debt_without_base_ref_skips_with_logged_reason(debt_repo, caplog):
    _git(debt_repo, "update-ref", "-d", "refs/remotes/origin/main")
    _write_specs(debt_repo, _marked("TST-01-001"), _marked("TST-01-002"))
    with caplog.at_level(logging.WARNING):
        check = _debt(debt_repo)
    assert check.skipped is not None
    assert check.added == frozenset()
    assert check.skipped in caplog.text


# --- base resolution ---------------------------------------------------------


def test_base_ref_defaults_to_origin_main():
    assert base_ref_name({}) == DEFAULT_BASE_REF == "origin/main"


@pytest.mark.parametrize("value", ["", "  "])
def test_blank_github_base_ref_falls_through_to_default(value):
    """A ``push`` run sets ``GITHUB_BASE_REF`` to the empty string."""
    assert base_ref_name({BASE_REF_ENV: value}) == DEFAULT_BASE_REF


def test_github_base_ref_names_the_remote_branch(
    suppression_repo, monkeypatch
):
    _git(suppression_repo, "update-ref", "refs/remotes/origin/release", "HEAD")
    _git(suppression_repo, "update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv(BASE_REF_ENV, "release")
    assert base_ref_name() == "origin/release"
    _write_specs(
        suppression_repo, _spec("TST-01-002", lint_suppress=_SUPPRESS)
    )
    check = _suppressions(suppression_repo)
    assert check.skipped is None
    assert check.added == {"TST-01-002"}


def test_unrelated_history_skips(suppression_repo, tmp_path):
    """A base sharing no history with HEAD (a shallow clone) is no base."""
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q", "-b", "main")
    (other / "f").write_text("x")
    _git(other, "add", "-A")
    _git(other, "commit", "-q", "-m", "unrelated")
    _git(
        suppression_repo,
        "fetch",
        "-q",
        str(other),
        "+main:refs/remotes/origin/main",
    )
    check = _suppressions(suppression_repo)
    assert check.skipped is not None
    assert "merge base" in check.skipped


def test_guarded_path_absent_at_base_reads_as_empty(tmp_path):
    """A guarded tree that is new on the branch has an empty base set."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README").write_text("x")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    _write_specs(repo, _spec("TST-01-001", lint_suppress=_SUPPRESS))
    assert _suppressions(repo).added == {"TST-01-001"}


def test_extractor_error_on_base_tree_names_the_merge_base(suppression_repo):
    """A guard that cannot read the base must not read as a pass."""
    base = _git(suppression_repo, "rev-parse", "HEAD").strip()
    (suppression_repo / "specs" / "notes.txt").write_text("a change to read")

    def extract(root: Path) -> frozenset[str]:
        if root != suppression_repo:
            raise ValueError("unknown field")
        return frozenset({"X"})

    with pytest.raises(BaseExtractionError) as excinfo:
        added_since_base(extract, repo_root=suppression_repo, paths=("specs",))
    message = str(excinfo.value)
    assert "unknown field" in message
    assert base[:12] in message
    assert "accept the old form" in message
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_extractor_error_on_working_tree_propagates_unchanged(
    suppression_repo,
):
    def extract(root: Path) -> frozenset[str]:
        raise ValueError("bad head")

    with pytest.raises(ValueError, match="bad head"):
        added_since_base(extract, repo_root=suppression_repo, paths=("specs",))


def test_missing_base_raises_when_required(suppression_repo):
    _git(suppression_repo, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(BaseUnavailableError, match="origin/main"):
        added_since_base(
            missing_story_suppression_carriers,
            repo_root=suppression_repo,
            paths=("specs",),
            require_base=True,
        )


def test_missing_base_raises_under_github_actions(
    suppression_repo, monkeypatch
):
    """In CI a lost checkout history fails the guard rather than skipping."""
    _git(suppression_repo, "update-ref", "-d", "refs/remotes/origin/main")
    monkeypatch.setenv(CI_ENV, "true")
    with pytest.raises(BaseUnavailableError):
        _suppressions(suppression_repo)


@pytest.mark.parametrize(
    ("env", "expected"),
    [({}, False), ({CI_ENV: ""}, False), ({CI_ENV: "true"}, True)],
)
def test_running_in_ci_reads_github_actions(env, expected):
    assert running_in_ci(env) is expected


def test_missing_git_binary_is_an_unavailable_base(
    suppression_repo, monkeypatch, caplog
):
    monkeypatch.setenv("PATH", str(suppression_repo / "no-such-bin"))
    with caplog.at_level(logging.WARNING):
        check = added_since_base(
            lambda root: frozenset(),
            repo_root=suppression_repo,
            paths=("specs",),
        )
    assert check.skipped is not None
    assert "git is not available" in check.skipped


def test_precomputed_head_is_used_instead_of_extracting(suppression_repo):
    """A caller may pass the head set it built from an in-memory corpus."""
    (suppression_repo / "specs" / "notes.txt").write_text("a change to read")
    check = added_since_base(
        missing_story_suppression_carriers,
        repo_root=suppression_repo,
        paths=("specs",),
        head=frozenset({"TST-01-001", "TST-01-009"}),
    )
    assert check.added == {"TST-01-009"}
    assert check.head_total == 2


def test_in_memory_test_sources_match_the_tree_scan(coverage_repo):
    """``test_sources`` yields the same set as reading ``test/`` from disk."""
    sources = [p.read_text() for p in (coverage_repo / "test").rglob("*.py")]
    assert uncovered_implementer_ids(
        coverage_repo, test_sources=sources
    ) == uncovered_implementer_ids(coverage_repo)


def test_failure_message_lists_each_added_item(suppression_repo):
    _write_specs(
        suppression_repo,
        _spec("TST-01-001", lint_suppress=_SUPPRESS),
        _spec("TST-01-002", lint_suppress=_SUPPRESS),
        _spec("TST-01-003", "project", lint_suppress=_SUPPRESS),
    )
    message = _suppressions(suppression_repo).failure_message(
        "carrier(s)", "Fix it."
    )
    assert "2 carrier(s) added" in message
    assert "  TST-01-002\n  TST-01-003\n" in message
    assert "\nFix it.\n" in message
    assert "git fetch origin" in message


def test_failure_message_without_a_head_total_omits_the_count():
    check = GrowthCheck("a" * 40, frozenset({"X"}), None)
    message = check.failure_message("item(s)", "Fix it.")
    assert "1 item(s) added since the merge base aaaaaaaaaaaa:\n" in message
    assert "in the working tree" not in message


@pytest.fixture
def files_repo(tmp_path: Path) -> Path:
    """A base with three tracked files under ``d/`` and one outside it."""
    repo = tmp_path / "repo"
    (repo / "d").mkdir(parents=True)
    for name in ("kept", "edited", "gone"):
        (repo / "d" / name).write_text(name)
    (repo / "outside").write_text("x")
    (repo / ".gitignore").write_text("*.ignored\n")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def test_changed_files_lists_each_kind_of_change(files_repo):
    base = _git(files_repo, "rev-parse", "HEAD").strip()
    (files_repo / "d" / "edited").write_text("edited again")
    (files_repo / "d" / "gone").unlink()
    (files_repo / "d" / "untracked").write_text("new")
    (files_repo / "d" / "staged").write_text("new")
    _git(files_repo, "add", "d/staged")
    (files_repo / "d" / "x.ignored").write_text("ignored")
    (files_repo / "outside").write_text("changed, but not under d/")
    changed = changed_files(files_repo, base, ("d",))
    assert sorted(changed.at_base) == ["d/edited", "d/gone"]
    assert sorted(changed.at_head) == ["d/edited", "d/staged", "d/untracked"]


def test_changed_files_lists_both_names_of_a_rename(files_repo):
    base = _git(files_repo, "rev-parse", "HEAD").strip()
    _git(files_repo, "mv", "d/kept", "d/moved")
    _git(files_repo, "commit", "-q", "-m", "rename")
    changed = changed_files(files_repo, base, ("d",))
    assert changed.at_base == ("d/kept",)
    assert changed.at_head == ("d/moved",)


def test_changed_files_with_no_paths_is_empty(files_repo):
    base = _git(files_repo, "rev-parse", "HEAD").strip()
    assert changed_files(files_repo, base, ()) == ChangedFiles((), ())


def _file_names(root: Path) -> frozenset[str]:
    return frozenset(
        p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
    )


def test_compare_changed_reads_only_the_changed_files(files_repo):
    (files_repo / "d" / "edited").write_text("edited again")
    (files_repo / "d" / "new").write_text("new")
    seen = compare_changed_with_base(
        _file_names, repo_root=files_repo, paths=("d",)
    )
    assert seen.base_value == {"d/edited"}
    assert seen.head_value == {"d/edited", "d/new"}
    assert seen.skipped is None


def test_compare_changed_with_nothing_changed_reads_empty_trees(files_repo):
    seen = compare_changed_with_base(
        _file_names, repo_root=files_repo, paths=("d",)
    )
    assert seen.base_value == frozenset()
    assert seen.head_value == frozenset()


def test_compare_changed_without_base_reads_the_whole_tree(files_repo):
    _git(files_repo, "update-ref", "-d", "refs/remotes/origin/main")
    seen = compare_changed_with_base(
        _file_names, repo_root=files_repo, paths=("d",)
    )
    assert seen.skipped is not None
    assert seen.base_value is None
    assert {"d/kept", "d/edited", "d/gone"} <= seen.head_value


def test_compare_changed_without_base_raises_when_required(files_repo):
    _git(files_repo, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(BaseUnavailableError):
        compare_changed_with_base(
            _file_names, repo_root=files_repo, paths=("d",), require_base=True
        )


def test_compare_changed_names_the_merge_base_on_a_base_error(files_repo):
    base = _git(files_repo, "rev-parse", "HEAD").strip()
    (files_repo / "d" / "edited").write_text("edited again")

    def read(root: Path) -> frozenset[str]:
        if root.name == "base":
            raise ValueError("unknown field")
        return frozenset()

    with pytest.raises(BaseExtractionError, match=base[:12]):
        compare_changed_with_base(read, repo_root=files_repo, paths=("d",))


def test_an_unchanged_tree_is_not_read_at_the_base(suppression_repo):
    """With nothing under the paths changed, the head result is the base's."""
    reads: list[Path] = []

    def extract(root: Path) -> frozenset[str]:
        reads.append(root)
        return frozenset({"X"})

    seen = compare_with_base(
        extract, repo_root=suppression_repo, paths=("specs",)
    )
    assert reads == [suppression_repo]
    assert seen.base_value == seen.head_value == {"X"}
    assert seen.base == _git(suppression_repo, "rev-parse", "HEAD").strip()


def test_a_change_outside_the_paths_does_not_read_the_base(suppression_repo):
    (suppression_repo / "elsewhere.txt").write_text("not a guarded path")
    reads: list[Path] = []

    def extract(root: Path) -> frozenset[str]:
        reads.append(root)
        return frozenset()

    compare_with_base(extract, repo_root=suppression_repo, paths=("specs",))
    assert reads == [suppression_repo]


def test_changed_files_against_an_unknown_commit_is_an_unavailable_base(
    files_repo,
):
    with pytest.raises(BaseUnavailableError, match="could not list"):
        changed_files(files_repo, "0" * 40, ("d",))


def test_changed_files_keeps_a_non_utf8_name(files_repo):
    base = _git(files_repo, "rev-parse", "HEAD").strip()
    name = os.fsdecode(b"bad\xff")
    (files_repo / "d" / name).write_text("new")
    changed = changed_files(files_repo, base, ("d",))
    assert changed.at_head == (f"d/{name}",)


def test_compare_changed_skips_a_listed_path_that_is_not_a_file(files_repo):
    """An untracked nested repository is listed as a directory, ``d/sub/``."""
    nested = files_repo / "d" / "sub"
    nested.mkdir()
    _git(nested, "init", "-q")
    (nested / "inner").write_text("inner")
    (files_repo / "d" / "edited").write_text("edited again")
    seen = compare_changed_with_base(
        _file_names, repo_root=files_repo, paths=("d",)
    )
    assert seen.head_value == {"d/edited"}
