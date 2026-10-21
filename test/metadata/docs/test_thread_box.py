"""Tests for the ``thread_box`` MkDocs hook.

Requirements: DF-11-015 (a member page shows, per thread, the pages before and
after it and a link to the start page, the same for every reader), DF-11-017
(no nav-order footer on a member page), DF-11-009 (titled by situation, never
by ``stakeholder_type``).
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import jinja2
import markdown  # type: ignore[import-untyped]  # Python-Markdown ships no stubs
import material  # type: ignore[import-untyped]  # ships no stubs
import pytest

from test.metadata.docs._thread_tree import page, stage, start_page, tree
from vultron.metadata.docs import thread_box
from vultron.metadata.docs.thread_box import FOOTER, hide_footer, load_build

_BODY = "# Shared\n\nBody text.\n"


def _run(src_uri: str, meta: dict[str, object] | None = None):
    page_ = SimpleNamespace(
        file=SimpleNamespace(src_uri=src_uri), meta=meta or {}
    )
    out = thread_box.on_page_markdown(
        _BODY,
        page=cast(Any, page_),
        config=cast(Any, None),
        files=cast(Any, None),
    )
    return out, page_.meta


@pytest.fixture
def two_threads(tmp_path: Path):
    """``topics/shared.md`` sits mid-chain on one thread, in a set on another."""
    root = tree(
        tmp_path,
        {
            "start/practice.md": start_page(
                "You coordinate cases",
                [stage("Learn", "chain", "a.md", "topics/shared.md", "b.md")],
            ),
            "start/study.md": start_page(
                "You study disclosure",
                [
                    stage("Begin", "chain", "c.md", "d.md"),
                    stage("Browse", "set", "topics/shared.md", "e.md"),
                    stage("Finish", "set", "f.md", "g.md"),
                ],
            ),
            **{f"{x}.md": page(x.upper()) for x in "abcdefg"},
            "topics/shared.md": (
                "---\nstakeholder_type: [cvd-practitioner]\nlevel: 300\n---\n"
                + _BODY
            ),
        },
    )
    load_build(root)
    yield root
    thread_box._BUILD.threads = ()
    thread_box._BUILD.titles = {}


@pytest.mark.spec("DF-11-015")
class TestMemberBox:
    def test_one_box_per_thread_with_its_neighbours(self, two_threads):
        out, _meta = _run("topics/shared.md")
        practice, study = out.split('!!! abstract "')[1:]
        assert practice.startswith('Reading path: You coordinate cases"')
        assert "[A](../a.md)" in practice and "[B](../b.md)" in practice
        assert (
            "[Back to the start of this reading path](../start/practice.md)"
            in practice
        )
        assert study.startswith('Reading path: You study disclosure"')
        before, after = study.split("After this page:")
        assert "[D](../d.md)" in before and "[C](../c.md)" not in before
        assert "[F](../f.md)" in after and "[G](../g.md)" in after
        assert "[E](../e.md)" not in study
        assert "(../start/study.md)" in study
        assert out.startswith(_BODY.rstrip("\n"))

    def test_the_box_is_the_same_for_every_reader(self, two_threads):
        out, _meta = _run("topics/shared.md")
        html = markdown.markdown(out, extensions=["admonition"])
        for forbidden in (
            "stakeholder_type",
            "cvd-practitioner",
            "level",
            "300",
        ):
            assert forbidden not in out
        assert "<script" not in html
        assert not re.search(r'href="[^"]*\?', html)
        assert html.count('class="admonition abstract"') == 2

    def test_the_first_page_has_no_before_set(self, two_threads):
        out, _meta = _run("a.md")
        assert "Before this page:" not in out
        assert "After this page:" in out and "(topics/shared.md)" in out

    def test_a_page_on_no_thread_is_unchanged(self, two_threads):
        out, meta = _run("start/practice.md", {"hide": ["toc"]})
        assert out == _BODY
        assert meta == {"hide": ["toc"]}


@pytest.mark.spec("DF-11-017")
class TestFooter:
    def test_a_member_page_hides_the_footer(self, two_threads):
        _out, meta = _run("b.md", {"hide": ["toc"]})
        assert meta["hide"] == ["toc", FOOTER]

    @pytest.mark.parametrize(
        ("meta", "expected"),
        [
            ({}, [FOOTER]),
            ({"hide": [FOOTER]}, [FOOTER]),
            ({"hide": "toc"}, ["toc", FOOTER]),
        ],
    )
    def test_hide_footer(self, meta, expected):
        hide_footer(meta)
        assert meta["hide"] == expected

    def test_the_hook_is_registered(self):
        from vultron.metadata.base import mkdocs_config, repo_root

        hooks = mkdocs_config(repo_root()).get("hooks")
        assert isinstance(hooks, list)
        assert "vultron/metadata/docs/thread_box.py" in hooks


def _footer(meta: dict[str, object]) -> str:
    """Render Material's own footer partial for a page with *meta*."""
    templates = Path(material.__file__).parent / "templates"
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates), autoescape=True
    )
    env.filters["url"] = lambda value: value
    neighbour = SimpleNamespace(url="x/", title="X")
    return env.get_template("partials/footer.html").render(
        features=["navigation.footer"],
        page=SimpleNamespace(
            meta=meta, previous_page=neighbour, next_page=neighbour
        ),
        lang=SimpleNamespace(t=lambda key: key),
        config=SimpleNamespace(
            theme=SimpleNamespace(
                icon=SimpleNamespace(previous=None, next=None)
            ),
            copyright=None,
            extra=SimpleNamespace(social=None, generator=False),
        ),
    )


_FOOTER_NAV = re.compile(r'<nav class="md-footer__inner md-grid"[^>]*>')


@pytest.mark.spec("DF-11-017")
class TestRenderedFooter:
    def test_a_member_page_renders_its_footer_hidden(self, two_threads):
        _out, meta = _run("b.md")
        (nav,) = _FOOTER_NAV.findall(_footer(meta))
        assert nav.endswith("hidden>")

    def test_a_page_on_no_thread_renders_its_footer(self, two_threads):
        _out, meta = _run("start/practice.md")
        (nav,) = _FOOTER_NAV.findall(_footer(meta))
        assert "hidden" not in nav
