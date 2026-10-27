"""Tests for reading-path threads (``uv run docs-threads``, ``docs-site``).

Requirements: DF-11-013 (a thread is staged data on its start page), DF-11-014
(the start page's listing is generated and check gated), DF-11-015 (the before
and after sets; the box itself is ``test_thread_boxes.py``), DF-11-016 (the
thread check), DF-09-009 (an empty target set fails).
"""

from __future__ import annotations

import re

import pytest
import yaml

from test.metadata.docs._thread_tree import (
    member,
    page,
    stage,
    start_page,
    tree,
)
from vultron.metadata.base import repo_root
from vultron.metadata.docs import site_sync, threads
from vultron.metadata.docs.landing_pages import (
    BEGIN_MARKER,
    CONTENTS_KEY,
    END_MARKER,
)
from vultron.metadata.docs.page_schema import (
    StageKind,
    ThreadDeclaration,
    ThreadMember,
    ThreadStage,
    is_start_page,
)
from vultron.metadata.docs.threads import (
    LISTING_BEGIN,
    LISTING_END,
    STOPPING_POINT,
    StartThread,
    check_threads,
    load_threads,
    page_titles,
    position,
    render_listing,
    splice_thread_listing,
)
from vultron.metadata.file_loading import (
    MetadataLoadError,
    MetadataLoadErrors,
    validate,
)


def _thread(*stages: ThreadStage) -> StartThread:
    return StartThread(path="start/s.md", title="You do X", stages=stages)


def _chain(*pages: str) -> ThreadStage:
    return ThreadStage(
        title="Chain",
        kind=StageKind.CHAIN,
        members=[ThreadMember(page=p, blurb="b") for p in pages],
    )


def _set(*pages: str) -> ThreadStage:
    return ThreadStage(
        title="Set",
        kind=StageKind.SET,
        members=[ThreadMember(page=p, blurb="b") for p in pages],
    )


def _paths(members: tuple[ThreadMember, ...]) -> list[str]:
    return [m.path for m in members]


# ---------------------------------------------------------------------------
# Schema (AC-1)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-013")
class TestThreadSchema:
    def test_a_staged_thread_validates(self):
        declared = validate(
            ThreadDeclaration,
            {
                "thread": [
                    stage(
                        "Decide",
                        "chain",
                        "a.md",
                        "b/c.md#part",
                        stopping_point=True,
                    ),
                    stage("Go on", "set", "d.md", framing="Prose."),
                ]
            },
        )
        first, second = declared.thread
        assert first.kind is StageKind.CHAIN and first.stopping_point
        assert first.members[1].path == "b/c.md"
        assert second.kind is StageKind.SET and second.framing == "Prose."

    @pytest.mark.parametrize(
        ("stage", "fault"),
        [
            ("not a mapping", "thread.0"),
            (
                {"title": "T", "kind": "tree", "members": [member("a.md")]},
                "kind",
            ),
            (
                {
                    "title": "T",
                    "kind": "set",
                    "members": [member("a.md")],
                    "extra": 1,
                },
                "extra",
            ),
            ({"title": "T", "kind": "set", "members": []}, "members"),
            ({"kind": "set", "members": [member("a.md")]}, "title"),
            (
                {"title": " ", "kind": "set", "members": [member("a.md")]},
                "title",
            ),
            (
                {"title": "T", "kind": "set", "members": [{"page": "a.md"}]},
                "blurb",
            ),
            (
                {
                    "title": "T",
                    "kind": "set",
                    "stopping_point": "yes",
                    "members": [member("a.md")],
                },
                "stopping_point",
            ),
        ],
        ids=[
            "malformed",
            "unknown-kind",
            "unknown-key",
            "empty-stage",
            "no-title",
            "blank-title",
            "no-blurb",
            "non-bool-stop",
        ],
    )
    def test_a_malformed_stage_is_a_finding(self, stage, fault):
        with pytest.raises(MetadataLoadError, match=fault):
            validate(ThreadDeclaration, {"thread": [stage]})

    @pytest.mark.parametrize(
        "target",
        [
            "https://example.org/x.md",
            "mailto:a@example.org",
            "/abs/x.md",
            "../outside.md",
            "img/diagram.png",
            "a.md#",
        ],
    )
    def test_a_non_page_member_is_a_finding(self, target):
        stage = {"title": "T", "kind": "set", "members": [member(target)]}
        with pytest.raises(MetadataLoadError, match="page"):
            validate(ThreadDeclaration, {"thread": [stage]})

    def test_an_empty_thread_is_a_finding(self):
        with pytest.raises(MetadataLoadError, match="thread"):
            validate(ThreadDeclaration, {"thread": []})

    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            ("start/coordinate-cases.md", True),
            ("start/index.md", False),
            ("start/sub/x.md", False),
            ("topics/x.md", False),
        ],
    )
    def test_start_pages(self, path, expected):
        assert is_start_page(path) is expected


# ---------------------------------------------------------------------------
# Before and after sets (DF-11-015)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-015")
class TestPosition:
    def test_inside_a_chain_the_neighbours_are_its_members(self):
        thread = _thread(_chain("a.md", "b.md", "c.md"))
        where = position(thread, "b.md")
        assert where is not None
        assert _paths(where.before) == ["a.md"]
        assert _paths(where.after) == ["c.md"]

    def test_a_set_member_sees_the_neighbouring_stages(self):
        thread = _thread(
            _chain("a.md", "b.md"),
            _set("x.md", "y.md"),
            _chain("c.md", "d.md"),
        )
        where = position(thread, "y.md")
        assert where is not None
        assert _paths(where.before) == ["b.md"]
        assert _paths(where.after) == ["c.md"]

    def test_a_chain_end_sees_every_page_of_a_neighbouring_set(self):
        thread = _thread(
            _set("x.md", "y.md"), _chain("a.md", "b.md"), _set("p.md", "q.md")
        )
        first = position(thread, "a.md")
        last = position(thread, "b.md")
        assert first is not None and last is not None
        assert _paths(first.before) == ["x.md", "y.md"]
        assert _paths(first.after) == ["b.md"]
        assert _paths(last.before) == ["a.md"]
        assert _paths(last.after) == ["p.md", "q.md"]

    def test_the_ends_of_the_thread_have_one_side_empty(self):
        thread = _thread(_chain("a.md", "b.md"))
        first = position(thread, "a.md")
        last = position(thread, "b.md")
        assert first is not None and last is not None
        assert first.before == () and last.after == ()

    def test_a_fragment_does_not_hide_the_page(self):
        thread = _thread(_chain("a.md", "g.md#part", "c.md"))
        where = position(thread, "g.md")
        assert where is not None
        assert _paths(where.after) == ["c.md"]

    def test_a_page_off_the_thread_has_no_position(self):
        assert position(_thread(_chain("a.md")), "z.md") is None


# ---------------------------------------------------------------------------
# Start-page listing (AC-2)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-014")
class TestListing:
    def _thread(self) -> StartThread:
        return StartThread(
            path="start/s.md",
            title="You do X",
            stages=(
                ThreadStage(
                    title="Decide",
                    kind=StageKind.CHAIN,
                    stopping_point=True,
                    members=[
                        ThreadMember(page="topics/a.md", blurb="first."),
                        ThreadMember(
                            page="ref/g.md#roles",
                            blurb="terms.",
                            label="Roles",
                        ),
                    ],
                ),
                ThreadStage(
                    title="Go further",
                    kind=StageKind.SET,
                    framing="One sentence.\nAnother sentence.\n",
                    members=[ThreadMember(page="howto/h.md", blurb="any.")],
                ),
            ),
        )

    def test_renders_stages_as_sections_chains_numbered_sets_bulleted(self):
        titles = {
            "topics/a.md": "A",
            "ref/g.md": "Glossary",
            "howto/h.md": "H",
        }
        assert render_listing(self._thread(), titles) == (
            "## Decide\n\n"
            "1. [A](../topics/a.md) — first.\n"
            "2. [Roles](../ref/g.md#roles) — terms.\n\n"
            f"{STOPPING_POINT}\n\n"
            "## Go further\n\n"
            "One sentence.\nAnother sentence.\n\n"
            "- [H](../howto/h.md) — any."
        )

    def test_framing_outside_the_markers_survives(self):
        titles = {"topics/a.md": "A", "ref/g.md": "G", "howto/h.md": "H"}
        current = (
            f"# T\n\nHand-written.\n\n{LISTING_BEGIN}\nstale\n{LISTING_END}\n"
        )
        spliced = splice_thread_listing(current, self._thread(), titles)
        assert spliced.startswith("# T\n\nHand-written.\n\n")
        assert "stale" not in spliced and "[A](../topics/a.md)" in spliced
        again = splice_thread_listing(spliced, self._thread(), titles)
        assert again == spliced

    def test_missing_markers_fail_rather_than_append(self):
        with pytest.raises(ValueError, match="markers"):
            splice_thread_listing(
                "# T\n",
                self._thread(),
                {"topics/a.md": "A", "ref/g.md": "G", "howto/h.md": "H"},
            )

    def test_the_label_defaults_to_the_page_title(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "You do X", [stage("S", "set", "a.md")]
                ),
                "a.md": "---\ntitle: Front Title\n---\n# Body Title\n",
            },
        )
        assert page_titles(root, load_threads(root)) == {"a.md": "Front Title"}

    def test_a_hand_edit_is_stale_and_write_repairs_it(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "You do X", [stage("S", "set", "a.md")]
                ),
                "a.md": page("A"),
                # docs-site refuses a nav with no generated landing page.
                "guides/index.md": (
                    f"---\n{CONTENTS_KEY}: generated\n---\n\n# Guides\n\n"
                    f"{BEGIN_MARKER}\n\n{END_MARKER}\n"
                ),
            },
            nav=[{"Guides": ["guides/index.md", "a.md"]}],
        )
        start = root / "docs/start/s.md"
        assert "docs/start/s.md" in site_sync.stale_artifacts(root)
        site_sync.write_artifacts(root)
        assert "docs/start/s.md" not in site_sync.stale_artifacts(root)
        start.write_text(start.read_text().replace("— what", "— hand, what"))
        assert "docs/start/s.md" in site_sync.stale_artifacts(root)
        site_sync.write_artifacts(root)
        assert "- [A](../a.md) — what you get." in start.read_text()
        assert "Framing." in start.read_text()


# ---------------------------------------------------------------------------
# Thread check (AC-4)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-016")
class TestThreadCheck:
    def test_a_valid_tree_passes(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page("S", [stage("S", "chain", "a.md")]),
                "start/index.md": page("Start"),
                "a.md": page("A"),
            },
        )
        (thread,) = check_threads(root)
        assert thread.path == "start/s.md" and thread.title == "S"

    def test_a_missing_page_fails(self, tmp_path):
        root = tree(
            tmp_path,
            {"start/s.md": start_page("S", [stage("S", "set", "gone.md")])},
        )
        with pytest.raises(
            MetadataLoadErrors, match=r"gone\.md.*does not exist"
        ):
            check_threads(root)

    def test_a_working_record_page_fails(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S", [stage("S", "set", "adr/0001-x.md")]
                ),
                "adr/0001-x.md": page("Decision"),
            },
        )
        with pytest.raises(MetadataLoadErrors, match="working record"):
            check_threads(root)

    def test_an_include_fragment_fails(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page("S", [stage("S", "set", "frag.md")]),
                "host.md": '# Host\n\n{% include-markdown "frag.md" %}\n',
                "frag.md": "Shared text.\n",
            },
        )
        with pytest.raises(MetadataLoadErrors, match="not a page"):
            check_threads(root)

    def test_a_page_listed_twice_in_one_thread_fails(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S",
                    [
                        stage("S", "chain", "a.md", "b.md"),
                        stage("T", "set", "a.md#part"),
                    ],
                ),
                "a.md": page("A"),
                "b.md": page("B"),
            },
        )
        with pytest.raises(MetadataLoadErrors, match=r"a\.md more than once"):
            check_threads(root)

    def test_a_page_on_two_threads_passes(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page("S", [stage("S", "set", "a.md")]),
                "start/t.md": start_page("T", [stage("T", "set", "a.md")]),
                "a.md": page("A"),
            },
        )
        assert len(check_threads(root)) == 2

    def test_no_threads_fails(self, tmp_path):
        root = tree(
            tmp_path, {"start/index.md": page("Start"), "a.md": page("A")}
        )
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            check_threads(root)

    def test_a_start_page_without_a_thread_fails(self, tmp_path):
        root = tree(tmp_path, {"start/s.md": page("S")})
        with pytest.raises(MetadataLoadErrors, match="declares no `thread:`"):
            load_threads(root)

    def test_every_fault_is_reported(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S", [stage("S", "set", "x.md", "y.md")]
                ),
                "start/t.md": page("T"),
            },
        )
        with pytest.raises(MetadataLoadErrors) as first:
            load_threads(root)
        assert len(first.value.failures) == 1
        (root / "docs/start/t.md").unlink()
        with pytest.raises(MetadataLoadErrors) as second:
            check_threads(root)
        assert len(second.value.failures) == 2

    def test_cli_exits_nonzero_on_a_fault(self, tmp_path, monkeypatch, capsys):
        root = tree(tmp_path, {"start/s.md": page("S")})
        monkeypatch.setattr(threads, "_find_repo_root", lambda: root)
        with pytest.raises(SystemExit) as exc:
            threads.main([])
        assert exc.value.code == 1
        assert "thread" in capsys.readouterr().err

    def test_the_committed_threads_pass(self):
        """The CI check for the ``docs-threads`` hook on a ``vultron/`` change.

        On a ``docs/`` change, ``docs-build-check.yml`` runs the hook (DOCBW-03-013).
        """
        committed = check_threads(repo_root())
        assert {t.path for t in committed} == {
            "start/coordinate-cases.md",
            "start/connect-your-tracker.md",
            "start/study-the-process.md",
            "start/contribute.md",
            "start/how-vultron-works.md",
        }


@pytest.mark.spec("DF-11-016")
@pytest.mark.parametrize(
    "changed",
    [
        "docs/start/contribute.md",
        "docs/topics/background/what-is-vultron.md",
        "mkdocs.yml",
        "vultron/metadata/docs/threads.py",
        "vultron/metadata/docs/page_schema.py",
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
    hook = hooks["docs-threads"]

    assert hook["entry"] == "uv run docs-threads"
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)


@pytest.mark.spec("DF-11-013")
class TestRenderingEdges:
    @pytest.mark.parametrize("brk", ["\n", "\r"])
    @pytest.mark.parametrize("field", ["title", "label"])
    def test_a_multi_line_title_or_label_is_a_finding(self, field, brk):
        stage_ = {"title": "T", "kind": "set", "members": [member("a.md")]}
        target = stage_ if field == "title" else stage_["members"][0]
        target[field] = f"one{brk}two"
        with pytest.raises(MetadataLoadError, match="single line"):
            validate(ThreadDeclaration, {"thread": [stage_]})

    def test_brackets_in_a_label_are_escaped(self):
        thread = _thread(
            ThreadStage(
                title="S",
                kind=StageKind.SET,
                members=[ThreadMember(page="a.md", blurb="b", label="A [x]")],
            )
        )
        assert r"[A \[x\]](../a.md)" in render_listing(thread, {"a.md": "A"})

    def test_a_backslash_in_a_label_is_escaped(self):
        thread = _thread(
            ThreadStage(
                title="S",
                kind=StageKind.SET,
                members=[ThreadMember(page="a.md", blurb="b", label="C:\\")],
            )
        )
        assert r"[C:\\](../a.md)" in render_listing(thread, {"a.md": "A"})

    def test_framing_keeps_line_breaks_and_indentation(self):
        thread = _thread(
            ThreadStage(
                title="S",
                kind=StageKind.SET,
                framing="Intro:\n\n- one\n    - nested   \n",
                members=[ThreadMember(page="a.md", blurb="b")],
            )
        )
        listing = render_listing(thread, {"a.md": "A"})
        assert "Intro:\n\n- one\n    - nested\n\n- [A]" in listing

    def test_every_missing_member_title_is_reported(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S", [stage("S", "set", "x.md", "y.md", "a.md")]
                ),
                "a.md": page("A"),
            },
        )
        with pytest.raises(MetadataLoadErrors) as exc:
            page_titles(root, load_threads(root))
        assert [
            str(f).split(" lists ")[1].split()[0] for f in exc.value.failures
        ] == [
            "x.md",
            "y.md",
        ]
