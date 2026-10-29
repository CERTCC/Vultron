"""Tests for the reading-path box fragments (``uv run docs-site``).

Requirements: DF-11-015 (one box per thread on every member page and start
page: a start, previous, current and next table, the same for every reader),
DF-11-022 (a section member's box names the section), DF-11-023 (each box is a
committed fragment under ``docs/start/_paths/``, generated, check gated and
excluded from the build), DF-11-009 (titled by situation, never by
``stakeholder_type``).
"""

from __future__ import annotations

import re
from pathlib import Path

import markdown  # type: ignore[import-untyped]  # Python-Markdown ships no stubs
import pytest

from test.metadata.docs._thread_tree import member, page, start_page, tree
from vultron.metadata.base import excluded_docs_spec, mkdocs_config, repo_root
from vultron.metadata.docs import site_sync
from vultron.metadata.docs.landing_pages import (
    BEGIN_MARKER,
    CONTENTS_KEY,
    END_MARKER,
)
from vultron.metadata.docs.threads import (
    BOX_DIR,
    EMPTY_CELL,
    StartThread,
    box_fragment_path,
    include_line,
    load_threads,
    page_titles,
    render_box,
    render_boxes,
)

_EXTENSIONS = ["admonition", "attr_list", "md_in_html", "tables"]


def _stage(title: str, kind: str, *members: dict) -> dict[str, object]:
    return {"title": title, "kind": kind, "members": list(members)}


@pytest.fixture
def two_threads(tmp_path: Path) -> Path:
    """``topics/shared.md`` is mid-chain on one thread and in a set on another.

    ``g.md#later`` is a section member, the last member of its thread.
    """
    return tree(
        tmp_path,
        {
            "start/practice.md": start_page(
                "You coordinate cases",
                [
                    _stage(
                        "Learn",
                        "chain",
                        member("a.md"),
                        member("topics/shared.md"),
                        member("b.md"),
                    )
                ],
            ),
            "start/study.md": start_page(
                "You study disclosure",
                [
                    _stage("Begin", "chain", member("c.md"), member("d.md")),
                    _stage(
                        "Browse",
                        "set",
                        member("topics/shared.md"),
                        member("e.md"),
                    ),
                    _stage(
                        "Finish",
                        "set",
                        member("f.md"),
                        member("g.md#later", label="The later part"),
                    ),
                ],
            ),
            **{f"{x}.md": page(x.upper()) for x in "abcdefg"},
            "topics/shared.md": (
                "---\nstakeholder_type: [cvd-practitioner]\nlevel: 300\n---\n"
                "# Shared\n"
            ),
            # docs-site refuses a nav with no generated landing page.
            "guides/index.md": (
                f"---\n{CONTENTS_KEY}: generated\n---\n\n# Guides\n\n"
                f"{BEGIN_MARKER}\n\n{END_MARKER}\n"
            ),
        },
        nav=[{"Guides": ["guides/index.md", "a.md"]}],
    )


def _boxes(root: Path) -> dict[str, str]:
    threads = load_threads(root)
    return render_boxes(threads, page_titles(root, threads))


def _thread(root: Path, path: str) -> StartThread:
    return next(t for t in load_threads(root) if t.path == path)


def _cells(box: str) -> dict[str, str]:
    """``{column heading: cell HTML}`` of a rendered box."""
    html = markdown.markdown(box, extensions=_EXTENSIONS)
    headings = re.findall(r"<th>(.*?)</th>", html)
    cells = re.findall(r"<td>(.*?)</td>", html, re.DOTALL)
    assert len(headings) == len(cells) == 4
    return dict(zip(headings, cells, strict=True))


def _box(root: Path, thread: str, target: str) -> str:
    return _boxes(root)[box_fragment_path(_thread(root, thread), target)]


@pytest.mark.spec("DF-11-015", "DF-11-034")
class TestBoxTable:
    def test_one_box_per_thread_and_target(self, two_threads):
        fragments = set(_boxes(two_threads))
        assert fragments == {
            f"{BOX_DIR}/practice/start__practice.md",
            f"{BOX_DIR}/practice/a.md",
            f"{BOX_DIR}/practice/topics__shared.md",
            f"{BOX_DIR}/practice/b.md",
            f"{BOX_DIR}/study/start__study.md",
            *(f"{BOX_DIR}/study/{x}.md" for x in "cdef"),
            f"{BOX_DIR}/study/topics__shared.md",
            f"{BOX_DIR}/study/g--later.md",
        }

    def test_columns_are_start_previous_current_next(self, two_threads):
        box = _box(two_threads, "start/practice.md", "topics/shared.md")
        assert list(_cells(box)) == ["Start", "Previous", "Current", "Next"]

    def test_a_chain_member_sees_its_neighbours(self, two_threads):
        box = _box(two_threads, "start/practice.md", "topics/shared.md")
        cells = _cells(box)
        assert (
            '<a href="../../practice.md">You coordinate cases</a>'
            in (cells["Start"])
        )
        assert '<a href="../../../a.md">A</a>' in cells["Previous"]
        assert '<a href="../../../b.md">B</a>' in cells["Next"]
        assert "This page is part of <em>Learn</em>." in markdown.markdown(
            box, extensions=_EXTENSIONS
        )

    def test_a_set_member_sees_the_neighbouring_stages(self, two_threads):
        cells = _cells(_box(two_threads, "start/study.md", "topics/shared.md"))
        assert "../../../d.md" in cells["Previous"]
        assert "../../../c.md" not in cells["Previous"]
        assert "../../../f.md" in cells["Next"]
        assert "../../../g.md#later" in cells["Next"]
        assert "e.md" not in cells["Previous"] + cells["Next"]

    def test_the_current_cell_is_text_not_a_link(self, two_threads):
        cells = _cells(_box(two_threads, "start/study.md", "topics/shared.md"))
        assert cells["Current"].split() == ["<ul>", "<li>Shared</li>", "</ul>"]

    def test_an_empty_set_is_three_dashes(self, two_threads):
        first = _cells(_box(two_threads, "start/practice.md", "a.md"))
        last = _cells(_box(two_threads, "start/study.md", "g.md#later"))
        assert first["Previous"].strip() == EMPTY_CELL
        assert last["Next"].strip() == EMPTY_CELL
        assert first["Next"].strip() != EMPTY_CELL

    def test_a_start_page_box(self, two_threads):
        box = _box(two_threads, "start/study.md", "start/study.md")
        cells = _cells(box)
        assert cells["Start"].split() == [
            "<ul>",
            "<li>You",
            "study",
            "disclosure</li>",
            "</ul>",
        ]
        assert cells["Current"] == cells["Start"]
        assert cells["Previous"].strip() == EMPTY_CELL
        assert '<a href="../../../c.md">C</a>' in cells["Next"]
        assert "d.md" not in cells["Next"]
        assert "is part of" not in box

    def test_a_start_page_box_next_is_a_whole_first_set(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S", [_stage("Any", "set", member("a.md"), member("b.md"))]
                ),
                "a.md": page("A"),
                "b.md": page("B"),
            },
        )
        cells = _cells(_box(root, "start/s.md", "start/s.md"))
        assert "a.md" in cells["Next"] and "b.md" in cells["Next"]

    @pytest.mark.spec("DF-11-035")
    def test_titled_by_situation_and_the_same_for_every_reader(
        self, two_threads
    ):
        for path, box in _boxes(two_threads).items():
            html = markdown.markdown(box, extensions=_EXTENSIONS)
            situation = (
                "You coordinate cases"
                if "/practice/" in path
                else "You study disclosure"
            )
            assert (
                f'<p class="admonition-title">Reading path: {situation}</p>'
                in html
            )
            for forbidden in ("stakeholder_type", "cvd-practitioner", "level"):
                assert forbidden not in box
            assert "<script" not in html
            assert not re.search(r'href="[^"]*\?', html)
            assert html.count('class="admonition abstract reading-path"') == 1

    def test_a_quote_in_the_title_is_escaped(self):
        thread = StartThread(
            path="start/s.md",
            title='You say "hi" & <go>',
            stages=(),
        )
        box = render_box(thread, "start/s.md", {})
        assert "Reading path: You say &quot;hi&quot; &amp; &lt;go&gt;</p>" in (
            box
        )

    def test_a_target_off_the_thread_is_refused(self, two_threads):
        thread = _thread(two_threads, "start/practice.md")
        with pytest.raises(ValueError, match=r"c\.md is not on the thread"):
            render_box(thread, "c.md", {})


@pytest.mark.spec("DF-11-022")
class TestSectionWording:
    def test_a_section_member_names_the_section(self, two_threads):
        box = _box(two_threads, "start/study.md", "g.md#later")
        assert "This section is part of *Finish*." in box
        assert "<li>The later part</li>" in _cells(box)["Current"]
        assert 'data-member="g.md#later"' in box

    def test_a_whole_page_member_keeps_the_page_wording(self, two_threads):
        box = _box(two_threads, "start/study.md", "f.md")
        assert "This page is part of *Finish*." in box
        assert "section" not in box


@pytest.mark.spec("DF-11-023")
class TestFragments:
    def test_fragment_names_flatten_the_path_and_keep_the_anchor(self):
        thread = StartThread(path="start/s.md", title="S", stages=())
        assert box_fragment_path(thread, "a/b/c.md") == (
            f"{BOX_DIR}/s/a__b__c.md"
        )
        assert box_fragment_path(thread, "a/b.md#one") != box_fragment_path(
            thread, "a/b.md#two"
        )

    def test_two_targets_sharing_a_name_are_refused(self, tmp_path):
        root = tree(
            tmp_path,
            {
                "start/s.md": start_page(
                    "S",
                    [_stage("A", "set", member("a__b.md"), member("a/b.md"))],
                ),
                "a__b.md": page("X"),
                "a/b.md": page("Y"),
            },
        )
        with pytest.raises(ValueError, match="would share the box fragment"):
            _boxes(root)

    @pytest.mark.parametrize(
        ("host", "expected"),
        [
            ("topics/a.md", '{% include-markdown "../start/_paths/s/x.md" %}'),
            ("start/s.md", '{% include-markdown "./_paths/s/x.md" %}'),
            ("index.md", '{% include-markdown "./start/_paths/s/x.md" %}'),
        ],
    )
    def test_include_line_is_relative_to_the_host(self, host, expected):
        assert include_line(host, f"{BOX_DIR}/s/x.md") == expected

    def test_write_creates_every_fragment_and_check_passes(self, two_threads):
        written = site_sync.write_artifacts(two_threads)
        assert f"docs/{BOX_DIR}/study/g--later.md" in written
        assert not [
            p for p in site_sync.stale_artifacts(two_threads) if BOX_DIR in p
        ]

    def test_a_hand_edit_is_stale(self, two_threads):
        site_sync.write_artifacts(two_threads)
        path = f"docs/{BOX_DIR}/practice/a.md"
        target = two_threads / path
        target.write_text(target.read_text() + "edited\n")
        assert path in site_sync.stale_artifacts(two_threads)

    def test_a_fragment_for_a_page_off_its_thread_is_stale_and_deleted(
        self, two_threads
    ):
        site_sync.write_artifacts(two_threads)
        orphan = f"docs/{BOX_DIR}/practice/gone.md"
        (two_threads / orphan).write_text("old box\n")
        assert orphan in site_sync.stale_artifacts(two_threads)
        assert orphan in site_sync.write_artifacts(two_threads)
        assert not (two_threads / orphan).exists()
        assert orphan not in site_sync.stale_artifacts(two_threads)

    def test_the_fragment_directory_is_excluded_from_the_build(self):
        excluded = excluded_docs_spec(mkdocs_config(repo_root()))
        assert excluded.match_file(f"{BOX_DIR}/coordinate-cases/a.md")

    @pytest.mark.spec("DF-11-044")
    def test_the_build_adds_no_box(self):
        hooks = mkdocs_config(repo_root()).get("hooks") or []
        assert isinstance(hooks, list)
        assert not [hook for hook in hooks if "thread" in str(hook)]


@pytest.mark.spec("DF-11-023")
def test_write_reports_a_deleted_fragment(two_threads, monkeypatch, capsys):
    site_sync.write_artifacts(two_threads)
    orphan = f"docs/{BOX_DIR}/practice/gone.md"
    (two_threads / orphan).write_text("old box\n")
    monkeypatch.setattr(site_sync, "repo_root", lambda: two_threads)
    site_sync.main(["--write"])
    assert capsys.readouterr().out == f"Deleted {orphan}\n"
