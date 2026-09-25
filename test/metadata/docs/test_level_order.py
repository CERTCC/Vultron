"""Tests for the check that no ``docs/`` page depends above its own level.

Requirements: DF-11-002 (the rule), DF-11-003/DF-11-012 (working record is
unleveled), DF-11-010 (fragments take their hosts' levels), DF-09-009 (an empty
target set fails); findings are attributed per MS-17-001. The scanner, the
``introduces:`` declarations and the baseline have their own test modules.
"""

from __future__ import annotations

import re

import pytest
import yaml

from test.metadata.docs._level_tree import (
    GLOSSARY,
    VIOLATING,
    assert_passes,
    failures,
    make_repo,
    leveled_page,
)
from vultron.metadata.base import repo_root
from vultron.metadata.docs import level_order
from vultron.metadata.docs.level_order import check_level_order, main
from vultron.metadata.file_loading import MetadataLoadError

# ---------------------------------------------------------------------------
# The rule (AC-1, AC-2, AC-3, AC-6a)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestRule:
    def test_compliant_page_passes(self, tmp_path):
        """A page using no higher-level concept depends on nothing above it."""
        root = make_repo(
            tmp_path, {"howto/a.md": leveled_page(300, "# A\n\nPlain.\n")}
        )

        result = check_level_order(root, baseline={})

        assert result.leveled_pages == 3
        assert result.introductions == 1
        assert result.baselined == []

    def test_unlinked_upward_dependency_fails_at_its_first_use(self, tmp_path):
        body = "# A\n\nFirst line.\nEach case ledger entry is signed.\n"
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        (failure,) = failures(root)

        # Frontmatter is four lines, so the body's fourth line is line 8.
        assert failure.location == "docs/howto/a.md:8:6"
        assert "docs/topics/ledger.md introduces at level 400" in str(failure)
        assert "this page is at 300" in str(failure)

    def test_link_at_first_use_satisfies_the_rule(self, tmp_path):
        """SG-11: the cross-page concept edge is a hyperlink (AC-2)."""
        body = (
            "# A\n\nEach [case ledger entry](../topics/ledger.md) is signed.\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        assert_passes(root)

    def test_earlier_link_satisfies_the_rule(self, tmp_path):
        body = (
            "# A\n\nRead [the ledger](../topics/ledger.md#entries) first.\n\n"
            "Each case ledger entry is signed.\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        assert_passes(root)

    def test_link_after_first_use_does_not(self, tmp_path):
        """A link below the first use leaves that use a forward reference."""
        body = (
            "# A\n\nEach case ledger entry is signed.\n\n"
            "See [the ledger](../topics/ledger.md).\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        (failure,) = failures(root)
        assert failure.line == 7

    def test_link_later_on_the_same_line_does_not(self, tmp_path):
        """One sentence per line (SG-38) must not let a sentence link late."""
        body = (
            "# A\n\nEach case ledger entry is signed; see "
            "[x](../topics/ledger.md).\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        (failure,) = failures(root)
        assert failure.location == "docs/howto/a.md:7:6"

    def test_link_to_another_page_does_not_satisfy(self, tmp_path):
        body = "# A\n\nEach [case ledger entry](b.md).\n"
        root = make_repo(
            tmp_path,
            {
                "howto/a.md": leveled_page(300, body),
                "howto/b.md": leveled_page(),
            },
        )

        assert len(failures(root)) == 1

    def test_glossary_link_at_first_use_satisfies_the_rule(self, tmp_path):
        """SG-11 names the glossary entry as a canonical introduction too."""
        body = (
            "# A\n\nEach [case ledger entry](../reference/glossary.md#l) "
            "is signed.\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        assert_passes(root)

    def test_glossary_link_elsewhere_does_not(self, tmp_path):
        """Only the introducer's link reaches forward; a glossary link names
        the one term it wraps."""
        body = (
            "# A\n\nSee [the glossary](../reference/glossary.md).\n"
            "Each case ledger entry is signed.\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        assert len(failures(root)) == 1

    @pytest.mark.parametrize(
        "body",
        [
            "Each [case ledger entry][cle] is signed.\n\n"
            "[cle]: ../topics/ledger.md\n",
            "Each [case ledger entry][] is signed.\n\n"
            "[Case Ledger Entry]: ../topics/ledger.md\n",
            "Each [case ledger\nentry](../topics/ledger.md) is signed.\n",
            'Each <a href="../topics/ledger.md">case ledger entry</a>.\n',
        ],
        ids=["reference", "collapsed-reference", "wrapped-text", "anchor"],
    )
    def test_every_link_form_satisfies_the_rule(self, tmp_path, body):
        root = make_repo(
            tmp_path, {"howto/a.md": leveled_page(300, "# A\n\n" + body)}
        )

        assert_passes(root)

    def test_reference_definition_alone_is_not_a_link(self, tmp_path):
        """An unused definition links nothing, however early it appears."""
        body = (
            "# A\n\n[cle]: ../topics/ledger.md\n\n"
            "Each case ledger entry is signed.\n"
        )
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        assert len(failures(root)) == 1

    def test_hyphenated_and_wrapped_uses_are_found(self, tmp_path):
        body = "# A\n\nEach case-ledger\nentry is signed.\n"
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(300, body)})

        (failure,) = failures(root)

        assert failure.location == "docs/howto/a.md:7:6"
        assert 'uses "case-ledger entry"' in failure.detail

    @pytest.mark.parametrize("level", [400, 500])
    def test_same_or_higher_level_page_is_compliant(self, tmp_path, level):
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = make_repo(tmp_path, {"howto/a.md": leveled_page(level, body)})

        assert_passes(root)

    def test_comparison_is_site_wide_not_per_audience(self, tmp_path):
        """One ladder: a cross-audience dependency is still ordered (AC-6a)."""
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = make_repo(
            tmp_path,
            {
                "howto/a.md": leveled_page(
                    300, body, audience="[process-researcher]"
                )
            },
        )

        assert len(failures(root)) == 1

    def test_every_violation_is_reported(self, tmp_path):
        body = "# A\n\nEach case ledger entry is signed.\n"
        root = make_repo(
            tmp_path,
            {
                "howto/a.md": leveled_page(300, body),
                "howto/b.md": leveled_page(200, body),
            },
        )

        assert {f.path for f in failures(root)} == {
            "docs/howto/a.md",
            "docs/howto/b.md",
        }

    def test_glossary_defines_its_terms_and_is_not_scanned(self, tmp_path):
        """The registry at 300 lists a 400-level term without depending on it."""
        root = make_repo(tmp_path, {})

        assert_passes(root)


# ---------------------------------------------------------------------------
# Skipped pages and fragments (AC-6, DF-11-010)
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-002")
class TestTargetSet:
    def test_working_record_page_is_skipped_not_level_zero(self, tmp_path):
        """A level-0 reading would flag this page; it carries no level."""
        body = "# ADR\n\nEach case ledger entry is signed.\n"
        root = make_repo(
            tmp_path,
            {
                "adr/0001-x.md": leveled_page(
                    None, body, audience="[project-contributor]"
                )
            },
        )

        result = check_level_order(root, baseline={})

        assert result.unleveled_pages == 1
        assert result.leveled_pages == 2

    def test_undeclared_page_is_skipped(self, tmp_path):
        body = "---\ntitle: T\n---\nEach case ledger entry is signed.\n"
        root = make_repo(tmp_path, {"howto/a.md": body})

        assert check_level_order(root, baseline={}).unleveled_pages == 1

    def test_fragment_included_by_a_fragment_takes_the_outer_hosts_level(
        self, tmp_path
    ):
        root = make_repo(
            tmp_path,
            {
                "howto/_outer.md": '{% include-markdown "./_inner.md" %}\n',
                "howto/_inner.md": "Each case ledger entry is signed.\n",
                "howto/low.md": leveled_page(
                    200, '{% include-markdown "./_outer.md" %}\n'
                ),
            },
            nav=["howto/low.md", "topics/ledger.md"],
        )

        (failure,) = failures(root)

        assert failure.location == "docs/howto/_inner.md:1:6"
        assert "lowest host (howto/low.md) is at 200" in str(failure)

    def test_link_in_an_included_fragment_counts_for_its_host(self, tmp_path):
        """The rendered page links out where the fragment is included."""
        host = (
            '# H\n\n{% include-markdown "./_see.md" %}\n\n'
            "Each case ledger entry is signed.\n"
        )
        root = make_repo(
            tmp_path,
            {
                "howto/_see.md": "See [the ledger](../topics/ledger.md).\n",
                "howto/low.md": leveled_page(300, host),
            },
            nav=["howto/low.md", "topics/ledger.md"],
        )

        assert_passes(root)

    def test_link_in_a_fragment_included_below_the_use_does_not(
        self, tmp_path
    ):
        host = (
            "# H\n\nEach case ledger entry is signed.\n\n"
            '{% include-markdown "./_see.md" %}\n'
        )
        root = make_repo(
            tmp_path,
            {
                "howto/_see.md": "See [the ledger](../topics/ledger.md).\n",
                "howto/low.md": leveled_page(300, host),
            },
            nav=["howto/low.md", "topics/ledger.md"],
        )

        (failure,) = failures(root)
        assert failure.location == "docs/howto/low.md:7:6"

    def test_auto_appended_abbreviations_are_not_scanned(self, tmp_path):
        """No leveled page hosts it: its entries become tooltips, not prose."""
        root = make_repo(tmp_path, {"_abbr.md": "*[CLE]: Case Ledger Entry\n"})
        config = root / "mkdocs.yml"
        config.write_text(
            config.read_text()
            + yaml.safe_dump(
                {
                    "markdown_extensions": [
                        {
                            "pymdownx.snippets": {
                                "auto_append": ["docs/_abbr.md"]
                            }
                        }
                    ]
                }
            )
        )

        assert_passes(root)

    def test_fragment_is_checked_at_its_lowest_hosts_level(self, tmp_path):
        host = '# H\n\n{% include-markdown "./_frag.md" %}\n'
        root = make_repo(
            tmp_path,
            {
                "howto/_frag.md": "Each case ledger entry is signed.\n",
                "howto/low.md": leveled_page(200, host),
                "howto/high.md": leveled_page(400, host),
            },
            nav=["howto/low.md", "howto/high.md", "topics/ledger.md"],
        )

        (failure,) = failures(root)

        assert failure.location == "docs/howto/_frag.md:1:6"
        assert "lowest host (howto/low.md) is at 200" in str(failure)

    @pytest.mark.parametrize(
        "body",
        [
            "```text\ncase ledger entry\n```\n",
            "~~~~\ncase ledger entry\n~~~~\n",
            "Use `case ledger entry` here.\n",
            "<!-- case ledger entry -->\n",
            "[x](https://example.org/case-ledger-entry)\n",
            "[x]: ../case ledger entry.md\n",
            "<code>case ledger entry</code>\n",
            "!!! note\n\n    ```text\n    case ledger entry\n    ```\n",
        ],
        ids=[
            "backtick-fence",
            "tilde-fence",
            "inline",
            "comment",
            "url",
            "ref",
            "code-element",
            "admonition-fence",
        ],
    )
    def test_non_prose_is_not_a_use(self, tmp_path, body):
        root = make_repo(
            tmp_path, {"howto/a.md": leveled_page(300, "# A\n\n" + body)}
        )

        assert_passes(root)

    def test_empty_target_set_fails(self, tmp_path):
        """DF-09-009: resolving no leveled page is a failure (AC-5)."""
        (tmp_path / "mkdocs.yml").write_text("nav: []\n")
        glossary = tmp_path / "docs" / "reference" / "glossary.md"
        glossary.parent.mkdir(parents=True)
        glossary.write_text(GLOSSARY.replace("level: 300", ""))

        with pytest.raises(MetadataLoadError, match="no leveled page"):
            check_level_order(tmp_path, baseline={})

    def test_no_introduced_concept_fails(self, tmp_path):
        """A tree declaring no concept would pass vacuously (DF-09-009)."""
        root = make_repo(tmp_path, {"topics/ledger.md": leveled_page(400)})

        with pytest.raises(MetadataLoadError, match="no page declares"):
            check_level_order(root, baseline={})

    def test_missing_glossary_fails(self, tmp_path):
        root = make_repo(tmp_path, {})
        (root / "docs" / "reference" / "glossary.md").unlink()

        with pytest.raises(MetadataLoadError, match="glossary.*is missing"):
            check_level_order(root, baseline={})


# ---------------------------------------------------------------------------
# Entry points and the real tree
# ---------------------------------------------------------------------------


def test_cli_reports_failures_without_a_traceback(
    tmp_path, monkeypatch, capsys
):
    root = make_repo(tmp_path, {"howto/a.md": VIOLATING})
    monkeypatch.setattr(level_order, "_find_repo_root", lambda: root)
    monkeypatch.setattr(level_order, "BASELINE_PATH", tmp_path / "none.txt")

    with pytest.raises(SystemExit) as info:
        main([])

    assert info.value.code == 1
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] 1 docs level-order finding(s)")
    assert "docs/howto/a.md:7:6" in err


@pytest.mark.parametrize(
    "changed",
    [
        "docs/tutorials/deep/page.md",
        "mkdocs.yml",
        "vultron/metadata/docs/level_order.py",
        "vultron/metadata/docs/level_order_baseline.txt",
        "vultron/metadata/docs/level_baseline.py",
        "vultron/metadata/docs/concept_scan.py",
        "vultron/metadata/docs/concept_registry.py",
        "vultron/metadata/docs/baseline_file.py",
        "vultron/metadata/docs/page_frontmatter.py",
        "vultron/metadata/docs/page_schema.py",
        "vultron/metadata/docs/glossary_index.py",
        "vultron/metadata/base.py",
        "vultron/metadata/markdown_tables.py",
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
    hook = hooks["docs-level-order"]

    assert hook["entry"] == "uv run docs-level-order"
    assert hook["pass_filenames"] is False
    assert re.search(hook["files"], changed)


@pytest.mark.spec("DF-11-002")
def test_the_committed_docs_tree_passes():
    """The gate CI enforces, independent of whether the hook ran locally."""
    result = check_level_order()

    assert result.leveled_pages > 0
    assert result.introductions > 0
