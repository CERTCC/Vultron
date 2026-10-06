"""Tests for the retired-requirement archive (MS-09-001, -004, -005)."""

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
    retire_spec,
    retired_spec_ids,
)


def _two_spec_file():
    data = _minimal_spec("TST-01-001")
    data["groups"][0]["specs"].append(
        _minimal_spec("TST-01-002")["groups"][0]["specs"][0]
    )
    return data


def _init_repo(path: Path) -> None:
    (path / "pyproject.toml").write_text("")
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)


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
