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
import material  # type: ignore[import-untyped]
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
# The installed Material theme supplies base.html and the theme's own main.html.
# The project's overrides/ directory takes precedence (same order as MkDocs).
_THEME_TEMPLATES = Path(material.__file__).parent / "templates"


def _make_jinja_env() -> jinja2.Environment:
    """Jinja2 environment that mirrors MkDocs' override-then-theme lookup."""
    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.FileSystemLoader(str(_OVERRIDES)),
                jinja2.FileSystemLoader(str(_THEME_TEMPLATES)),
            ]
        ),
        undefined=jinja2.Undefined,
        autoescape=True,
    )


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


def _template_inherits_badge(template_name: str) -> bool:
    """True when the named override template extends main.html.

    A template that extends ``main.html`` inherits the page-type badge via
    ``super()`` and is safe for reader-facing pages.  A template that does
    not extend ``main.html`` bypasses the badge's content block.
    """
    path = _OVERRIDES / str(template_name)
    if not path.exists():
        return False
    return '{%- extends "main.html" -%}' in path.read_text()


def test_no_reader_facing_page_replaces_the_theme_template():
    """A page with its own ``template:`` must extend main.html to keep the badge.

    A template that extends ``main.html`` is safe: it inherits the page-type
    badge (DF-11-018, ADR-0136) via ``super()``.  A template that bypasses
    ``main.html`` would silently drop the badge.
    """
    tree = classify_docs_tree(_ROOT)
    replacing = [
        rel
        for rel in tree.pages
        if not is_working_record(rel)
        and (
            template := load_frontmatter(
                _ROOT / "docs" / rel, root=_ROOT
            ).metadata.get("template")
        )
        and not _template_inherits_badge(template)
    ]

    assert tree.pages
    assert replacing == []


def test_home_template_extends_main_html():
    """home.html must extend main.html so the page-type badge is inherited."""
    source = (_OVERRIDES / "home.html").read_text()

    assert '{%- extends "main.html" -%}' in source


def test_home_template_renders_hero_when_meta_present():
    """hero: frontmatter produces a .vultron-hero block.

    Checks that the template source references the expected CSS class and the
    hero key names used by docs/index.md.  Full rendering is not attempted
    because MkDocs' Jinja2 filters (``url``, ``script_tag``, …) are not
    available outside a live build.
    """
    source = (_OVERRIDES / "home.html").read_text()

    assert "vultron-hero" in source
    assert 'h.get("title")' in source or "h['title']" in source
    assert 'h.get("tagline")' in source or "h['tagline']" in source
    assert 'h.get("buttons")' in source or "h['buttons']" in source


def test_home_template_renders_nothing_extra_when_no_hero():
    """hero block is guarded so pages without hero: frontmatter stay unchanged."""
    source = (_OVERRIDES / "home.html").read_text()

    # The hero block must be inside a conditional.
    hero_block_start = source.find("vultron-hero")
    assert hero_block_start != -1, "vultron-hero not found in template"

    # The conditional guard `{%- if h %}` must appear before the hero block.
    guard_marker = "{%- if h %}"
    guard_pos = source.find(guard_marker)
    assert guard_pos != -1, (
        f"{guard_marker!r} not found — hero block is not guarded"
    )
    assert guard_pos < hero_block_start, (
        "hero guard must precede the hero block"
    )


def test_home_template_omits_image_when_absent():
    """The image element is inside a conditional so it renders only when present."""
    source = (_OVERRIDES / "home.html").read_text()

    # The <img> tag must be inside an `if` that checks for the image key.
    img_pos = source.find("<img")
    assert img_pos != -1, (
        "<img not found — image element missing from template"
    )

    image_guard = source.find('h.get("image")', 0, img_pos)
    assert image_guard != -1, (
        'h.get("image") guard must appear before the <img> element'
    )


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
