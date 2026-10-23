"""Tests for the ``anchor_ids`` MkDocs hook (#3735).

The hook registers every ``id`` in a page's rendered HTML as a link target so
that a ``<a id="mv-03-002">`` printed by an exec block survives
``mkdocs build --strict``. Its collection rule must match MkDocs' own raw-HTML
collector (``id`` on any tag, ``name`` on ``<a>`` only), it must add to — never
replace — what MkDocs already collected, and it must leave the HTML alone.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from vultron.metadata.base import mkdocs_config
from vultron.metadata.docs.anchor_ids import anchor_ids_in, on_page_content

_HOOK_PATH = "vultron/metadata/docs/anchor_ids.py"


def _page(present: set[str] | None) -> Any:
    """A stand-in for ``mkdocs.structure.pages.Page`` with the one attribute
    the hook reads."""
    return SimpleNamespace(present_anchor_ids=present)


def _run(html: str, present: set[str] | None) -> tuple[str, Any]:
    page = _page(present)
    out = on_page_content(
        html, page=page, config=cast(Any, None), files=cast(Any, None)
    )
    return out, page


class TestAnchorIdsIn:
    def test_id_on_an_arbitrary_tag(self):
        html = '<table><tr><td><a id="mv-03-002"></a><code>MV-03-002</code>'
        assert anchor_ids_in(html) == {"mv-03-002"}

    def test_id_on_any_element_not_only_anchors(self):
        html = '<div id="x"></div><span id="y"></span><h2 id="z">Z</h2>'
        assert anchor_ids_in(html) == {"x", "y", "z"}

    def test_name_on_an_anchor_tag(self):
        assert anchor_ids_in('<a name="legacy"></a>') == {"legacy"}

    def test_name_on_a_non_anchor_tag_is_ignored(self):
        """``<input name>``/``<div name>`` are not scroll targets; MkDocs'
        collector ignores them and so does the hook."""
        html = '<input name="q"><div name="not-a-target"></div>'
        assert anchor_ids_in(html) == frozenset()

    @pytest.mark.parametrize("html", ['<a id=""></a>', '<a name=""></a>'])
    def test_empty_values_are_ignored(self, html: str):
        assert anchor_ids_in(html) == frozenset()

    def test_no_anchors_gives_an_empty_set(self):
        assert anchor_ids_in("<p>plain prose</p>") == frozenset()


class TestOnPageContent:
    def test_adds_ids_to_the_existing_set(self):
        """The set MkDocs collected is extended, not replaced."""
        present = {"from-mkdocs"}
        _, page = _run('<a id="from-exec"></a>', present)
        assert page.present_anchor_ids == {"from-mkdocs", "from-exec"}
        assert page.present_anchor_ids is present

    def test_leaves_a_page_alone_when_validation_is_off(self):
        """``present_anchor_ids`` is ``None`` when anchor validation is off or
        the page was not rendered; the hook must not invent a set."""
        _, page = _run('<a id="x"></a>', None)
        assert page.present_anchor_ids is None

    def test_returns_the_html_unchanged(self):
        html = '<h2 id="h">Head</h2>\n<a id="x"></a><p>text &amp; more</p>'
        out, _ = _run(html, set())
        assert out == html

    def test_a_fabricated_anchor_is_still_absent(self):
        """The hook registers what is in the HTML and nothing else, so a link
        to a made-up id keeps failing under --strict."""
        _, page = _run('<a id="rmb-12-001"></a>', set())
        assert "rmb-12-001" in page.present_anchor_ids
        assert "rmb-99-999" not in page.present_anchor_ids


def test_hook_is_registered_in_mkdocs_yml():
    """The hook only runs if ``mkdocs.yml`` names it under ``hooks:``."""
    hooks = cast(list[str], mkdocs_config().get("hooks") or [])
    assert _HOOK_PATH in hooks, (
        f"{_HOOK_PATH} is not under hooks: in mkdocs.yml"
    )
