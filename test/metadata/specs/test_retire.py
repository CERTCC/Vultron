"""Tests for the retired-requirement archive (MS-09-001, -004, -005, -006, -008)."""

import subprocess
from datetime import date
from pathlib import Path

import pytest

from test.metadata.specs._helpers import write_yaml
from test.metadata.specs.test_lint import _minimal_spec
from vultron.metadata.base import repo_root
from vultron.metadata.specs.lint import lint
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.retire import (
    RetireError,
    main,
    retire_spec,
    retired_spec_ids,
)


def _two_spec_file():
    data = _minimal_spec("TST-01-001")
    data["groups"][0]["specs"].append(
        _minimal_spec("TST-01-002")["groups"][0]["specs"][0]
    )
    return data


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=path, check=True)


def _commit(path: Path, message: str) -> None:
    """Stage everything under *path* and commit it."""
    _git(path, "add", "-A")
    _git(
        path,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "commit",
        "-q",
        "-m",
        message,
    )


def _init_repo(path: Path) -> None:
    """Commit *path* and point ``origin/main`` at it: the published base."""
    (path / "pyproject.toml").write_text("")
    _git(path, "init", "-q")
    _commit(path, "base")
    _git(path, "update-ref", "refs/remotes/origin/main", "HEAD")


@pytest.fixture(autouse=True)
def _default_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """The base is ``origin/main`` whatever PR base the CI run names."""
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway repo with a ``specs/`` dir holding two requirements."""
    (tmp_path / "specs").mkdir()
    write_yaml(tmp_path / "specs", _two_spec_file())
    (tmp_path / "notes.md").write_text("See TST-01-001 and TST-01-002.\n")
    _init_repo(tmp_path)
    return tmp_path


def _retire(repo: Path, **kw):
    return retire_spec(
        "TST-01-001",
        why="superseded by a better rule",
        retired_by="#1",
        repo_root=repo,
        today=date(2026, 10, 5),
        **kw,
    )


def test_retire_moves_item_to_archive(repo: Path) -> None:
    _retire(repo, replacement="TST-01-002")

    assert "TST-01-001" not in load_registry(repo / "specs").all_specs
    entry = (repo / "plan/retired-specs/TST-01-001.md").read_text()
    assert "# TST-01-001 (retired)" in entry
    assert "2026-10-05 (#1)" in entry
    assert "**Replacement**: TST-01-002" in entry
    assert "TST-01-001 MUST do the thing" in entry
    assert retired_spec_ids(repo) == {"TST-01-001"}


def test_retire_records_history_and_lists_cross_references(
    repo: Path,
) -> None:
    refs = _retire(repo)

    history = list((repo / "plan/history").glob("*/implementation/*.md"))
    assert [p.name for p in history] == ["SPEC-RETIRE-TST-01-001.md"]
    assert "superseded by a better rule" in history[0].read_text()
    assert [(rel, n) for rel, n, _ in refs] == [("notes.md", 1)]


def test_retire_refuses_archived_id_and_changes_nothing(repo: Path) -> None:
    _retire(repo)
    before = (repo / "specs/specs.yaml").read_text()
    with pytest.raises(RetireError, match="already in the archive"):
        _retire(repo)
    assert (repo / "specs/specs.yaml").read_text() == before


def test_retire_refuses_unknown_id_and_unknown_replacement(
    repo: Path,
) -> None:
    with pytest.raises(RetireError, match="not declared"):
        retire_spec("TST-09-999", why="x", retired_by="#1", repo_root=repo)
    with pytest.raises(RetireError, match="replacement"):
        _retire(repo, replacement="TST-09-999")


def test_retire_restores_file_when_group_would_be_left_empty(
    tmp_path: Path,
) -> None:
    (tmp_path / "specs").mkdir()
    write_yaml(tmp_path / "specs", _minimal_spec("TST-01-001"))
    _init_repo(tmp_path)
    before = (tmp_path / "specs/specs.yaml").read_text()

    with pytest.raises(RetireError, match="unloadable"):
        retire_spec("TST-01-001", why="x", retired_by="#1", repo_root=tmp_path)

    assert (tmp_path / "specs/specs.yaml").read_text() == before
    assert not (tmp_path / "plan/retired-specs").exists()


def test_lint_rejects_reusing_a_retired_id(tmp_path: Path, capsys) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    write_yaml(specs, _minimal_spec("TST-01-001"))
    archive = tmp_path / "plan/retired-specs"
    archive.mkdir(parents=True)
    (archive / "TST-01-001.md").write_text("# TST-01-001 (retired)\n")
    (archive / "README.md").write_text("not an entry\n")

    assert lint(specs) == 1
    assert "MS-09-004" in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra", [{"deprecated": True}, {"superseded_by": "TST-01-002"}]
)
def test_lint_rejects_deprecated_in_place(
    tmp_path: Path, capsys, extra: dict
) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    data = _two_spec_file()
    data["groups"][0]["specs"][0].update(extra)
    write_yaml(specs, data)

    assert lint(specs) == 1
    assert "MS-09-001" in capsys.readouterr().err


def test_live_specs_do_not_reuse_or_deprecate() -> None:
    """The real corpus satisfies the retirement rules."""
    root = repo_root()
    registry = load_registry(root / "specs")
    assert not set(registry.all_specs) & retired_spec_ids(root)
    assert all(
        not {"deprecated", "superseded_by"} & s.model_fields_set
        for s in registry.all_specs.values()
    )


def test_archive_is_outside_the_spec_loader_scope() -> None:
    """Retired text sits outside ``specs/``, so no loader reads it (MS-09-005)."""
    root = repo_root()
    assert (root / "plan/retired-specs").is_dir()
    assert not (root / "specs/retired-specs").exists()
    loaded = {p.resolve() for p in (root / "specs").glob("*.yaml")}
    archive = (root / "plan/retired-specs").resolve()
    assert not any(archive in p.parents for p in loaded)


def test_retire_rolls_back_when_history_write_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure after the spec edit leaves spec and archive untouched."""
    import vultron.metadata.specs.retire as retire_mod

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(retire_mod, "append_history_entry", boom)
    before = (repo / "specs/specs.yaml").read_text()

    with pytest.raises(OSError):
        _retire(repo)

    assert (repo / "specs/specs.yaml").read_text() == before
    assert not (repo / "plan/retired-specs").exists()


def test_retire_finds_id_line_with_trailing_comment(repo: Path) -> None:
    spec_file = repo / "specs/specs.yaml"
    text = spec_file.read_text().replace(
        "id: TST-01-001", "id: TST-01-001  # note", 1
    )
    spec_file.write_text(text)

    _retire(repo)

    assert retired_spec_ids(repo) == {"TST-01-001"}


def _edit_statement(repo: Path, new: str) -> None:
    """Change TST-01-001's statement in the working tree to *new*."""
    spec_file = repo / "specs/specs.yaml"
    spec_file.write_text(
        spec_file.read_text().replace(
            "TST-01-001 MUST do the thing", f"TST-01-001 MUST {new}", 1
        )
    )


def _assert_nothing_changed(repo: Path, spec_text_before: str) -> None:
    """The spec file, the archive and the history are as they were."""
    assert (repo / "specs/specs.yaml").read_text() == spec_text_before
    assert not (repo / "plan/retired-specs").exists()
    assert not (repo / "plan/history").exists()


def _publish_branch(repo: Path, branch: str) -> None:
    """Point ``origin/<branch>`` at ``HEAD``."""
    _git(repo, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")


@pytest.mark.spec("MS-09-008")
def test_retire_archives_base_text_when_block_edited_on_branch(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The archive keeps the published text, not a branch edit (#5400)."""
    _edit_statement(repo, "do an edit")

    _retire(repo)

    entry = (repo / "plan/retired-specs/TST-01-001.md").read_text()
    assert "TST-01-001 MUST do the thing" in entry
    assert "MUST do an edit" not in entry
    assert "TST-01-001" not in load_registry(repo / "specs").all_specs
    assert "edit is dropped" in caplog.text


@pytest.mark.spec("MS-09-008")
def test_retire_finds_base_text_in_another_spec_file(repo: Path) -> None:
    """The base lookup scans every spec file, not the working-tree one."""
    _git(repo, "mv", "specs/specs.yaml", "specs/moved.yaml")
    moved = repo / "specs/moved.yaml"
    moved.write_text(
        moved.read_text().replace(
            "TST-01-001 MUST do the thing", "TST-01-001 MUST do a move", 1
        )
    )

    _retire(repo)

    entry = (repo / "plan/retired-specs/TST-01-001.md").read_text()
    assert "TST-01-001 MUST do the thing" in entry
    assert "do a move" not in entry


@pytest.mark.spec("MS-09-008")
def test_retire_refuses_id_absent_on_base_and_changes_nothing(
    repo: Path,
) -> None:
    """An ID added on the branch was never published, so it is refused."""
    data = _two_spec_file()
    data["groups"][0]["specs"].append(
        _minimal_spec("TST-01-003")["groups"][0]["specs"][0]
    )
    write_yaml(repo / "specs", data)
    before = (repo / "specs/specs.yaml").read_text()

    with pytest.raises(RetireError, match="not declared at the merge base"):
        retire_spec("TST-01-003", why="x", retired_by="#1", repo_root=repo)

    _assert_nothing_changed(repo, before)


@pytest.mark.spec("MS-09-008")
def test_retire_refuses_unresolvable_base_and_changes_nothing(
    repo: Path,
) -> None:
    before = (repo / "specs/specs.yaml").read_text()

    with pytest.raises(RetireError, match="no-such-ref"):
        _retire(repo, base_ref="no-such-ref")

    _assert_nothing_changed(repo, before)


@pytest.mark.spec("MS-09-008")
def test_retire_refuses_unreadable_base_tree_and_changes_nothing(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure reading the base tree is a refusal, not a traceback."""
    import vultron.metadata.specs.retire as retire_mod

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("no space left on device")

    monkeypatch.setattr(retire_mod, "materialize_tree", boom)
    before = (repo / "specs/specs.yaml").read_text()

    with pytest.raises(RetireError, match="no space left"):
        _retire(repo)

    _assert_nothing_changed(repo, before)


@pytest.mark.spec("MS-09-008")
def test_retire_uses_explicit_base(repo: Path) -> None:
    """``--base`` names the published tree when it is not ``origin/main``."""
    _edit_statement(repo, "do v2")
    _commit(repo, "v2")
    _publish_branch(repo, "release")

    _retire(repo, base_ref="origin/release")

    entry = (repo / "plan/retired-specs/TST-01-001.md").read_text()
    assert "TST-01-001 MUST do v2" in entry


@pytest.mark.spec("MS-09-008")
def test_retire_defaults_base_to_github_base_ref(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no ``--base``, a PR run reads ``origin/$GITHUB_BASE_REF``."""
    _edit_statement(repo, "do v2")
    _commit(repo, "v2")
    _publish_branch(repo, "release")
    monkeypatch.setenv("GITHUB_BASE_REF", "release")

    _retire(repo)

    entry = (repo / "plan/retired-specs/TST-01-001.md").read_text()
    assert "TST-01-001 MUST do v2" in entry


@pytest.mark.spec("MS-09-008")
def test_cli_passes_base_and_reports_refusal(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(repo)
    argv = ["TST-01-001", "--why", "x", "--by", "#1", "--base", "no-such-ref"]
    before = (repo / "specs/specs.yaml").read_text()

    with pytest.raises(SystemExit) as exc:
        main(argv)

    assert exc.value.code == 1
    assert "no-such-ref" in capsys.readouterr().err
    _assert_nothing_changed(repo, before)


def test_retire_accepts_sub_item_id_and_keeps_its_parent_citations_apart(
    tmp_path: Path,
) -> None:
    """A sub-item ID such as ``TST-01-001b`` is retirable (MS-04-001).

    Its parent's citations are not its own, and the parent's are not listed
    for it.
    """
    data = _two_spec_file()
    data["groups"][0]["specs"][1]["id"] = "TST-01-001b"
    (tmp_path / "specs").mkdir()
    write_yaml(tmp_path / "specs", data)
    (tmp_path / "notes.md").write_text("See TST-01-001.\nSee TST-01-001b.\n")
    _init_repo(tmp_path)

    refs = retire_spec(
        "TST-01-001b",
        why="restated its parent",
        retired_by="#1",
        repo_root=tmp_path,
        today=date(2026, 10, 5),
    )

    assert "TST-01-001b" not in load_registry(tmp_path / "specs").all_specs
    assert retired_spec_ids(tmp_path) == {"TST-01-001b"}
    assert [(rel, n) for rel, n, _ in refs] == [("notes.md", 2)]


def test_retire_does_not_list_a_sub_item_citation_for_its_parent(
    repo: Path,
) -> None:
    (repo / "notes.md").write_text("See TST-01-001b.\n")

    assert _retire(repo) == []
