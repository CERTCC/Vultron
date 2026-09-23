"""Tests for the ``spec-backstop`` spec-selection check.

Requirements: specs/spec-registry.yaml SR-12-001 through SR-12-008.
"""

import ast
import io
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from vultron.metadata.specs.backstop import (
    FileChange,
    GroupHit,
    Requirement,
    analyze,
    changed_nodes,
    changed_symbols,
    index_test_file,
    mentions,
    mirror_tests,
    parse_diff_hunks,
    parse_manifest,
    render_text,
    unresolved_groups,
)
from vultron.metadata.specs import backstop

# ---------------------------------------------------------------------------
# Diff parsing (SR-12-001)
# ---------------------------------------------------------------------------

DIFF = textwrap.dedent("""\
    diff --git a/vultron/a/mod.py b/vultron/a/mod.py
    index 1..2 100644
    --- a/vultron/a/mod.py
    +++ b/vultron/a/mod.py
    @@ -3,0 +4,2 @@ def f():
    +    x = 1
    +    y = 2
    @@ -10 +12 @@ class C:
    -    old
    +    new
    @@ -20,3 +22,0 @@ class C:
    -    gone
    diff --git a/vultron/a/old.py b/vultron/a/old.py
    deleted file mode 100644
    --- a/vultron/a/old.py
    +++ /dev/null
    @@ -1,2 +0,0 @@
    -def g():
    -    pass
    diff --git a/docs/x.md b/docs/x.md
    --- a/docs/x.md
    +++ b/docs/x.md
    @@ -1 +1 @@
    -a
    +b
    """)


@pytest.mark.spec("SR-12-001")
def test_parse_diff_hunks_collects_new_side_lines():
    changed, deleted = parse_diff_hunks(DIFF)
    assert changed == {"vultron/a/mod.py": {4, 5, 12, 22}}
    assert deleted == {"vultron/a/old.py"}


# ---------------------------------------------------------------------------
# Changed symbols (SR-12-002)
# ---------------------------------------------------------------------------

SOURCE = textwrap.dedent("""\
    import os

    CONSTANT = 1


    @decorator
    def top_function():
        return 1


    class SomeClass:
        def method(self):
            return 2
    """)


@pytest.mark.spec("SR-12-002")
@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        ({13}, {"SomeClass"}),
        ({6}, {"top_function"}),
        ({1}, set()),
        ({3, 8}, {"CONSTANT", "top_function"}),
        (None, {"CONSTANT", "top_function", "SomeClass"}),
    ],
)
def test_changed_symbols(lines, expected):
    assert changed_symbols(ast.parse(SOURCE), lines) == expected


@pytest.mark.spec("SR-12-002")
def test_changed_symbols_skip_dunders():
    tree = ast.parse("__all__ = ['x']\n")
    assert changed_symbols(tree, None) == set()


# ---------------------------------------------------------------------------
# Test index and mirror paths (SR-12-003)
# ---------------------------------------------------------------------------

TEST_SOURCE = textwrap.dedent("""\
    import pytest
    import vultron.a.mod as m
    from vultron.a import mod
    from vultron.b.other import Thing, helper
    from os import path

    pytestmark = [pytest.mark.spec("AA-01-001")]


    @pytest.mark.spec("AA-02-001", "AA-02-002")
    def test_x():
        from vultron.c import late


    class TestY:
        pytestmark = pytest.mark.spec("AA-03-001")

        @pytest.mark.parametrize("x", [1])
        @pytest.mark.spec("AA-04-001")
        def test_z(self, x):
            try:
                from vultron.d import deep
            except ImportError:
                pass
    """)


@pytest.mark.spec("SR-12-003")
def test_index_test_file_collects_imports_and_markers():
    info = index_test_file("test/test_x.py", TEST_SOURCE)
    assert info is not None
    assert {"vultron.a.mod", "vultron.b.other", "vultron.c"} <= info.modules
    assert ("vultron.b.other", "Thing") in info.names
    assert ("vultron.c", "late") in info.names
    assert not any(module == "os" for module, _ in info.names)
    assert ("vultron.d", "deep") in info.names
    assert info.spec_ids == {
        "AA-01-001",
        "AA-02-001",
        "AA-02-002",
        "AA-03-001",
        "AA-04-001",
    }


def test_index_test_file_ignores_syntax_errors():
    assert index_test_file("test/test_bad.py", "def (:\n") is None


@pytest.mark.spec("SR-12-003")
def test_mirror_tests():
    tests = [
        "test/a/test_mod.py",
        "test/a/mod/test_one.py",
        "test/a/mod/deeper/test_two.py",
        "test/a/test_other.py",
    ]
    assert mirror_tests("vultron/a/mod.py", tests) == [
        "test/a/mod/test_one.py",
        "test/a/test_mod.py",
    ]
    assert mirror_tests("vultron/a/mod/__init__.py", tests) == [
        "test/a/mod/test_one.py",
        "test/a/test_mod.py",
    ]


# ---------------------------------------------------------------------------
# Statement mentions (SR-12-003)
# ---------------------------------------------------------------------------


def _req(statement, rid="AA-01-001"):
    return Requirement(rid, rid[:5], rid[:2], statement)


@pytest.mark.spec("SR-12-003")
@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("See `vultron/a/mod.py` for details.", {"vultron/a/mod.py"}),
        ("The vultron/a/mod module MUST hold.", {"vultron/a/mod"}),
        ("Use `vultron.a.mod`.", {"vultron.a.mod"}),
        ("Use `vultron.a.mod.SomeClass`.", {"vultron.a.mod", "SomeClass"}),
        ("Everything under `vultron/a/` MUST hold.", set()),
        ("`vultron/a/mod/sub.py` MUST hold.", set()),
        ("`vultron.a.mod.submodule` MUST hold.", set()),
        ("The run step MUST use top_function.", {"top_function"}),
        ("The `run` step MUST hold.", set()),
        ("Not a SomeClassy word.", set()),
        ("The registry MUST hold.", set()),
        ("The `registry` MUST hold.", {"registry"}),
        ("A Manifest MUST hold.", set()),
        ("A `Manifest` MUST hold.", {"Manifest"}),
    ],
)
def test_mentions(statement, expected):
    symbols = {"SomeClass", "top_function", "run", "registry", "Manifest"}
    assert mentions(_req(statement), "vultron/a/mod.py", symbols) == expected


# ---------------------------------------------------------------------------
# Analysis (SR-12-003, SR-12-004, SR-12-005, SR-12-007)
# ---------------------------------------------------------------------------

REQS = [
    _req("AA-01-001 MUST hold.", "AA-01-001"),
    _req("AA-02-001 MUST hold.", "AA-02-001"),
    _req("BB-01-001 MUST keep `vultron/a/mod.py` small.", "BB-01-001"),
    _req("CC-01-001 MUST hold.", "CC-01-001"),
    _req("DD-01-001 MUST hold.", "DD-01-001"),
]


def _tests():
    sources = {
        "test/x/test_symbol.py": (
            "import pytest\nfrom vultron.a.mod import SomeClass\n"
            '@pytest.mark.spec("AA-01-001")\ndef test_a(): pass\n'
        ),
        "test/x/test_module_only.py": (
            "import pytest\nfrom vultron.a.mod import OtherThing\n"
            '@pytest.mark.spec("CC-01-001", "AA-01-001")\ndef test_b(): pass\n'
        ),
        "test/a/test_mod.py": (
            'import pytest\n@pytest.mark.spec("AA-02-001")\n'
            "def test_c(): pass\n"
        ),
    }
    index = {p: index_test_file(p, s) for p, s in sources.items()}
    return {p: info for p, info in index.items() if info is not None}


def _change(lines=None):
    return FileChange("vultron/a/mod.py", SOURCE, lines)


@pytest.mark.spec("SR-12-003")
@pytest.mark.spec("SR-12-004")
def test_analyze_tiers():
    report = analyze([_change({13})], _tests(), REQS)
    assert set(report.must) == {"AA-01", "AA-02", "BB-01"}
    assert set(report.info) == {"CC-01"}
    assert report.must["AA-01"].reqs == {"AA-01-001"}
    assert any("SomeClass" in e for e in report.must["AA-01"].evidence)
    assert any("mirror" in e for e in report.must["AA-02"].evidence)
    assert report.no_signal == []


@pytest.mark.spec("SR-12-009")
def test_hub_symbol_import_hits_demoted_to_info():
    report = analyze([_change({13})], _tests(), REQS, hub_threshold=0)
    assert report.hubs == {"SomeClass": 1}
    assert set(report.must) == {"AA-02", "BB-01"}  # mirror and mention stay
    assert set(report.info) == {"AA-01", "CC-01"}
    assert any("hub SomeClass" in e for e in report.info["AA-01"].evidence)


@pytest.mark.spec("SR-12-009")
def test_hub_threshold_not_exceeded_keeps_must():
    report = analyze([_change({13})], _tests(), REQS, hub_threshold=1)
    assert report.hubs == {}
    assert "AA-01" in report.must


@pytest.mark.spec("SR-12-009")
def test_render_text_names_hubs():
    report = analyze([_change({13})], _tests(), REQS, hub_threshold=0)
    assert (
        "hub symbols (imported by >0 test files; hits shown as "
        "INFO): SomeClass (1)"
    ) in render_text(report)
    plain = analyze([_change({13})], _tests(), REQS)
    assert "hub symbols" not in render_text(plain)


@pytest.mark.spec("SR-12-003")
def test_analyze_changed_test_markers_only_in_changed_nodes():
    source = (
        "import pytest\n"
        '@pytest.mark.spec("DD-01-001")\ndef test_a(): pass\n'
        '@pytest.mark.spec("CC-01-001")\ndef test_b(): pass\n'
    )
    change = FileChange("test/x/test_new.py", source, {3})
    report = analyze([change], {}, REQS)
    assert set(report.must) == {"DD-01"}


@pytest.mark.spec("SR-12-007")
def test_analyze_reports_files_without_signal():
    change = FileChange("vultron/z/lonely.py", "def lonely_fn(): pass\n")
    report = analyze([change, _change()], _tests(), REQS)
    assert report.no_signal == ["vultron/z/lonely.py"]


def test_changed_nodes_whole_file():
    assert len(changed_nodes(ast.parse(SOURCE), None)) == 3


@pytest.mark.spec("SR-12-005")
def test_render_text_sections():
    report = analyze([_change({13})], _tests(), REQS)
    text = render_text(report)
    assert "MUST (3 groups)" in text
    assert "AA-01" in text and "AA-01-001" in text
    assert "INFO (1 groups): CC-01(1)" in text


# ---------------------------------------------------------------------------
# Manifest (SR-12-006)
# ---------------------------------------------------------------------------

MANIFEST = textwrap.dedent("""\
    Spec manifest
    Loaded (floor): AA-01-001
    Loaded (cross-cutting): ARCH CS
    Loaded (selected): BB — covers the path; ZZ-09 (reason names CC-01)
    Considered, skipped:
    - DD-01 — not relevant; EE-01 — no, see AA-02
    Some trailing prose mentions CC-01.
    """)


@pytest.mark.spec("SR-12-006")
def test_parse_manifest():
    manifest = parse_manifest(MANIFEST, {"ARCH", "CS", "BB", "AA"})
    assert manifest.loaded == {"AA-01-001", "ARCH", "CS", "BB", "ZZ-09"}
    assert manifest.dismissed == {"DD-01", "EE-01"}


def _hit(group, *reqs):
    return GroupHit(group, group[:2], set(reqs), set())


@pytest.mark.spec("SR-12-006")
def test_unresolved_groups():
    manifest = parse_manifest(MANIFEST, {"ARCH", "CS", "BB", "AA"})
    must = {
        "AA-01": _hit("AA-01", "AA-01-001"),
        "AA-02": _hit("AA-02", "AA-02-001"),
        "BB-01": _hit("BB-01", "BB-01-001"),
        "CC-01": _hit("CC-01", "CC-01-001"),
        "DD-01": _hit("DD-01", "DD-01-001"),
        "ZZ-09": _hit("ZZ-09", "ZZ-09-001"),
    }
    assert [h.group for h in unresolved_groups(must, manifest)] == [
        "AA-02",
        "CC-01",
    ]


# ---------------------------------------------------------------------------
# CLI (SR-12-001, SR-12-005, SR-12-006, SR-12-007, SR-12-008)
# ---------------------------------------------------------------------------

SPEC_YAML = {
    "id": "AA",
    "title": "Fixture",
    "description": "Backstop fixture",
    "version": "1.0",
    "scope": ["prototype"],
    "groups": [
        {
            "id": "AA-01",
            "title": "One",
            "specs": [
                {
                    "id": "AA-01-001",
                    "priority": "MUST",
                    "kind": "project",
                    "statement": "`vultron/a/mod.py` MUST hold.",
                }
            ],
        },
        {
            "id": "AA-02",
            "title": "Two",
            "specs": [
                {
                    "id": "AA-02-001",
                    "priority": "MUST",
                    "kind": "project",
                    "statement": "Something MUST hold.",
                }
            ],
        },
    ],
}


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "aa.yaml").write_text(yaml.safe_dump(SPEC_YAML))
    (tmp_path / "vultron" / "a").mkdir(parents=True)
    (tmp_path / "vultron" / "a" / "mod.py").write_text(SOURCE)
    (tmp_path / "vultron" / "z.py").write_text("def lonely_fn(): pass\n")
    (tmp_path / "test" / "a").mkdir(parents=True)
    (tmp_path / "test" / "a" / "test_mod.py").write_text(
        'import pytest\n@pytest.mark.spec("AA-02-001")\ndef test_c(): pass\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _main(monkeypatch, *argv, stdin=None):
    monkeypatch.setattr(sys, "argv", ["spec-backstop", *argv])
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    return backstop.main()


@pytest.mark.spec("SR-12-001")
@pytest.mark.spec("SR-12-005")
def test_cli_paths_json(repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--paths", "vultron/a/mod.py", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert [g["group"] for g in data["must"]] == ["AA-01", "AA-02"]
    assert set(data) >= {"changed", "must", "info", "no_signal"}


@pytest.mark.spec("SR-12-009")
def test_cli_hub_threshold_flag(repo, monkeypatch, capsys):
    (repo / "test" / "a" / "test_mod.py").write_text(
        "import pytest\nfrom vultron.a.mod import SomeClass\n"
        '@pytest.mark.spec("AA-02-001")\ndef test_c(): pass\n'
    )
    argv = ["--paths", "vultron/a/mod.py", "--json", "--hub-threshold", "0"]
    assert _main(monkeypatch, *argv) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["hubs"] == {"SomeClass": 1}
    assert data["hub_threshold"] == 0


@pytest.mark.spec("SR-12-006")
def test_cli_manifest_exit_codes(repo, monkeypatch, capsys):
    manifest = "Loaded (selected): AA-01\n"
    code = _main(
        monkeypatch,
        "--paths",
        "vultron/a/mod.py",
        "--manifest",
        "-",
        stdin=manifest,
    )
    assert code == 1
    assert "AA-02" in capsys.readouterr().out
    manifest += "Considered, skipped: AA-02 — not touched\n"
    code = _main(
        monkeypatch,
        "--paths",
        "vultron/a/mod.py",
        "--manifest",
        "-",
        stdin=manifest,
    )
    assert code == 0


@pytest.mark.spec("SR-12-007")
def test_cli_no_signal_note(repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--paths", "vultron/z.py") == 0
    err = capsys.readouterr().err
    assert "no deterministic signal for: vultron/z.py" in err


@pytest.mark.spec("SR-12-007")
def test_cli_no_note_when_signal(repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--paths", "vultron/a/mod.py") == 0
    assert "no deterministic signal" not in capsys.readouterr().err


@pytest.mark.spec("SR-12-008")
def test_cli_missing_manifest_exits_2(repo, monkeypatch, capsys):
    code = _main(
        monkeypatch, "--paths", "vultron/a/mod.py", "--manifest", "nope.txt"
    )
    assert code == 2
    assert "nope.txt" in capsys.readouterr().err


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(repo):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.mark.spec("SR-12-008")
def test_cli_bad_base_exits_2(git_repo, monkeypatch, capsys):
    assert _main(monkeypatch, "--base", "no-such-ref") == 2
    assert "no-such-ref" in capsys.readouterr().err


@pytest.mark.spec("SR-12-001")
def test_cli_git_mode_collects_all_change_kinds(git_repo, monkeypatch, capsys):
    _git(git_repo, "checkout", "-q", "-b", "feature")
    mod = git_repo / "vultron" / "a" / "mod.py"
    mod.write_text(mod.read_text().replace("return 2", "return 3"))
    _git(git_repo, "commit", "-q", "-am", "edit")
    (git_repo / "vultron" / "z.py").write_text("def lonely_fn(): return 1\n")
    (git_repo / "vultron" / "new.py").write_text("def fresh(): pass\n")
    assert _main(monkeypatch, "--base", "main", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    changed = {c["path"]: c["symbols"] for c in data["changed"]}
    assert changed == {
        "vultron/a/mod.py": ["SomeClass"],
        "vultron/new.py": ["fresh"],
        "vultron/z.py": ["lonely_fn"],
    }
    assert [g["group"] for g in data["must"]] == ["AA-01", "AA-02"]


# ---------------------------------------------------------------------------
# Noise control (SR-12-010, SR-12-011)
# ---------------------------------------------------------------------------


def _pri(rid, priority, statement="names `vultron/a/mod.py`"):
    return Requirement(rid, rid[:5], rid[:2], statement, priority)


@pytest.mark.spec("SR-12-010")
def test_should_only_group_is_advisory():
    """A SHOULD cannot block: TRIG-05 forced a load with no obligation."""
    report = analyze([_change()], {}, [_pri("EE-01-001", "SHOULD")])
    assert "EE-01" not in report.must
    assert "EE-01" in report.info
    assert any("advisory" in e for e in report.info["EE-01"].evidence)


@pytest.mark.spec("SR-12-010")
@pytest.mark.parametrize("priority", ["MUST", "MUST_NOT"])
def test_mandatory_priorities_still_block(priority):
    report = analyze([_change()], {}, [_pri("EE-01-001", priority)])
    assert "EE-01" in report.must


@pytest.mark.spec("SR-12-010")
def test_one_must_among_shoulds_keeps_the_group_blocking():
    """Only the mandatory ID blocks, and the group is not listed twice."""
    report = analyze(
        [_change()],
        {},
        [_pri("EE-01-001", "SHOULD"), _pri("EE-01-002", "MUST")],
    )
    assert report.must["EE-01"].reqs == {"EE-01-002"}
    assert "EE-01" not in report.info


@pytest.mark.spec("SR-12-011")
def test_logger_is_not_a_changed_symbol():
    """`logger` is module boilerplate, and matched every `logger.info` spec."""
    tree = ast.parse("import logging\nlogger = logging.getLogger(__name__)\n")
    assert changed_symbols(tree, None) == set()


@pytest.mark.spec("SR-12-011")
def test_catch_all_suite_markers_are_advisory():
    """One import from a 17-group suite put 13 unrelated groups in MUST."""
    span = backstop.MONOLITH_GROUP_SPAN + 1
    ids = [f"G{i:02d}-01-001" for i in range(span)]
    marks = ", ".join(f'"{i}"' for i in ids)
    source = (
        "import pytest\nfrom vultron.a.mod import SomeClass\n"
        f"@pytest.mark.spec({marks})\ndef test_a(): pass\n"
    )
    tests = {
        "test/x/test_all.py": index_test_file("test/x/test_all.py", source)
    }
    reqs = [_pri(i, "MUST", "holds") for i in ids]
    report = analyze([_change({13})], tests, reqs)
    assert not report.must
    assert len(report.info) == span
    assert report.monoliths == {"test/x/test_all.py": span}
    assert "catch-all test files" in render_text(report)


@pytest.mark.spec("SR-12-011")
def test_suite_at_the_span_still_promotes():
    span = backstop.MONOLITH_GROUP_SPAN
    ids = [f"G{i:02d}-01-001" for i in range(span)]
    marks = ", ".join(f'"{i}"' for i in ids)
    source = (
        "import pytest\nfrom vultron.a.mod import SomeClass\n"
        f"@pytest.mark.spec({marks})\ndef test_a(): pass\n"
    )
    tests = {
        "test/x/test_all.py": index_test_file("test/x/test_all.py", source)
    }
    reqs = [_pri(i, "MUST", "holds") for i in ids]
    report = analyze([_change({13})], tests, reqs)
    assert len(report.must) == span
    assert not report.monoliths


@pytest.mark.spec("SR-12-011")
def test_no_python_source_says_exit_zero_is_not_coverage():
    """A docs-only diff has no signal, and silence read as a pass."""
    report = analyze([], {}, REQS)
    text = render_text(report)
    assert "no Python source in the diff" in text
    assert "not evidence" in text
