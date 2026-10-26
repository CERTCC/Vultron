"""Tests for the check that no thread page depends on a later member.

Requirements: DF-11-024 (the rule), DF-11-013 (a thread's stages are a partial
order), DF-11-002 (the term-dependency scan it reuses), DF-11-010 (a fragment
renders on its host), DF-09-009 (an empty target set fails); findings are
attributed per MS-17-001. The scan itself is tested in ``test_level_order.py``
and ``test_concept_scan.py``.
"""

from __future__ import annotations

import re

import pytest
import yaml

from test.metadata.docs._level_tree import leveled_page, make_repo
from test.metadata.docs._thread_tree import stage, start_page
from vultron.metadata.base import repo_root
from vultron.metadata.docs import thread_order
from vultron.metadata.docs.level_order import check_level_order
from vultron.metadata.docs.page_schema import StageKind, ThreadStage
from vultron.metadata.docs.thread_order import (
    check_thread_order,
    later_members,
    main,
    prune_baseline,
    read_baseline,
    write_baseline,
)
from vultron.metadata.docs.threads import StartThread, check_threads
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

#: The committed baseline, pinned. It may only shrink: drop a key here when
#: ``--prune-baseline`` drops it from the file, and never add one. Pinning the
#: keys rather than their count also stops an entry being swapped for another.
_BASELINED: frozenset[tuple[str, str, str]] = frozenset()

#: The fixture's ledger page, ``topics/ledger.md``, introduces this term.
_TERM = "Case Ledger Entry"
_USE = "# A\n\nEach case ledger entry is signed.\n"
_KEY = ("start/s.md", "howto/a.md", _TERM)


def _repo(tmp_path, stages, files=None, nav=None):
    """A checkout whose one start page, ``start/s.md``, opens *stages*.

    ``howto/a.md`` uses the ledger term unlinked, at the ledger's own level,
    so the level check has nothing to say about it.
    """
    return make_repo(
        tmp_path,
        {
            "start/s.md": start_page("S", stages),
            "howto/a.md": leveled_page(400, _USE),
            "howto/b.md": leveled_page(400),
            **(files or {}),
        },
        nav=nav,
    )


def _failures(root, baseline=None):
    with pytest.raises(MetadataLoadErrors) as info:
        check_thread_order(root, baseline=baseline or {})
    return info.value.failures


def _chain(*pages):
    return stage("Read in order", "chain", *pages)


def _set(*pages):
    return stage("Read any", "set", *pages)


# ---------------------------------------------------------------------------
# The rule (AC-1)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-024")
class TestRule:
    def test_earlier_use_of_a_later_members_term_fails(self, tmp_path):
        """A level-compliant page still cannot run ahead of its thread."""
        root = _repo(tmp_path, [_chain("howto/a.md", "topics/ledger.md")])
        assert check_level_order(root, baseline={}).baselined == []

        (failure,) = _failures(root)

        # Frontmatter is four lines, so the body's third line is line 7.
        assert failure.location == "docs/howto/a.md:7:6"
        assert "docs/topics/ledger.md introduces later" in str(failure)
        assert "docs/start/s.md" in str(failure)
        assert "DF-11-024" in str(failure)

    def test_link_to_the_introducer_satisfies_the_rule(self, tmp_path):
        body = "# A\n\nEach [case ledger entry](../topics/ledger.md).\n"
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "topics/ledger.md")],
            {"howto/a.md": leveled_page(400, body)},
        )

        assert check_thread_order(root, baseline={}).baselined == []

    def test_earlier_link_to_the_introducer_satisfies_the_rule(self, tmp_path):
        body = (
            "# A\n\nRead [the ledger](../topics/ledger.md) first.\n\n"
            "Each case ledger entry is signed.\n"
        )
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "topics/ledger.md")],
            {"howto/a.md": leveled_page(400, body)},
        )

        assert check_thread_order(root, baseline={}).baselined == []

    def test_glossary_link_at_the_use_satisfies_the_rule(self, tmp_path):
        body = "# A\n\nEach [case ledger entry](../reference/glossary.md#l).\n"
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "topics/ledger.md")],
            {"howto/a.md": leveled_page(400, body)},
        )

        assert check_thread_order(root, baseline={}).baselined == []

    def test_link_later_on_the_same_line_does_not(self, tmp_path):
        body = "# A\n\nEach case ledger entry; see [x](../topics/ledger.md).\n"
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "topics/ledger.md")],
            {"howto/a.md": leveled_page(400, body)},
        )

        (failure,) = _failures(root)
        assert failure.location == "docs/howto/a.md:7:6"

    def test_use_after_the_introducer_passes(self, tmp_path):
        root = _repo(tmp_path, [_chain("topics/ledger.md", "howto/a.md")])

        assert check_thread_order(root, baseline={}).baselined == []

    def test_members_of_one_set_are_unordered(self, tmp_path):
        root = _repo(tmp_path, [_set("howto/a.md", "topics/ledger.md")])

        assert check_thread_order(root, baseline={}).baselined == []

    def test_a_later_stage_comes_after_every_earlier_member(self, tmp_path):
        root = _repo(
            tmp_path,
            [_set("howto/b.md", "howto/a.md"), _set("topics/ledger.md")],
        )

        (failure,) = _failures(root)
        assert failure.path == "docs/howto/a.md"

    def test_a_page_off_the_thread_is_not_checked(self, tmp_path):
        """Only members are ordered; the level rule governs other pages."""
        root = _repo(tmp_path, [_chain("howto/b.md", "topics/ledger.md")])

        assert check_thread_order(root, baseline={}).baselined == []

    def test_each_thread_is_checked_on_its_own(self, tmp_path):
        """A page can precede the introducer on one thread only."""
        root = _repo(
            tmp_path,
            [_chain("topics/ledger.md", "howto/a.md")],
            {
                "start/t.md": start_page(
                    "T", [_chain("howto/a.md", "topics/ledger.md")]
                )
            },
        )

        (failure,) = _failures(root)
        assert "docs/start/t.md" in str(failure)
        assert "docs/start/s.md" not in str(failure)

    def test_fragment_rendered_by_an_earlier_member_is_checked(self, tmp_path):
        host = '# A\n\n{% include-markdown "./_frag.md" %}\n'
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "topics/ledger.md")],
            {
                "howto/a.md": leveled_page(400, host),
                "howto/_frag.md": "Each case ledger entry is signed.\n",
            },
            nav=["start/s.md", "howto/a.md", "topics/ledger.md"],
        )

        (failure,) = _failures(root)
        assert failure.location == "docs/howto/_frag.md:1:6"
        assert "renders on docs/howto/a.md" in str(failure)

    def test_fragment_on_two_earlier_members_is_one_finding(self, tmp_path):
        host = '# H\n\n{% include-markdown "./_frag.md" %}\n'
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "howto/b.md", "topics/ledger.md")],
            {
                "howto/a.md": leveled_page(400, host),
                "howto/b.md": leveled_page(400, host),
                "howto/_frag.md": "Each case ledger entry is signed.\n",
            },
            nav=["start/s.md", "howto/a.md", "howto/b.md", "topics/ledger.md"],
        )

        (failure,) = _failures(root)
        assert failure.location == "docs/howto/_frag.md:1:6"
        assert "renders on docs/howto/a.md" in str(failure)

    def test_the_glossary_as_an_earlier_member_is_not_checked(self, tmp_path):
        """It defines every term it lists, as the level check also holds."""
        root = _repo(
            tmp_path, [_chain("reference/glossary.md", "topics/ledger.md")]
        )

        assert check_thread_order(root, baseline={}).baselined == []

    def test_no_threads_fails(self, tmp_path):
        """DF-09-009: resolving no thread is a failure (AC-3)."""
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(400, _USE)})

        with pytest.raises(MetadataLoadError, match="no reading-path threads"):
            check_thread_order(root, baseline={})


@pytest.mark.spec("DF-11-013")
def test_later_members_follow_stage_and_chain_order():
    def built(kind, *pages):
        return ThreadStage.model_validate(stage("S", kind, *pages))

    thread = StartThread(
        path="start/s.md",
        title="S",
        stages=(
            built(StageKind.CHAIN, "a.md", "b.md"),
            built(StageKind.SET, "c.md", "d.md"),
            built(StageKind.CHAIN, "e.md"),
        ),
    )

    order = {
        member.path: [m.path for m in later]
        for member, later in later_members(thread)
    }

    assert order == {
        "a.md": ["b.md", "c.md", "d.md", "e.md"],
        "b.md": ["c.md", "d.md", "e.md"],
        "c.md": ["e.md"],
        "d.md": ["e.md"],
        "e.md": [],
    }


# ---------------------------------------------------------------------------
# Baseline (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-024")
class TestBaseline:
    def test_baselined_violation_is_tolerated(self, tmp_path):
        root = _repo(tmp_path, [_chain("howto/a.md", "topics/ledger.md")])

        result = check_thread_order(root, baseline={_KEY: "awaiting #1"})

        assert result.baselined == [_KEY]

    def test_stale_entry_fails(self, tmp_path):
        root = _repo(tmp_path, [_chain("topics/ledger.md", "howto/a.md")])

        (failure,) = _failures(root, baseline={_KEY: "old"})

        assert "no longer a violation" in failure.detail
        assert "--prune-baseline" in failure.detail
        assert "_BASELINED" in failure.detail

    def test_stale_committed_entry_names_its_line(self, tmp_path, monkeypatch):
        root = _repo(tmp_path, [_chain("topics/ledger.md", "howto/a.md")])
        path = tmp_path / "baseline.txt"
        write_baseline({_KEY: "old"}, path)
        monkeypatch.setattr(thread_order, "BASELINE_PATH", path)

        with pytest.raises(MetadataLoadErrors) as info:
            check_thread_order(root)

        (failure,) = info.value.failures
        entry = "start/s.md | howto/a.md | Case Ledger Entry | old"
        number = path.read_text().splitlines().index(entry) + 1
        assert failure.location == f"baseline.txt:{number}"

    @pytest.mark.parametrize(
        "line",
        [
            "start/s.md | howto/a.md | Case Ledger Entry",
            "start/s.md | howto/a.md | Case Ledger Entry | ",
            "howto/a.md | Case Ledger Entry | reason",
        ],
        ids=["no-reason", "empty-reason", "no-thread"],
    )
    def test_malformed_entry_names_its_line(self, tmp_path, line):
        path = tmp_path / "baseline.txt"
        path.write_text(f"# header\n\n{line}\n")

        with pytest.raises(MetadataLoadErrors) as info:
            read_baseline(path)

        (failure,) = info.value.failures
        assert failure.location == "baseline.txt:3"
        assert "thread | page | term | reason" in failure.detail

    def test_round_trip(self, tmp_path):
        path = tmp_path / "baseline.txt"
        entries = {("s.md", "b.md", "T"): "b", ("s.md", "a.md", "T"): "a"}

        write_baseline(entries, path)

        assert read_baseline(path) == entries
        body = [
            ln
            for ln in path.read_text().splitlines()
            if ln and not ln.startswith("#")
        ]
        assert body == ["s.md | a.md | T | a", "s.md | b.md | T | b"]

    def test_prune_only_removes(self, tmp_path):
        """An unlisted violation stays a finding: prune never admits it."""
        root = _repo(
            tmp_path,
            [_chain("howto/a.md", "howto/b.md", "topics/ledger.md")],
            {"howto/b.md": leveled_page(400, _USE)},
        )
        path = tmp_path / "baseline.txt"
        gone = ("start/s.md", "howto/gone.md", _TERM)
        write_baseline({_KEY: "still open", gone: "fixed"}, path)

        assert prune_baseline(root, baseline_path=path) == 1
        assert read_baseline(path) == {_KEY: "still open"}

    def test_committed_baseline_never_grows(self):
        """A new finding is fixed by a link or a reorder, never an entry."""
        added = set(read_baseline()) - _BASELINED
        assert not added, (
            f"thread_order_baseline.txt gained {sorted(added)}. Link each new "
            f"use to its introducing page (SG-11) instead of baselining it."
        )

    def test_pin_matches_the_committed_baseline(self):
        """A pruned entry leaves the pin too, so the pin cannot re-admit it."""
        assert set(read_baseline()) == _BASELINED


# ---------------------------------------------------------------------------
# Entry points and the real tree (AC-3)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-024")
def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = _repo(tmp_path, [_chain("howto/a.md", "topics/ledger.md")])
    monkeypatch.setattr(thread_order, "_find_repo_root", lambda: root)
    monkeypatch.setattr(thread_order, "BASELINE_PATH", tmp_path / "none.txt")

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] 1 docs thread-order finding(s)")
    assert "docs/howto/a.md:7:6" in err


@pytest.mark.spec("DF-11-024")
def test_cli_reports_a_pass(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, [_chain("topics/ledger.md", "howto/a.md")])
    monkeypatch.setattr(thread_order, "_find_repo_root", lambda: root)
    monkeypatch.setattr(thread_order, "BASELINE_PATH", tmp_path / "none.txt")

    main([])

    out = capsys.readouterr().out
    assert out.startswith("Checked 1 thread(s) against 1 introduced concept")
    assert "0 baselined violation(s) remain" in out


@pytest.mark.spec("DF-11-024")
def test_cli_prunes_the_committed_baseline(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, [_chain("topics/ledger.md", "howto/a.md")])
    path = tmp_path / "baseline.txt"
    write_baseline({_KEY: "fixed"}, path)
    monkeypatch.setattr(thread_order, "_find_repo_root", lambda: root)
    monkeypatch.setattr(thread_order, "BASELINE_PATH", path)

    main(["--prune-baseline"])

    assert "Removed 1 entry(ies) from baseline.txt." in capsys.readouterr().out
    assert read_baseline(path) == {}


@pytest.mark.spec("DF-11-024")
def test_the_committed_threads_pass_the_order_check():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_thread_order()

    assert result.threads == len(check_threads(repo_root()))
    assert result.introductions > 0


@pytest.mark.spec("DF-11-024")
@pytest.mark.parametrize(
    "changed",
    [
        "docs/start/contribute.md",
        "docs/topics/process_models/_dfa_notation_definition.md",
        "mkdocs.yml",
        "vultron/metadata/docs/thread_order.py",
        "vultron/metadata/docs/thread_order_baseline.txt",
        "vultron/metadata/docs/level_order.py",
        "vultron/metadata/docs/threads.py",
        "vultron/metadata/docs/baseline_file.py",
        "vultron/metadata/file_loading.py",
    ],
)
def test_pre_commit_hook_runs_on_every_input(changed):
    config = yaml.safe_load(
        (repo_root() / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    )
    hooks = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
    }
    hook = hooks["docs-thread-order"]

    assert hook["entry"] == "uv run docs-thread-order"
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)
