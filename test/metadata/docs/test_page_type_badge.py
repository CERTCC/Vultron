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


@pytest.mark.spec("DF-11-037")
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


@pytest.mark.spec("DF-11-037")
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


_EXTENDS_MAIN = re.compile(r"""\{%-?\s*extends\s+["']main\.html["']\s*-?%\}""")


def _template_inherits_badge(template_name: str) -> bool:
    """True when the named override template extends main.html.

    A template that extends ``main.html`` inherits the page-type badge via
    ``super()`` and is safe for reader-facing pages.  A template that does
    not extend ``main.html`` bypasses the badge's content block.
    """
    path = _OVERRIDES / template_name
    return path.is_file() and bool(_EXTENDS_MAIN.search(path.read_text()))


def _page_template(rel: str) -> str | None:
    """The ``template:`` a docs page declares, or ``None`` when it has none."""
    meta = load_frontmatter(_ROOT / "docs" / rel, root=_ROOT).metadata
    template = meta.get("template")
    return None if template is None else str(template)


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
        and (template := _page_template(rel)) is not None
        and not _template_inherits_badge(template)
    ]

    assert tree.pages
    assert replacing == []


@pytest.mark.parametrize(
    ("source", "inherits"),
    [
        ('{%- extends "main.html" -%}', True),
        ("{% extends 'main.html' %}", True),
        ('{% extends "base.html" %}', False),
    ],
    ids=["trimmed", "plain", "base"],
)
def test_the_extends_pattern_reads_both_spellings(source, inherits):
    assert bool(_EXTENDS_MAIN.search(source)) is inherits


def test_home_template_extends_main_html():
    """home.html must extend main.html so the page-type badge is inherited."""
    assert _template_inherits_badge("home.html")


_STUB_MAIN = "{% block content %}<article>BODY</article>{% endblock %}"


def _render_home(meta: dict[str, object] | None) -> str:
    """Render home.html over a stub main.html, as MkDocs would without the theme.

    MkDocs' ``url`` filter makes a path relative to the page; the stub
    prefixes ``REL/`` so a test can see the filter ran. MkDocs builds its
    environment without autoescape, so neither does this one.
    """
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.DictLoader({"main.html": _STUB_MAIN}),
                jinja2.FileSystemLoader(_OVERRIDES),
            ]
        ),
        undefined=jinja2.StrictUndefined,
        autoescape=False,  # noqa: S701 -- mirror MkDocs; home.html escapes
    )
    env.filters["url"] = lambda value: (
        value if str(value).startswith("#") else f"REL/{value}"
    )
    return env.get_template("home.html").render(page=_Page(meta))


_HERO: dict[str, object] = {
    "title": "Hero <title>",
    "tagline": 'A "quoted" tagline',
    "buttons": [
        {"text": "First", "url": "#anchor"},
        {"text": "Second", "url": "reference/x/"},
    ],
}


def test_home_template_renders_the_hero_before_the_content():
    html = _render_home({"hero": _HERO})

    assert html.index('class="vultron-hero"') < html.index("<article>")
    assert "Hero &lt;title&gt;" in html
    assert "A &#34;quoted&#34; tagline" in html


def test_home_template_marks_only_the_first_button_primary():
    html = _render_home({"hero": _HERO})

    assert re.search(
        r'href="#anchor"\s+class="md-button md-button--primary"\s*>First<',
        html,
    )
    assert re.search(
        r'href="REL/reference/x/"\s+class="md-button"\s*>Second<', html
    )


@pytest.mark.parametrize(
    "meta",
    [{}, {"title": "No hero"}, None],
    ids=["empty", "no-hero", "no-meta"],
)
def test_home_template_renders_nothing_extra_when_no_hero(meta):
    html = _render_home(meta)

    assert "vultron-hero" not in html
    assert "<article>BODY</article>" in html


def test_home_template_omits_image_when_absent():
    assert "<img" not in _render_home({"hero": _HERO})


def test_home_template_renders_an_image_with_its_alt_text():
    html = _render_home(
        {
            "hero": {
                **_HERO,
                "image": "assets/x.svg",
                "image_alt": "A <diagram>",
            }
        }
    )

    assert 'src="REL/assets/x.svg"' in html
    assert 'alt="A &lt;diagram&gt;"' in html


def test_every_hero_image_has_alt_text():
    """A hero ``image:`` without non-empty ``image_alt:`` is inaccessible."""
    tree = classify_docs_tree(_ROOT)
    missing = []
    for rel in tree.pages:
        hero = load_frontmatter(_ROOT / "docs" / rel, root=_ROOT).metadata.get(
            "hero"
        )
        if (
            isinstance(hero, dict)
            and hero.get("image")
            and not str(hero.get("image_alt") or "").strip()
        ):
            missing.append(rel)

    assert tree.pages
    assert missing == []


_HAND_BADGE = re.compile(
    r"""class=["'][^"']*\bpage-type\b|\{[^}]*\.page-type\b"""
)


@pytest.mark.spec("DF-11-038")
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
@pytest.mark.spec("DF-11-038")
def test_the_hand_badge_pattern_catches_both_spellings(text):
    assert _HAND_BADGE.search(text)
