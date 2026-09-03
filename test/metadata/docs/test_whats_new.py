"""Tests for vultron.metadata.docs.whats_new (issue #3144).

The "What's New" page auto-generates a list of recently-added docs pages.
The original implementation emitted root-absolute links (``/reference/...``),
which drop the ``/Vultron/`` base-path prefix on the deployed site and 404.

markdown-exec output is NOT processed by MkDocs' relative-link treeprocessor,
so links must already be the final built URL. These tests pin the renderer to
directory-style *relative* URLs (``../../reference/quick_reference/``), which
resolve correctly both on the deployed sub-path and under ``mkdocs serve``.
"""

from vultron.metadata.docs.whats_new import (
    NO_PAGES_MESSAGE,
    keep_existing_pages,
    render_recent_pages,
)


def test_render_recent_pages_emits_relative_dir_url_not_root_absolute():
    """Links must be page-relative directory URLs, never root-absolute (#3144)."""
    out = render_recent_pages(["docs/reference/quick_reference.md"])
    # The regression: no leading-slash / root-absolute href.
    assert "](/" not in out
    # markdown-exec output is not rewritten by MkDocs, so the link must already
    # be the final directory-style URL, relative to docs/about/whats_new.md.
    assert "](../../reference/quick_reference/)" in out
    # A .md source link would be emitted verbatim and 404 — never emit one.
    assert ".md)" not in out


def test_render_recent_pages_links_to_adr_page():
    out = render_recent_pages(["docs/adr/0019-case-log.md"])
    assert "](../../adr/0019-case-log/)" in out


def test_render_recent_pages_index_page_collapses_to_directory():
    out = render_recent_pages(["docs/reference/index.md"])
    assert "](../../reference/)" in out


def test_render_recent_pages_readme_collapses_to_directory():
    """MkDocs serves README.md as the directory index, like index.md."""
    out = render_recent_pages(["docs/adr/archived/README.md"])
    assert "](../../adr/archived/)" in out


def test_render_recent_pages_excludes_draft_pages():
    """draft-*.md are dropped by mkdocs draft_docs and would 404 (#3144)."""
    out = render_recent_pages(
        [
            "docs/reference/draft-vultron-replication-spec.md",
            "docs/reference/quick_reference.md",
        ]
    )
    assert "draft-vultron-replication-spec" not in out
    assert "quick_reference" in out


def test_render_recent_pages_keeps_undrafted_exception():
    """The one file negated in draft_docs IS built, so keep it."""
    out = render_recent_pages(["docs/reference/draft-vultron-spec.md"])
    assert "](../../reference/draft-vultron-spec/)" in out


def test_render_recent_pages_docs_root_index_does_not_crash():
    """docs/index.md collapses to "" — relpath must not raise (#3144)."""
    out = render_recent_pages(["docs/index.md"])
    # From docs/about/whats_new.md up to the docs root is ../../ (two levels).
    assert "](../../)" in out
    assert "[Home]" in out


def test_render_recent_pages_index_title_uses_directory_name():
    """Index/README pages are titled after their directory, not "Index"/"Readme"."""
    out = render_recent_pages(
        ["docs/reference/index.md", "docs/adr/archived/README.md"]
    )
    assert "[Reference]" in out
    assert "[Archived]" in out
    assert "[Index]" not in out
    assert "[Readme]" not in out


def test_render_recent_pages_self_link_is_relative():
    out = render_recent_pages(["docs/about/whats_new.md"])
    assert "](./)" in out


def test_render_recent_pages_humanizes_title():
    out = render_recent_pages(["docs/reference/quick_reference.md"])
    assert "[Quick Reference]" in out


def test_render_recent_pages_empty_returns_placeholder():
    assert render_recent_pages([]) == NO_PAGES_MESSAGE


def test_render_recent_pages_filters_non_navigable():
    """Underscore-prefixed and includes/ paths are excluded from nav."""
    out = render_recent_pages(
        [
            "docs/howto/activitypub/activities/_create_report.md",
            "docs/includes/curr_ver.md",
            "docs/reference/quick_reference.md",
        ]
    )
    assert "_create_report" not in out
    assert "curr_ver" not in out
    assert "quick_reference" in out


def test_keep_existing_pages_drops_renamed_or_deleted(tmp_path):
    """git reports the pre-rename path; if the file is gone its link 404s (#3144)."""
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0019-new-name.md").write_text("x")

    kept = keep_existing_pages(
        [
            "docs/adr/0019-old-name.md",  # renamed away — must be dropped
            "docs/adr/0019-new-name.md",  # exists — kept
            "",  # blank line from git output — ignored
        ],
        repo_root=tmp_path,
    )

    assert kept == ["docs/adr/0019-new-name.md"]


def test_render_recent_pages_sorts_and_dedups():
    out = render_recent_pages(
        [
            "docs/reference/b.md",
            "docs/reference/a.md",
            "docs/reference/a.md",
        ]
    )
    assert out.count("](../../reference/a/)") == 1
    assert out.index("reference/a/") < out.index("reference/b/")
