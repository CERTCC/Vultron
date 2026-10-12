"""Tests for vultron.metadata.specs.growth_guard (SR-05-005, MS-12-007).

Each test builds a throwaway git repository whose ``origin/main`` ref is the
base, edits the working tree, and runs a real guard extractor through
:func:`added_since_base`: the protocol-coverage guard
(:func:`uncovered_protocol_ids`) and the ``missing_story_reference`` guard
(:func:`missing_story_suppression_carriers`).
"""

import logging
import subprocess
from pathlib import Path

import pytest
import yaml

from vultron.metadata.specs.coverage import uncovered_protocol_ids
from vultron.metadata.specs.growth_guard import (
    BASE_REF_ENV,
    CI_ENV,
    DEFAULT_BASE_REF,
    BaseExtractionError,
    BaseUnavailableError,
    added_since_base,
    base_ref_name,
    running_in_ci,
)
from vultron.metadata.specs.kind_classification import (
    missing_story_suppression_carriers,
)

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
        uncovered_protocol_ids, repo_root=repo, paths=("specs", "test")
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


# --- protocol-coverage guard (SR-05-005) -----------------------------------


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
    assert uncovered_protocol_ids(
        coverage_repo, test_sources=sources
    ) == uncovered_protocol_ids(coverage_repo)


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
