"""Tests for vultron.metadata.docs.links (issue #3634, DOCBW-03-007).

When ``docs/ns/`` moved to ``draft_docs``, the What's New page kept linking to
``../../ns/`` — well-formed, correctly relative, and 404ing — and every gate
passed (#3574). These tests pin the check that resolves each reference against
the built tree.

The load-bearing cases close the ways it could pass while checking nothing: an
absent, empty, or HTML-less ``site/`` raises rather than reporting clean, and a
page no other page links to is still read (a crawl from ``index.html`` would
never reach it).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.docs.links import (
    DeadReference,
    main,
    scan_site,
    site_base_path,
)

SITE_URL = "https://example.org/Vultron/"


def _build_tree(
    root: Path, pages: dict[str, str], site_url: str | None = SITE_URL
) -> None:
    """Create a synthetic checkout: ``mkdocs.yml`` plus a built ``site/``.

    Args:
        pages: ``site/``-relative path to file body. Non-HTML entries stand in
            for assets.
        site_url: Written to ``mkdocs.yml``; ``None`` omits the key.
    """
    config = f"site_url: '{site_url}'\n" if site_url else "site_name: x\n"
    (root / "mkdocs.yml").write_text(config, encoding="utf-8")
    for rel, body in pages.items():
        path = root / "site" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def _page(*hrefs: str) -> str:
    return "".join(f'<a href="{h}">x</a>\n' for h in hrefs)


CLEAN = {
    "index.html": _page(
        "guide/",
        ".",
        "#top",
        "",
        "https://example.com/elsewhere",
        "//cdn.example.com/lib.js",
    )
    + "<link href=\"assets/site.css\">\n<img src='assets/logo.png'>\n",
    "guide/index.html": _page("../", "../index.html", "../assets/site.css"),
    "assets/site.css": "body {}",
    "assets/logo.png": "png",
}


def _dead(root: Path) -> list[DeadReference]:
    return scan_site(root).dead


# --- clean and empty trees ------------------------------------------------


@pytest.mark.spec("DOCBW-03-007")
def test_clean_tree_has_no_dead_references(tmp_path):
    _build_tree(tmp_path, CLEAN)
    scan = scan_site(tmp_path)
    assert scan.dead == []
    assert scan.pages == 2
    # Fragment-only, empty, and external references are not counted.
    assert scan.references == 7


@pytest.mark.spec("DF-09-009")
def test_absent_site_raises(tmp_path):
    (tmp_path / "mkdocs.yml").write_text(f"site_url: '{SITE_URL}'\n", "utf-8")
    with pytest.raises(FileNotFoundError, match="absent or empty"):
        scan_site(tmp_path)


@pytest.mark.spec("DF-09-009")
def test_empty_site_raises(tmp_path):
    _build_tree(tmp_path, {})
    (tmp_path / "site").mkdir()
    with pytest.raises(FileNotFoundError, match="absent or empty"):
        scan_site(tmp_path)


@pytest.mark.spec("DF-09-009")
def test_site_without_html_raises(tmp_path):
    _build_tree(tmp_path, {"assets/site.css": "body {}"})
    with pytest.raises(FileNotFoundError, match="no HTML pages"):
        scan_site(tmp_path)


# --- the failures the gate exists for ------------------------------------


@pytest.mark.spec("DOCBW-03-007")
def test_reference_to_withheld_page_is_dead(tmp_path):
    """The #3574 shape: a correct-looking relative link to an unbuilt page."""
    _build_tree(
        tmp_path,
        {**CLEAN, "about/whats-new/index.html": _page("../../ns/")},
    )
    assert _dead(tmp_path) == [
        DeadReference(page="about/whats-new/index.html", reference="../../ns/")
    ]


@pytest.mark.spec("DOCBW-03-007")
def test_reference_ending_in_md_is_dead(tmp_path):
    _build_tree(
        tmp_path,
        {**CLEAN, "guide/index.html": _page("../reference/topic.md")},
    )
    assert [d.reference for d in _dead(tmp_path)] == ["../reference/topic.md"]


@pytest.mark.spec("DOCBW-03-007")
def test_dead_reference_on_unreachable_page_is_found(tmp_path):
    """Anti-crawl: no page links to ``orphan/``, and its links are still read."""
    _build_tree(tmp_path, {**CLEAN, "orphan/index.html": _page("../gone/")})
    assert _dead(tmp_path) == [
        DeadReference(page="orphan/index.html", reference="../gone/")
    ]


@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize(
    "href",
    [
        "missing/",  # a directory the build did not produce
        "assets/",  # a directory with no index.html
        "../../outside.html",  # climbs out of site/
        "/Other/index.html",  # root-absolute outside the site's base path
        "/Vultron/missing.css",  # root-absolute under it, but unbuilt
    ],
)
def test_unresolvable_reference_is_dead(tmp_path, href: str):
    _build_tree(tmp_path, {**CLEAN, "index.html": _page(href)})
    assert [d.reference for d in _dead(tmp_path)] == [href]


def test_dead_references_are_sorted_by_page_then_reference(tmp_path):
    _build_tree(
        tmp_path,
        {
            **CLEAN,
            "b/index.html": _page("z/", "a/"),
            "a/index.html": _page("q/"),
        },
    )
    assert [(d.page, d.reference) for d in _dead(tmp_path)] == [
        ("a/index.html", "q/"),
        ("b/index.html", "a/"),
        ("b/index.html", "z/"),
    ]


# --- edge cases measured on the real tree: each resolves -----------------


@pytest.mark.spec("DOCBW-03-007")
def test_root_absolute_reference_under_site_url_resolves(tmp_path):
    """``404.html`` writes its references under ``site_url``'s path."""
    _build_tree(
        tmp_path,
        {
            **CLEAN,
            "404.html": _page(
                "/Vultron/assets/site.css", "/Vultron/", "/Vultron"
            ),
        },
    )
    assert _dead(tmp_path) == []


@pytest.mark.spec("DOCBW-03-007")
def test_entity_obfuscated_mailto_is_not_an_internal_reference(tmp_path):
    """Material encodes ``mailto:`` as character references."""
    obfuscated = "".join(f"&#{ord(c)};" for c in "mailto:a@example.org")
    _build_tree(tmp_path, {**CLEAN, "guide/index.html": _page(obfuscated)})
    scan = scan_site(tmp_path)
    assert scan.dead == []
    assert scan.references == 4  # CLEAN's index.html refs only


@pytest.mark.spec("DOCBW-03-007")
@pytest.mark.parametrize(
    "href",
    [
        "guide/#section",
        "guide/?q=1",
        "guide/?q=1#section",
        "guide/index.html#x",
    ],
)
def test_fragment_and_query_are_stripped_before_resolution(tmp_path, href):
    _build_tree(tmp_path, {**CLEAN, "orphan/index.html": _page(f"../{href}")})
    assert _dead(tmp_path) == []


def test_percent_encoded_and_entity_escaped_paths_resolve(tmp_path):
    _build_tree(
        tmp_path,
        {
            **CLEAN,
            "a b/index.html": "",
            "orphan/index.html": _page("../a%20b/", "../guide/?x=1&amp;y=2"),
        },
    )
    assert _dead(tmp_path) == []


def test_data_attribute_is_not_a_reference(tmp_path):
    _build_tree(
        tmp_path,
        {**CLEAN, "orphan/index.html": '<div data-href="nowhere/"></div>'},
    )
    assert _dead(tmp_path) == []


@pytest.mark.parametrize(
    "site_url, expected",
    [(SITE_URL, "/Vultron/"), ("https://example.org", "/"), (None, "/")],
)
def test_site_base_path(tmp_path, site_url, expected):
    _build_tree(tmp_path, {}, site_url=site_url)
    assert site_base_path(tmp_path) == expected


def test_without_site_url_root_absolute_resolves_from_site_root(tmp_path):
    _build_tree(
        tmp_path,
        {**CLEAN, "404.html": _page("/assets/site.css")},
        site_url=None,
    )
    assert _dead(tmp_path) == []


# --- CLI -----------------------------------------------------------------


def test_main_exits_zero_and_reports_coverage_on_clean_tree(tmp_path, capsys):
    _build_tree(tmp_path, CLEAN)
    main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert "7 internal references across 2 pages" in out


@pytest.mark.spec("DOCBW-03-007")
def test_main_reports_each_dead_reference_and_exits_nonzero(tmp_path, capsys):
    _build_tree(tmp_path, {**CLEAN, "orphan/index.html": _page("../gone/")})
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "orphan/index.html: ../gone/" in err
    assert "1 of 8 internal reference(s)" in err


@pytest.mark.spec("DF-09-009")
def test_main_exits_nonzero_when_no_internal_reference_was_checked(
    tmp_path, capsys
):
    """Only external and fragment links: a pass would have resolved nothing."""
    _build_tree(
        tmp_path, {"index.html": _page("https://example.com/", "#top")}
    )
    assert scan_site(tmp_path).references == 0
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    assert "no internal references" in capsys.readouterr().err


@pytest.mark.spec("DF-09-009")
def test_main_exits_nonzero_without_a_built_site(tmp_path, capsys):
    (tmp_path / "mkdocs.yml").write_text(f"site_url: '{SITE_URL}'\n", "utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path)])
    assert exc.value.code == 1
    assert "run 'uv run mkdocs build' first" in capsys.readouterr().err
