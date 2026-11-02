"""`build-context` hands build's loaded context to pr-ship (PAD-07-015 to PAD-07-019).

`write` records facts only; `check` answers `mode=reuse` only for a valid file of
the current branch recorded at an ancestor of `HEAD`, and `mode=fallback` with a
reason for every other case — absent, not JSON, malformed, another branch, stale.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from test.metadata._script_sandbox import commit, git
from vultron.metadata.planning import build_context
from vultron.metadata.planning.build_context import BuildContext, main

BRANCH = "task/9-demo"
MANIFEST = """\
Spec manifest
Loaded (floor): PAD-07-001, PAD-18-004
Loaded (cross-cutting): ARCH
Loaded (selected): PAD-07 — pre-push review; SR-12 — backstop
Considered, skipped: PAD-04 — claiming unchanged
"""


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A task branch fresh off origin/main, with one note and a glossary."""
    for name in [n for n in os.environ if n.startswith("GIT_")]:
        monkeypatch.delenv(name)
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/wire.md").write_text("x\n")
    glossary = tmp_path / build_context.GLOSSARY
    glossary.parent.mkdir(parents=True)
    glossary.write_text(
        "# Glossary\n\n## Behavior Trees\n\n## Use-Case Layer\n"
    )
    (tmp_path / ".gitignore").write_text(".claude/\n")
    commit(tmp_path, "a.txt", "a\n", "base")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "main")
    git(tmp_path, "checkout", "-qb", BRANCH)
    (tmp_path / "manifest.txt").write_text(MANIFEST)
    topics = SimpleNamespace(
        files=[SimpleNamespace(id=t) for t in ("ARCH", "PAD", "SR")]
    )
    monkeypatch.setattr(build_context, "load_registry", lambda _: topics)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write(*extra: str) -> int:
    return main(
        [
            "write",
            "--manifest", "manifest.txt",
            "--hint", "wire layer",
            "--hint", "BT integration",
            "--note", "notes/wire.md",
            "--glossary", "Behavior Trees",
            *extra,
        ]
    )  # fmt: skip


def _path(repo: Path) -> Path:
    return repo / ".claude/pr-context-task%2F9-demo.json"


def _check(
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, list[str]]]:
    capsys.readouterr()
    rc = main(["check"])
    out: dict[str, list[str]] = {}
    for line in capsys.readouterr().out.splitlines():
        key, value = line.split("=", 1)
        out.setdefault(key, []).append(value)
    return rc, out


def test_path_is_branch_keyed_like_the_prepush_artifact(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["path"]) == 0
    assert capsys.readouterr().out.strip() == str(_path(repo))
    assert main(["path", "--branch", "bug/1-a%b"]) == 0
    assert (
        capsys.readouterr()
        .out.strip()
        .endswith("pr-context-bug%2F1-a%25b.json")
    )


def test_write_records_the_facts_found(repo: Path) -> None:
    assert _write() == 0
    recorded = json.loads(_path(repo).read_text())
    head = git(repo, "rev-parse", "HEAD")
    assert recorded == {
        "schema_version": "1.0",
        "branch": BRANCH,
        "head_sha": head,
        "base_sha": head,
        "spec_ids": ["PAD-07-001", "PAD-18-004"],
        "spec_groups": ["PAD-07", "SR-12"],
        "spec_topics": ["ARCH"],
        "domain_hints": ["wire layer", "BT integration"],
        "notes": ["notes/wire.md"],
        "glossary_sections": ["Behavior Trees"],
    }


def test_the_record_refuses_any_other_field() -> None:
    """No place for the author's reasoning (PAD-07-001, PAD-07-015)."""
    fields = {
        "branch": BRANCH,
        "head_sha": "a",
        "base_sha": "b",
        "domain_hints": ["x"],
    }
    BuildContext.model_validate(fields)
    with pytest.raises(ValidationError):
        BuildContext.model_validate({**fields, "reasoning": "I think..."})


@pytest.mark.parametrize(
    ("args", "manifest"),
    [
        (("--note", "notes/missing.md"), MANIFEST),
        (("--glossary", "No Such Section"), MANIFEST),
        ((), "Spec manifest\nConsidered, skipped: PAD-04 — n/a\n"),
        (("--base", "origin/nowhere"), MANIFEST),
    ],
)
def test_write_refuses_inputs_that_are_not_facts(
    repo: Path, args: tuple[str, ...], manifest: str
) -> None:
    (repo / "manifest.txt").write_text(manifest)
    assert _write(*args) == 2
    assert not _path(repo).exists()


def test_check_reuses_a_fresh_file(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write()
    commit(repo, "b.txt", "work\n")
    rc, out = _check(capsys)
    assert rc == 0
    assert out["mode"] == ["reuse"]
    assert out["spec_ids"] == ["PAD-07-001,PAD-18-004"]
    assert out["spec_groups"] == ["PAD-07,SR-12"]
    assert out["spec_topics"] == ["ARCH"]
    assert out["hint"] == ["wire layer", "BT integration"]
    assert out["note"] == ["notes/wire.md"]
    assert out["glossary"] == ["Behavior Trees"]


def test_check_survives_create_prs_cherry_pick_onto_a_newer_base(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Written before the first commit, the file outlives the freshen."""
    _write()
    commit(repo, "b.txt", "work\n")
    work = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "main")
    commit(repo, "c.txt", "main moves\n")
    git(repo, "checkout", "-q", "-B", BRANCH, "main")
    git(repo, "cherry-pick", work)
    rc, out = _check(capsys)
    assert (rc, out["mode"]) == (0, ["reuse"])


def _fallback(capsys: pytest.CaptureFixture[str]) -> str:
    rc, out = _check(capsys)
    assert rc == 3
    assert out["mode"] == ["fallback"]
    assert "spec_ids" not in out
    return out["reason"][0]


@pytest.mark.usefixtures("repo")
def test_check_falls_back_when_the_file_is_absent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert _fallback(capsys) == "no build context file"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("{not json", "not valid JSON"),
        ("[1, 2]", "malformed"),
        ('{"branch": "task/9-demo"}', "malformed"),
    ],
)
def test_check_falls_back_on_a_malformed_file(
    repo: Path, capsys: pytest.CaptureFixture[str], text: str, reason: str
) -> None:
    _path(repo).parent.mkdir(exist_ok=True)
    _path(repo).write_text(text)
    assert reason in _fallback(capsys)


def test_check_falls_back_on_a_file_with_an_extra_field(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write()
    data = json.loads(_path(repo).read_text())
    _path(repo).write_text(json.dumps({**data, "verdict": "looks fine"}))
    assert "malformed" in _fallback(capsys)


def test_check_falls_back_on_a_file_for_another_branch(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write()
    data = json.loads(_path(repo).read_text())
    _path(repo).write_text(json.dumps({**data, "branch": "task/8-other"}))
    assert "task/8-other" in _fallback(capsys)


def test_check_falls_back_when_the_recorded_head_left_the_history(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    commit(repo, "b.txt", "first try\n")
    _write()
    git(repo, "reset", "-q", "--hard", "HEAD~1")
    commit(repo, "b.txt", "second try\n")
    assert "not an ancestor" in _fallback(capsys)


def test_check_falls_back_when_the_recorded_head_is_unknown(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write()
    data = json.loads(_path(repo).read_text())
    _path(repo).write_text(json.dumps({**data, "head_sha": "f" * 40}))
    assert "not in the object store" in _fallback(capsys)


def test_check_is_a_setup_error_off_a_branch(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write()
    git(repo, "checkout", "-q", "--detach")
    assert main(["check"]) == 2
    assert "not on a branch" in capsys.readouterr().err


def test_write_refuses_an_unreadable_manifest(repo: Path) -> None:
    (repo / "manifest.txt").unlink()
    assert _write() == 2


def test_write_refuses_a_checkout_without_the_glossary(repo: Path) -> None:
    (repo / build_context.GLOSSARY).unlink()
    assert _write() == 2


def test_write_refuses_an_empty_hint(repo: Path) -> None:
    assert _write("--hint", "") == 2
    assert not _path(repo).exists()


def test_write_is_a_setup_error_off_a_branch(repo: Path) -> None:
    git(repo, "checkout", "-q", "--detach")
    assert _write() == 2


def test_outside_a_work_tree_is_a_setup_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    monkeypatch.chdir(outside)
    assert main(["check"]) == 2
