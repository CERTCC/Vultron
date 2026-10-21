"""Tests for the page-type badge the site renders from frontmatter.

Requirement: DF-11-019 (ADR-0136). The badge is
``overrides/partials/page_type.html``, included by ``overrides/main.html`` and
styled by ``docs/stylesheets/page_type.css``. Its labels are checked against
:data:`~vultron.metadata.docs.page_schema.PAGE_TYPE_BADGES`, so the template
cannot drift from the schema.
"""

from __future__ import annotations

import re
from pathlib import Path

import jinja2
import pytest

from vultron.metadata.base import mkdocs_config, repo_root
from vultron.metadata.docs.page_frontmatter import classify_docs_tree
from vultron.metadata.docs.page_schema import (
    PAGE_TYPE_BADGES,
    PageType,
    is_working_record,
)
from vultron.metadata.file_loading import load_frontmatter

pytestmark = pytest.mark.spec("DF-11-019")

_ROOT = repo_root()
_OVERRIDES = _ROOT / "overrides"
_STYLESHEETS = _ROOT / "docs" / "stylesheets"


class _Page:
    """The slice of an MkDocs page the template reads."""

    def __init__(self, meta: dict[str, object] | None) -> None:
        self.meta = meta


def _render(page: _Page | None) -> str:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(_OVERRIDES),
        undefined=jinja2.StrictUndefined,
        autoescape=True,
    )
    template = env.get_template("partials/page_type.html")
    return template.render(page=page).strip()


@pytest.mark.parametrize(
    ("page_type", "label"),
    [(member.value, label) for member, label in PAGE_TYPE_BADGES.items()],
)
def test_each_rendered_type_shows_its_label(page_type, label):
    html = _render(_Page({"page_type": page_type}))

    assert f'class="page-type page-type--{page_type}"' in html
    assert re.search(rf">\s*{re.escape(label)}\s*<", html)


def test_every_type_but_routing_has_a_badge():
    assert set(PAGE_TYPE_BADGES) == set(PageType) - {PageType.ROUTING}


@pytest.mark.parametrize(
    "page",
    [
        _Page({"page_type": "routing"}),
        _Page({"title": "No declaration"}),
        _Page({}),
        _Page({"page_type": "howto"}),
        _Page({"page_type": ["reference"]}),
        _Page({"page_type": {"reference": True}}),
        None,
    ],
    ids=[
        "routing",
        "undeclared",
        "no-meta",
        "unknown",
        "list",
        "mapping",
        "no-page",
    ],
)
def test_no_badge_without_a_rendered_type(page):
    assert _render(page) == ""


def test_the_template_names_no_type_the_schema_lacks():
    """A label in the template with no schema entry is a stale badge."""
    source = (_OVERRIDES / "partials" / "page_type.html").read_text()
    labels_block = re.search(r"page_type_labels = \{(.*?)\}", source, re.S)
    assert labels_block is not None
    named = dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', labels_block[1]))

    assert named == {
        member.value: label for member, label in PAGE_TYPE_BADGES.items()
    }


@pytest.mark.parametrize(
    "page_type", [member.value for member in PAGE_TYPE_BADGES]
)
def test_each_rendered_type_has_an_icon_rule(page_type):
    css = (_STYLESHEETS / "page_type.css").read_text()
    rule = re.search(
        rf"\.page-type--{re.escape(page_type)}\s*\{{(.*?)\}}", css, re.S
    )

    assert rule is not None
    assert "--page-type-icon: url('data:image/svg+xml" in rule[1]
    assert "--page-type-color:" in rule[1]


def test_routing_has_no_style_rule():
    css = (_STYLESHEETS / "page_type.css").read_text()
    assert ".page-type--routing" not in css


def test_the_theme_override_includes_the_badge_in_the_content_block():
    source = (_OVERRIDES / "main.html").read_text()
    block = re.search(
        r"\{% block content %\}(.*?)\{% endblock %\}", source, re.S
    )

    assert '{% extends "base.html" %}' in source
    assert block is not None
    assert '{% include "partials/page_type.html" %}' in block[1]
    assert "{{ super() }}" in block[1]


def test_the_site_loads_the_override_and_the_stylesheet():
    config = mkdocs_config(_ROOT)
    theme = config.get("theme")
    extra_css = (_STYLESHEETS / "extra.css").read_text()
    extra_css_files = config.get("extra_css")

    assert isinstance(theme, dict)
    assert Path(str(theme.get("custom_dir"))) == Path("overrides")
    assert isinstance(extra_css_files, list)
    assert "stylesheets/extra.css" in extra_css_files
    assert '@import "page_type.css";' in extra_css


def test_no_reader_facing_page_replaces_the_theme_template():
    """A page with its own ``template:`` would skip the badge's content block."""
    tree = classify_docs_tree(_ROOT)
    replacing = [
        rel
        for rel in tree.pages
        if not is_working_record(rel)
        and "template"
        in load_frontmatter(_ROOT / "docs" / rel, root=_ROOT).metadata
    ]

    assert tree.pages
    assert replacing == []


_HAND_BADGE = re.compile(
    r"""class=["'][^"']*\bpage-type\b|\{[^}]*\.page-type\b"""
)


def test_no_page_writes_a_badge_by_hand():
    """Badges come only from frontmatter; no check compares a hand-written one."""
    sources = sorted((_ROOT / "docs").rglob("*.md"))
    hand_written = [
        path.relative_to(_ROOT).as_posix()
        for path in sources
        if _HAND_BADGE.search(path.read_text(encoding="utf-8"))
    ]

    assert sources
    assert hand_written == []


@pytest.mark.parametrize(
    "text",
    [
        '<span class="page-type page-type--reference">Reference</span>',
        "[Reference](x.md){ .page-type }",
    ],
    ids=["html", "attr-list"],
)
def test_the_hand_badge_pattern_catches_both_spellings(text):
    assert _HAND_BADGE.search(text)
