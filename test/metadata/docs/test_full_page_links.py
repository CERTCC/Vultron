"""Tests for the ``full_page_links`` MkDocs hook (#4092).

On the single-page edition of the Protocol Specification (``full.md``) the hook
rewrites a link to another page of the section, with a fragment, to a bare
``#fragment`` link. A fragment-less link, an ``index.md`` link, a link outside
the section and every page other than ``full.md`` are left alone.

The last class assembles the real ``full.md`` the way the build does
(``include-markdown`` first, then the hook) and checks that no cross-reference
leaves the page and that every in-page target is a heading id on it.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, cast

import markdown  # type: ignore[import-untyped]  # Python-Markdown ships no stubs
import pytest
from mkdocs_include_markdown_plugin.event import (
    on_page_markdown as include_markdown,
)
from mkdocs_include_markdown_plugin.plugin import IncludeMarkdownPlugin

from vultron.metadata.base import mkdocs_config, repo_root
from vultron.metadata.docs.anchor_ids import anchor_ids_in
from vultron.metadata.docs.full_page_links import (
    FULL_PAGE_SRC_URI,
    on_page_markdown,
    rewrite_section_links,
)

_HOOK_PATH = "vultron/metadata/docs/full_page_links.py"

# A link that leaves full.md for a page beside it, with a fragment.
_SIBLING_LINK = re.compile(r"\]\((?:\./)?([^)/#\s]+\.md)#")
_IN_PAGE_LINK = re.compile(r"\]\(#([^)\s]+)")


def _run(md: str, src_uri: str) -> str:
    page = SimpleNamespace(file=SimpleNamespace(src_uri=src_uri))
    return on_page_markdown(
        md,
        page=cast(Any, page),
        config=cast(Any, None),
        files=cast(Any, None),
    )


class TestRewriteSectionLinks:
    @pytest.mark.parametrize(
        "page",
        [
            "tracking-models.md",
            "./tracking-models.md",
            "annex-g-capability-shapes.md",
            "open-questions.md",
        ],
    )
    def test_same_section_link_with_fragment_is_rewritten(self, page: str):
        md = f"See [§6 Report Management (RM) State Machine]({page}#6-rm)."
        assert rewrite_section_links(md) == (
            "See [§6 Report Management (RM) State Machine](#6-rm)."
        )

    def test_link_title_is_kept(self):
        md = '[x](layers.md#41-report-management-messages "RM messages")'
        assert rewrite_section_links(md) == (
            '[x](#41-report-management-messages "RM messages")'
        )

    def test_every_link_on_a_line_is_rewritten(self):
        md = "[a](layers.md#a) and [b](conformance.md#b)"
        assert rewrite_section_links(md) == "[a](#a) and [b](#b)"

    @pytest.mark.parametrize(
        "md",
        [
            pytest.param("[Layers](layers.md)", id="fragment-less"),
            pytest.param("[parts](index.md#parts)", id="index-with-fragment"),
            pytest.param("[spec](index.md)", id="index"),
            pytest.param(
                "[RM](../../topics/process_models/rm/index.md#rm-states)",
                id="outside-the-section",
            ),
            pytest.param(
                "[CS](../formal_protocol/transitions.md#cs)",
                id="sibling-directory",
            ),
            pytest.param("[here](#already-in-page)", id="already-in-page"),
            pytest.param(
                "[ext](https://example.org/layers.md#x)", id="external"
            ),
        ],
    )
    def test_other_links_are_untouched(self, md: str):
        assert rewrite_section_links(md) == md


class TestOnPageMarkdown:
    _MD = "[§6](tracking-models.md#6-rm) and [Layers](layers.md)"

    def test_full_page_is_rewritten(self):
        assert _run(self._MD, FULL_PAGE_SRC_URI) == (
            "[§6](#6-rm) and [Layers](layers.md)"
        )

    @pytest.mark.parametrize(
        "src_uri",
        [
            "reference/vultron-spec/tracking-models.md",
            "reference/vultron-spec/annex-a-single-vendor.md",
            "reference/vultron-spec/index.md",
            "reference/other/full.md",
        ],
    )
    def test_every_other_page_is_untouched(self, src_uri: str):
        assert _run(self._MD, src_uri) == self._MD


def test_hook_is_registered_in_mkdocs_yml():
    """The hook only runs if ``mkdocs.yml`` names it under ``hooks:``."""
    hooks = cast(list[str], mkdocs_config().get("hooks") or [])
    assert _HOOK_PATH in hooks, (
        f"{_HOOK_PATH} is not under hooks: in mkdocs.yml"
    )


# Enough of the site's Markdown extensions for headings to render with the ids
# the build gives them: ``toc`` makes the ids, and ``superfences`` keeps a
# ``#`` line inside a fenced (or exec) block from reading as a heading.
_HEADING_EXTENSIONS = [
    "toc",
    "attr_list",
    "md_in_html",
    "admonition",
    "def_list",
    "footnotes",
    "tables",
    "pymdownx.details",
    "pymdownx.superfences",
    "pymdownx.tabbed",
]


@pytest.fixture(scope="module")
def full_page_markdown() -> str:
    """``full.md`` as the build hands it to Python-Markdown: assembled by
    ``include-markdown`` (with the site's options), then rewritten by the
    hook."""
    plugin = IncludeMarkdownPlugin()
    options = next(
        entry["include-markdown"]
        for entry in cast(list[Any], mkdocs_config()["plugins"])
        if isinstance(entry, dict) and "include-markdown" in entry
    )
    errors, _ = plugin.load_config(options)
    assert not errors, errors
    docs_dir = repo_root() / "docs"
    src = docs_dir / FULL_PAGE_SRC_URI
    page = SimpleNamespace(file=SimpleNamespace(abs_src_path=str(src)))
    assembled = include_markdown(
        src.read_text(encoding="utf-8"),
        cast(Any, page),
        str(docs_dir),
        plugin=plugin,
    )
    return _run(assembled, FULL_PAGE_SRC_URI)


class TestAssembledFullPage:
    def test_no_cross_reference_leaves_for_a_part_page(
        self, full_page_markdown: str
    ):
        leaving = sorted(
            set(_SIBLING_LINK.findall(full_page_markdown)) - {"index.md"}
        )
        assert not leaving, f"full.md still links off-page to {leaving}"

    def test_every_in_page_target_is_a_unique_heading_id(
        self, full_page_markdown: str
    ):
        """A rewritten link must land on its heading: the id must exist, and
        no duplicate heading may share it (a duplicate gains a ``_1`` suffix,
        so the bare link would land on the first copy)."""
        targets = set(_IN_PAGE_LINK.findall(full_page_markdown))
        assert targets, "no in-page links found; the check would be vacuous"
        ids = anchor_ids_in(
            markdown.markdown(
                full_page_markdown, extensions=_HEADING_EXTENSIONS
            )
        )
        assert not sorted(targets - ids), "dead in-page anchors"
        duplicated = sorted(t for t in targets if f"{t}_1" in ids)
        assert not duplicated, f"ambiguous in-page anchors: {duplicated}"


def test_full_page_source_exists():
    """The hook keys on this path; a move would silently disable it."""
    assert (repo_root() / "docs" / FULL_PAGE_SRC_URI).is_file()
