"""Tests for the added-reference check on edited ADRs (MS-15-006, MS-15-007)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from vultron.metadata.adr.added_refs import (
    ReferenceResolver,
    RefKind,
    added_reference_faults,
    check_paths,
    main,
    references_in,
    symbols_in,
)
from vultron.metadata.base import repo_root
from vultron.metadata.specs.lint import _SPEC_SYMBOL_RE


def _adr(body: str, suppress: list[str] | None = None) -> str:
    extra = f"lint_suppress: [{', '.join(suppress)}]\n" if suppress else ""
    return (
        "---\nstatus: proposed\ncreated: 2026-10-01\nupdated: 2026-10-01\n"
        f"revision: 1\n{extra}---\n\n# Title\n\n{body}\n"
    )


@pytest.fixture
def resolver(tmp_path: Path) -> ReferenceResolver:
    """A tree whose only symbols are ``LiveClass`` and ``live_func``."""
    (tmp_path / "vultron").mkdir()
    (tmp_path / "vultron" / "mod.py").write_text(
        "class LiveClass:\n    max_tries = 1\n\n\ndef live_func():\n"
        "    LIVE_CONST = 1\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text("x", encoding="utf-8")
    return ReferenceResolver(tmp_path)


# --- Shapes (AC-4) -----------------------------------------------------------


@pytest.mark.spec("MS-15-006")
@pytest.mark.parametrize(
    ("span", "symbol"),
    [
        ("CaseLogEntry", "CaseLogEntry"),
        ("EMState", "EMState"),
        ("commit_ledger_entry()", "commit_ledger_entry"),
        ("dl.save()", "save"),
        ("AppConfig.max_retries", "max_retries"),
        ("PECState.SIGNATORY", "SIGNATORY"),
    ],
)
def test_shapes_the_spec_corpus_check_misses_are_read(
    span: str, symbol: str
) -> None:
    assert _SPEC_SYMBOL_RE.findall(f"`{span}`") == []
    assert symbol in symbols_in(span)


@pytest.mark.spec("MS-15-006")
def test_underscored_constant_is_still_read() -> None:
    assert symbols_in("SEMANTIC_REGISTRY") == ["SEMANTIC_REGISTRY"]


@pytest.mark.parametrize(
    "span",
    [
        "Case",
        "MUST",
        "queue",
        "httpx.Limits",
        'object_.type_ == "CaseLedgerEntry"',
        "list[str]",
        "uv run pytest",
        "as_Link",
    ],
)
def test_prose_vocabulary_and_expressions_are_not_symbols(span: str) -> None:
    assert symbols_in(span) == []


def test_a_module_prefix_is_not_read_but_its_class_is() -> None:
    assert symbols_in("httpx.AsyncClient") == ["AsyncClient"]


def test_references_skip_frontmatter_and_fenced_code() -> None:
    text = (
        "---\nstatus: proposed\nnote: `FrontOnly`\n---\n"
        "Body names `BodyName` and `docs/x.md`.\n"
        "```python\n`FencedName`\n```\n"
        "And `vultron/core/` too.\n"
    )
    refs = references_in(text)
    assert [(r.kind, r.name, r.line, r.column) for r in refs] == [
        (RefKind.SYMBOL, "BodyName", 5, 13),
        (RefKind.PATH, "docs/x.md", 5, 28),
        (RefKind.DIRECTORY, "vultron/core/", 9, 6),
    ]


# --- Added references only (AC-1, AC-2) --------------------------------------


@pytest.mark.spec("MS-15-006")
def test_added_unresolvable_symbol_fails_with_its_position(
    resolver: ReferenceResolver,
) -> None:
    old = _adr("Uses `LiveClass`.")
    new = _adr("Uses `LiveClass` and `GoneClass`.")
    (fault,) = added_reference_faults("docs/adr/0001-x.md", old, new, resolver)
    assert fault.location == "docs/adr/0001-x.md:10:23"
    assert "'GoneClass'" in fault.detail
    assert "MS-15-006" in fault.detail
    assert str(fault).startswith("docs/adr/0001-x.md:10:23 — ")


@pytest.mark.spec("MS-15-006")
@pytest.mark.parametrize(
    "ref",
    ["live_func()", "LiveClass.max_tries", "LIVE_CONST", "docs/page.md"],
)
def test_added_reference_that_resolves_passes(
    resolver: ReferenceResolver, ref: str
) -> None:
    new = _adr(f"Uses `{ref}`.")
    assert added_reference_faults("a.md", _adr(""), new, resolver) == []


@pytest.mark.spec("MS-15-006")
@pytest.mark.parametrize(
    "ref", ["gone_func()", "docs/gone.md", "docs/gone/dir/", "/abs/x.py"]
)
def test_added_unresolvable_function_or_path_fails(
    resolver: ReferenceResolver, ref: str
) -> None:
    new = _adr(f"Uses `{ref}`.")
    assert len(added_reference_faults("a.md", _adr(""), new, resolver)) == 1


@pytest.mark.spec("MS-15-006")
def test_reference_already_on_the_base_never_fails(
    resolver: ReferenceResolver,
) -> None:
    old = _adr("Was `GoneClass` in `docs/gone.md`.")
    new = _adr("Reworded.\n\nIt was `GoneClass`, see `docs/gone.md`.")
    assert added_reference_faults("a.md", old, new, resolver) == []


@pytest.mark.spec("MS-15-006")
def test_new_record_has_every_reference_added(
    resolver: ReferenceResolver,
) -> None:
    new = _adr("`GoneClass`, `GoneClass` again, and `LiveClass`.")
    faults = added_reference_faults("a.md", None, new, resolver)
    assert [f.detail.split("'")[1] for f in faults] == ["GoneClass"]


# --- Opt-out (AC-5) ----------------------------------------------------------


@pytest.mark.spec("MS-15-007")
def test_inline_removal_annotation_passes_with_the_opt_out(
    resolver: ReferenceResolver,
) -> None:
    body = "`GoneClass` and that module were **deleted** in #2940."
    assert added_reference_faults("a.md", None, _adr(body), resolver)
    suppressed = _adr(body, ["phantom_symbol_ref"])
    assert added_reference_faults("a.md", None, suppressed, resolver) == []


@pytest.mark.spec("MS-15-007")
def test_each_opt_out_covers_only_its_own_kind(
    resolver: ReferenceResolver,
) -> None:
    body = "`GoneClass` lived in `docs/gone.md`."
    by_symbol = added_reference_faults(
        "a.md", None, _adr(body, ["phantom_symbol_ref"]), resolver
    )
    by_path = added_reference_faults(
        "a.md", None, _adr(body, ["phantom_path_ref"]), resolver
    )
    assert [f.detail.split("'")[1] for f in by_symbol] == ["docs/gone.md"]
    assert [f.detail.split("'")[1] for f in by_path] == ["GoneClass"]


def test_invalid_frontmatter_suppresses_nothing(
    resolver: ReferenceResolver,
) -> None:
    text = "---\nlint_suppress: [phantom_symbol_ref]\n---\n`GoneClass`\n"
    assert len(added_reference_faults("a.md", None, text, resolver)) == 1


def test_this_modules_examples_do_not_resolve_in_the_real_tree() -> None:
    """Invented names quoted by the check and its tests stay unresolved."""
    real = ReferenceResolver(repo_root())
    new = _adr("`ZzInventedOnlyHereClass`")
    assert len(added_reference_faults("a.md", None, new, real)) == 1


# --- Against a base commit (AC-1, AC-3) --------------------------------------

_VCS = "g" + "it"


def _run(*args: str) -> None:
    subprocess.run(args, check=True, capture_output=True)


def _commit(message: str) -> None:
    _run(_VCS, "add", "-A")
    _run(
        _VCS,
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.org",
        "commit",
        "-q",
        "-m",
        message,
    )


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository whose HEAD holds one ADR naming a live class."""
    (tmp_path / "vultron").mkdir()
    (tmp_path / "vultron" / "mod.py").write_text(
        "class LiveClass: ...\n", encoding="utf-8"
    )
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        _adr("Uses `LiveClass`."), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _run(_VCS, "init", "-q")
    _commit("x")
    return adr_dir


@pytest.mark.spec("MS-15-006")
def test_check_paths_refuses_an_added_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    (adr_dir / "0001-x.md").write_text(
        _adr("Uses `LiveClass` and `GoneClass`."), encoding="utf-8"
    )
    (adr_dir / "index.md").write_text("`AlsoGone`", encoding="utf-8")
    paths = [Path("docs/adr/0001-x.md"), Path("docs/adr/index.md")]
    (fault,) = check_paths(paths, "HEAD", tmp_path)
    assert fault.path == "docs/adr/0001-x.md"


@pytest.mark.spec("MS-15-006")
def test_a_code_change_never_fails_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing a symbol a record names strands the reference, and passes."""
    adr_dir = _repo(tmp_path, monkeypatch)
    (tmp_path / "vultron" / "mod.py").write_text(
        "class Renamed: ...\n", encoding="utf-8"
    )
    edited = adr_dir / "0001-x.md"
    edited.write_text(
        edited.read_text(encoding="utf-8") + "\nAn editorial line.\n",
        encoding="utf-8",
    )
    assert check_paths([Path("docs/adr/0001-x.md")], "HEAD", tmp_path) == []
    assert check_paths([], "HEAD", tmp_path) == []


@pytest.mark.spec("MS-15-006")
def test_check_paths_follows_a_rename_to_the_old_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adr_dir = _repo(tmp_path, monkeypatch)
    (adr_dir / "0001-x.md").write_text(
        _adr("Uses `LiveClass` and `GoneClass`."), encoding="utf-8"
    )
    _commit("stale reference already on the base")
    _run(_VCS, "mv", "docs/adr/0001-x.md", "docs/adr/0001-y.md")
    assert check_paths([Path("docs/adr/0001-y.md")], "HEAD", tmp_path) == []


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
        _adr("Uses `GoneClass`."), encoding="utf-8"
    )
    with pytest.raises(SystemExit) as refused:
        main(["docs/adr/0001-x.md"])
    assert refused.value.code == 1
    assert "[ERROR] docs/adr/0001-x.md:10:7 — " in capsys.readouterr().err
    with pytest.raises(SystemExit) as bad_base:
        main(["--base", "no-such-ref", "docs/adr/0001-x.md"])
    assert bad_base.value.code == 2
