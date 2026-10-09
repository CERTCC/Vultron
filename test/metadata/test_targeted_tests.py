"""Tests for the ``targeted-tests`` local test gate.

Requirements: specs/parallel-development.yaml PAD-18-002, PAD-18-003,
PAD-18-004.
"""

import json
import shlex
import sys
from pathlib import Path

import pytest

from test.support.git_repo import git, init_git_repo
from vultron.metadata.planning import targeted_tests
from vultron.metadata.planning.targeted_tests import (
    ARCHITECTURE_TESTS,
    INTEGRATION_PREFIXES,
    full_suite_trigger,
    overlap,
    pytest_argv,
    select_tests,
)
from vultron.metadata.specs.backstop import (
    HUB_THRESHOLD,
    FileChange,
    index_test_file,
)

SOURCE = """\
def changed_fn():
    return 1


def other_fn():
    return 2
"""


def _index(files: dict[str, str]):
    index = {}
    for path, source in files.items():
        indexed = index_test_file(path, source)
        assert indexed is not None
        index[path] = indexed
    return index


TESTS = _index(
    {
        "test/x/test_uses_changed.py": (
            "from vultron.a.mod import changed_fn\n"
        ),
        "test/x/test_uses_other.py": "from vultron.a.mod import other_fn\n",
        "test/x/test_reexport.py": "from vultron.a import changed_fn\n",
        "test/x/test_module_object.py": "from vultron.a import mod\n",
        "test/x/test_plain_import.py": "import vultron.a.mod\n",
        "test/x/test_plain_and_from.py": (
            "import vultron.a.mod\nfrom vultron.a.mod import other_fn\n"
        ),
        "test/x/test_unrelated.py": "from vultron.b import thing\n",
        "test/a/test_mod.py": "from vultron.a.mod import changed_fn\n",
        "test/architecture/test_layers.py": "import ast\n",
    }
)


def _change(
    lines: frozenset[int] | None = frozenset({1, 2}),
    path: str = "vultron/a/mod.py",
    source: str = SOURCE,
) -> FileChange:
    """A changed file; ``lines=None`` means the whole file changed."""
    return FileChange(path, source, lines)


def _select(paths, changes, tests=TESTS, exists=lambda p: True):
    return select_tests(paths, changes, tests, exists)


# ---------------------------------------------------------------------------
# Targeted set (PAD-18-002)
# ---------------------------------------------------------------------------


@pytest.mark.spec("PAD-18-002")
def test_selects_importers_mirror_and_architecture():
    selection = _select(["vultron/a/mod.py"], [_change()])
    assert not selection.full
    assert selection.tests == [
        ARCHITECTURE_TESTS,
        "test/a/test_mod.py",
        "test/x/test_module_object.py",
        "test/x/test_plain_and_from.py",
        "test/x/test_plain_import.py",
        "test/x/test_reexport.py",
        "test/x/test_uses_changed.py",
    ]
    assert selection.unmapped == []


@pytest.mark.spec("PAD-18-002")
def test_importer_of_an_unchanged_symbol_is_not_selected():
    selection = _select(["vultron/a/mod.py"], [_change()])
    assert "test/x/test_uses_other.py" not in selection.tests
    assert "test/x/test_unrelated.py" not in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_mirror_test_selected_even_when_it_imports_nothing_changed():
    tests = _index({"test/a/test_mod.py": "import ast\n"})
    selection = _select(["vultron/a/mod.py"], [_change()], tests)
    assert selection.tests == [ARCHITECTURE_TESTS, "test/a/test_mod.py"]


@pytest.mark.spec("PAD-18-002")
def test_set_has_no_duplicates():
    """The mirror test also imports the changed symbol; listed once."""
    test_change = _change(
        path="test/a/test_mod.py", source="", lines=frozenset({1})
    )
    arch_change = _change(
        path="test/architecture/test_layers.py", source="", lines=None
    )
    selection = _select(
        ["vultron/a/mod.py", test_change.path, arch_change.path],
        [_change(), test_change, arch_change],
    )
    assert len(selection.tests) == len(set(selection.tests))
    assert selection.tests.count("test/a/test_mod.py") == 1
    assert "test/architecture/test_layers.py" not in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_changed_test_file_alone_is_selected():
    change = _change(
        path="test/x/test_unrelated.py", source="", lines=frozenset({1})
    )
    selection = _select([change.path], [change])
    assert selection.tests == [ARCHITECTURE_TESTS, "test/x/test_unrelated.py"]
    assert selection.unmapped == []


@pytest.mark.spec("PAD-18-002")
def test_deleted_test_file_is_not_selected():
    change = _change(path="test/x/test_gone.py", source="", lines=None)
    selection = _select([change.path], [change], exists=lambda p: False)
    assert selection.tests == [ARCHITECTURE_TESTS]
    assert selection.unmapped == []


@pytest.mark.spec("PAD-18-002")
def test_non_python_only_diff_selects_just_architecture():
    selection = _select(
        ["docs/index.md", "specs/x.yaml", "test/AGENTS.md"], []
    )
    assert not selection.full
    assert selection.tests == [ARCHITECTURE_TESTS]
    assert selection.unmapped == ["docs/index.md", "specs/x.yaml"]


@pytest.mark.spec("PAD-18-002")
def test_deleted_module_selects_its_importers_and_mirror():
    """A deleted module carries its old source and changes every symbol."""
    gone = _change(lines=None)
    selection = _select([gone.path], [gone])
    assert "test/x/test_uses_changed.py" in selection.tests
    assert "test/x/test_uses_other.py" in selection.tests
    assert "test/a/test_mod.py" in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_unparseable_module_selects_every_importer():
    broken = _change(source="def broken(:\n", lines=frozenset({1}))
    selection = _select([broken.path], [broken])
    assert "test/x/test_uses_other.py" in selection.tests
    assert "test/x/test_unrelated.py" not in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_unparseable_module_reaches_reexport_importers():
    broken = _change(source="def broken(:\n", lines=frozenset({1}))
    assert "test/x/test_reexport.py" in _select([broken.path], [broken]).tests


MODULE_WITH_IMPORTS = '''\
"""Module docstring."""

import os


def changed_fn():
    return os.sep


def other_fn():
    return 2
'''


@pytest.mark.spec("PAD-18-002")
def test_import_line_change_selects_every_importer():
    """A broken import fails every importer, not just one name's."""
    change = _change(source=MODULE_WITH_IMPORTS, lines=frozenset({3}))
    selection = _select([change.path], [change])
    assert "test/x/test_uses_other.py" in selection.tests
    assert "test/x/test_uses_changed.py" in selection.tests
    assert "test/x/test_unrelated.py" not in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_docstring_change_is_not_a_module_level_change():
    change = _change(source=MODULE_WITH_IMPORTS, lines=frozenset({1}))
    assert (
        "test/x/test_uses_other.py"
        not in _select([change.path], [change]).tests
    )


@pytest.mark.spec("PAD-18-002")
def test_reexport_change_in_package_init_selects_its_importers():
    tests = _index({"test/x/test_bar.py": "from vultron.a import bar\n"})
    change = _change(
        path="vultron/a/__init__.py",
        source="from vultron.a.mod import changed_fn as bar\n",
        lines=frozenset({1}),
    )
    selection = _select([change.path], [change], tests)
    assert "test/x/test_bar.py" in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_plain_import_beside_a_from_import_still_selects():
    """``import vultron.a.mod`` reaches every symbol by attribute access."""
    selection = _select(["vultron/a/mod.py"], [_change()])
    assert "test/x/test_plain_and_from.py" in selection.tests


@pytest.mark.spec("PAD-18-002")
def test_hub_threshold_does_not_demote_importers():
    """Selection needs every importer; spec-backstop's hub cut is precision."""
    count = HUB_THRESHOLD + 5
    tests = _index(
        {
            f"test/h/test_{i}.py": "from vultron.a.mod import changed_fn\n"
            for i in range(count)
        }
    )
    selection = _select(["vultron/a/mod.py"], [_change()], tests)
    assert len(selection.tests) == count + 1


@pytest.mark.spec("PAD-18-002")
def test_module_nothing_tests_is_unmapped():
    change = _change(path="vultron/z.py", lines=None)
    selection = _select([change.path], [change], tests={})
    assert selection.tests == [ARCHITECTURE_TESTS]
    assert selection.unmapped == ["vultron/z.py"]


@pytest.mark.spec("PAD-18-002")
def test_pytest_argv_enables_the_integration_marker():
    selection = _select(["vultron/a/mod.py"], [_change()])
    argv = pytest_argv(selection)
    assert argv[:3] == ["uv", "run", "pytest"]
    marker = argv.index("-m")
    assert argv[marker + 1] == ""
    assert argv[-len(selection.tests) :] == selection.tests


# ---------------------------------------------------------------------------
# Escalation (PAD-18-003)
# ---------------------------------------------------------------------------

FULL_PATHS = [
    "conftest.py",
    "test/conftest.py",
    "test/core/behaviors/conftest.py",
    "test/architecture/conftest.py",
    "pyproject.toml",
    "uv.lock",
    "test/support/clock.py",
    "test/metadata/specs/_helpers.py",
    "test/core/behaviors/case/nodes/revision_relay_fixtures.py",
    "test/adapters/driven/golden/wire_render_core_vocab.json",
    "vultron/demo/cli.py",
    "integration_tests/demo/run.sh",
    "vultron/adapters/driving/fastapi/main.py",
    "vultron/core/behaviors/bridge.py",
    "vultron/core/use_cases/received/case.py",
    "vultron/wire/as2/extractor/__init__.py",
]


@pytest.mark.spec("PAD-18-003")
@pytest.mark.parametrize("path", FULL_PATHS)
def test_shared_infrastructure_and_integration_paths_escalate(path):
    selection = _select(["vultron/a/mod.py", path], [_change()])
    assert selection.full
    assert selection.tests == []
    assert [t.path for t in selection.triggers] == [path]


@pytest.mark.spec("PAD-18-003")
def test_full_paths_cover_every_integration_prefix():
    """Each PAD-18-003 prefix is exercised by a real path above."""
    for prefix in INTEGRATION_PREFIXES:
        assert any(p.startswith(prefix) for p in FULL_PATHS), prefix


@pytest.mark.spec("PAD-18-003")
@pytest.mark.parametrize(
    "path",
    [
        "vultron/core/models/case.py",
        "vultron/wire/as2/extractor.py",
        "test/core/test_x.py",
        "test/architecture/_corpus.py",
        "test/AGENTS.md",
        "docs/index.md",
        "specs/parallel-development.yaml",
    ],
)
def test_ordinary_paths_do_not_escalate(path):
    assert full_suite_trigger(path) is None


@pytest.mark.spec("PAD-18-003")
def test_full_pytest_argv_has_no_paths():
    selection = _select(["uv.lock"], [])
    argv = pytest_argv(selection)
    assert argv[-2:] == ["-m", ""]


# ---------------------------------------------------------------------------
# Overlap (PAD-18-004)
# ---------------------------------------------------------------------------


@pytest.mark.spec("PAD-18-004")
def test_overlap_is_the_intersection():
    assert overlap(["a", "b", "c"], ["c", "d", "a"]) == ["a", "c"]
    assert overlap(["a"], ["b"]) == []


# ---------------------------------------------------------------------------
# CLI against a real git repository
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "vultron" / "a").mkdir(parents=True)
    (tmp_path / "vultron" / "a" / "mod.py").write_text(SOURCE)
    (tmp_path / "test" / "a").mkdir(parents=True)
    (tmp_path / "test" / "architecture").mkdir()
    (tmp_path / "test" / "a" / "test_mod.py").write_text(
        "from vultron.a.mod import changed_fn\n"
    )
    (tmp_path / "test" / "a" / "test_other.py").write_text(
        "from vultron.a.mod import other_fn\n"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "index.md").write_text("# x\n")
    init_git_repo(tmp_path, monkeypatch)
    git(tmp_path, "checkout", "-q", "-b", "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _main(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["targeted-tests", *argv])
    return targeted_tests.main()


def _edit(path: Path, old: str, new: str) -> None:
    path.write_text(path.read_text().replace(old, new))


@pytest.mark.spec("PAD-18-002")
def test_cli_lists_targeted_set(git_repo, monkeypatch, capsys):
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 1", "return 3")
    assert _main(monkeypatch, "--base", "main") == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [ARCHITECTURE_TESTS, "test/a/test_mod.py"]


@pytest.mark.spec("PAD-18-002")
def test_cli_non_python_diff_names_unmapped(git_repo, monkeypatch, capsys):
    (git_repo / "docs" / "index.md").write_text("# y\n")
    assert _main(monkeypatch, "--base", "main") == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [ARCHITECTURE_TESTS]
    assert "no test maps to: docs/index.md" in captured.err


@pytest.mark.spec("PAD-18-002")
def test_cli_deleted_module(git_repo, monkeypatch, capsys):
    git(git_repo, "rm", "-q", "vultron/a/mod.py")
    git(git_repo, "commit", "-q", "-m", "delete")
    assert _main(monkeypatch, "--base", "main") == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        ARCHITECTURE_TESTS,
        "test/a/test_mod.py",
        "test/a/test_other.py",
    ]


@pytest.mark.spec("PAD-18-002")
def test_cli_changed_test_file_only(git_repo, monkeypatch, capsys):
    _edit(git_repo / "test" / "a" / "test_other.py", "other_fn", "other_fn\n")
    assert _main(monkeypatch, "--base", "main") == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [ARCHITECTURE_TESTS, "test/a/test_other.py"]


@pytest.mark.spec("PAD-18-002")
def test_cli_pytest_line_is_runnable(git_repo, monkeypatch, capsys):
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 1", "return 3")
    assert _main(monkeypatch, "--base", "main", "--pytest") == 0
    argv = shlex.split(capsys.readouterr().out)
    assert argv[argv.index("-m") + 1] == ""
    assert argv[-2:] == [ARCHITECTURE_TESTS, "test/a/test_mod.py"]


@pytest.mark.spec("PAD-18-003")
def test_cli_reports_full_with_trigger(git_repo, monkeypatch, capsys):
    (git_repo / "test" / "conftest.py").write_text("import pytest\n")
    assert _main(monkeypatch, "--base", "main") == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "full"
    assert out[1].startswith("test/conftest.py: ")


@pytest.mark.spec("PAD-18-003")
def test_cli_escalation_is_keyed_on_the_branch_diff(
    git_repo, monkeypatch, capsys
):
    """A fix commit on top of a conftest.py change still escalates."""
    (git_repo / "test" / "conftest.py").write_text("import pytest\n")
    git(git_repo, "add", ".")
    git(git_repo, "commit", "-q", "-m", "conftest")
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 1", "return 3")
    git(git_repo, "commit", "-q", "-am", "fix")
    assert _main(monkeypatch, "--base", "main", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mode"] == "full"
    assert data["triggers"][0]["path"] == "test/conftest.py"
    assert data["tests"] == []
    assert data["pytest"][-2:] == ["-m", ""]


@pytest.mark.spec("PAD-18-003")
def test_cli_pytest_full_names_trigger_on_stderr(
    git_repo, monkeypatch, capsys
):
    _edit(git_repo / "pyproject.toml", "name='x'", "name='y'")
    assert _main(monkeypatch, "--base", "main", "--pytest") == 0
    captured = capsys.readouterr()
    assert shlex.split(captured.out)[-2:] == ["-m", ""]
    assert "pyproject.toml" in captured.err


@pytest.mark.spec("PAD-18-004")
def test_cli_overlap_exits_1_on_shared_file(git_repo, monkeypatch, capsys):
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 1", "return 3")
    git(git_repo, "commit", "-q", "-am", "branch edit")
    git(git_repo, "checkout", "-q", "main")
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 2", "return 4")
    (git_repo / "docs" / "index.md").write_text("# main\n")
    git(git_repo, "commit", "-q", "-am", "main edit")
    git(git_repo, "checkout", "-q", "feature")
    assert _main(monkeypatch, "--base", "main", "--overlap") == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["vultron/a/mod.py"]
    assert "1 file(s) changed on both main" in captured.err


@pytest.mark.spec("PAD-18-004")
def test_cli_overlap_exits_0_when_disjoint(git_repo, monkeypatch, capsys):
    _edit(git_repo / "vultron" / "a" / "mod.py", "return 1", "return 3")
    git(git_repo, "commit", "-q", "-am", "branch edit")
    git(git_repo, "checkout", "-q", "main")
    (git_repo / "docs" / "index.md").write_text("# main\n")
    git(git_repo, "commit", "-q", "-am", "main edit")
    git(git_repo, "checkout", "-q", "feature")
    assert _main(monkeypatch, "--base", "main", "--overlap", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["overlap"] == []
    assert data["base"] == "main"


@pytest.mark.spec("PAD-18-002")
def test_cli_bad_base_exits_2(git_repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--base", "no-such-ref") == 2
    assert "no-such-ref" in capsys.readouterr().err


@pytest.mark.spec("PAD-18-004")
def test_cli_pytest_with_overlap_is_a_usage_error(git_repo, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--overlap", "--pytest")
    assert exc.value.code == 2
