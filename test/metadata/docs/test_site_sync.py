"""Tests for the generated docs-site artifacts (``uv run docs-site``).

Requirements: DF-11-005 (landing pages generated and check gated; every
group-opening index declares its shape; routing pages link every member),
DF-11-008 (the coverage matrix), DF-11-011 (the stakeholder-type fragment),
DF-09-009 (an empty target set fails), DF-11-004 (a level is never rendered).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vultron.metadata.base import repo_root
from vultron.metadata.docs import page_schema, site_sync
from vultron.metadata.docs.coverage_matrix import (
    MATRIX_PATH,
    ROWS,
    measure_coverage,
    render_matrix,
)
from vultron.metadata.docs.landing_pages import (
    BEGIN_MARKER,
    CONTENTS_KEY,
    END_MARKER,
    Entry,
    discover_landing_pages,
    discover_section_indexes,
    render_listing,
    routing_faults,
    sort_entries,
    splice_listing,
)
from vultron.metadata.docs.page_schema import (
    ALL_STAKEHOLDERS,
    AUDIENCE_DESCRIPTIONS,
    LEVELS,
    AudienceDescription,
    StakeholderType,
)
from vultron.metadata.docs.stakeholder_fragment import (
    FRAGMENT_PATH,
    render_fragment,
)
from vultron.metadata.file_loading import MetadataLoadError, MetadataLoadErrors

_LANDING = (
    f"---\n{CONTENTS_KEY}: generated\n---\n\n"
    "# Guides\n\nHand-written framing.\n\n"
    f"{BEGIN_MARKER}\n\n{END_MARKER}\n\nHand-written see-also.\n"
)


def _index(contents: str | None, body: str = "# Sub\n") -> str:
    """A group-opening ``index.md`` declaring *contents*, or nothing."""
    head = f"---\n{CONTENTS_KEY}: {contents}\n---\n\n" if contents else ""
    return head + body


#: A nested generated index: the same markers, one level down.
_SUB_LANDING = _index(
    "generated", f"# Sub\n\n{BEGIN_MARKER}\n\n{END_MARKER}\n"
)


def _page(
    title: str,
    description: str | None = None,
    level: int | None = None,
    stakeholder_type: str | None = None,
) -> str:
    keys = []
    if description is not None:
        keys.append(f"description: {description}")
    if level is not None:
        keys.append(f"level: {level}")
    if stakeholder_type is not None:
        keys.append(f"stakeholder_type: {stakeholder_type}")
    head = "---\n" + "\n".join(keys) + "\n---\n\n" if keys else ""
    return f"{head}# {title}\n"


def _repo(tmp_path: Path, files: dict[str, str], nav: list[object]) -> Path:
    (tmp_path / "mkdocs.yml").write_text(yaml.safe_dump({"nav": nav}))
    for rel, text in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _guides_repo(tmp_path: Path, **pages: str) -> Path:
    files = {"docs/guides/index.md": _LANDING}
    files.update({f"docs/guides/{k}.md": v for k, v in pages.items()})
    nav: list[object] = [
        {"Guides": ["guides/index.md"] + [f"guides/{k}.md" for k in pages]}
    ]
    return _repo(tmp_path, files, nav)


def _e(label: str, level: int | None = None) -> Entry:
    return Entry(label=label, target=f"{label}.md", level=level)


# ---------------------------------------------------------------------------
# Landing pages
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-005")
class TestSortEntries:
    def test_no_levels_keeps_nav_order(self):
        entries = [_e("c"), _e("a"), _e("b")]
        assert [e.label for e in sort_entries(entries)] == ["c", "a", "b"]

    def test_every_level_declared_sorts_by_level(self):
        entries = [_e("c", 300), _e("a", 100), _e("b", 200)]
        assert [e.label for e in sort_entries(entries)] == ["a", "b", "c"]

    def test_equal_levels_keep_nav_order(self):
        entries = [_e("x", 200), _e("y", 100), _e("z", 200)]
        assert [e.label for e in sort_entries(entries)] == ["y", "x", "z"]

    def test_undeclared_entry_travels_with_the_declared_one_before_it(self):
        entries = [_e("lead"), _e("deep", 400), _e("tail"), _e("intro", 100)]
        assert [e.label for e in sort_entries(entries)] == [
            "lead",
            "intro",
            "deep",
            "tail",
        ]


@pytest.mark.spec("DF-11-005")
class TestLandingPageGeneration:
    def test_lists_every_nav_member_with_its_description(self, tmp_path):
        root = _guides_repo(
            tmp_path,
            one=_page("One", description="First  guide,\n  folded."),
            two=_page("Two"),
        )
        (page,) = discover_landing_pages(root)
        assert page.path == "guides/index.md"
        assert render_listing(page) == (
            "- [One](one.md) — First guide, folded.\n- [Two](two.md)"
        )

    def test_orders_by_declared_level(self, tmp_path):
        root = _guides_repo(
            tmp_path,
            deep=_page("Deep", level=300),
            intro=_page("Intro", level=100),
        )
        (page,) = discover_landing_pages(root)
        assert [e.label for e in page.entries] == ["Intro", "Deep"]

    def test_never_renders_a_level(self, tmp_path):
        root = _guides_repo(tmp_path, deep=_page("Deep", level=300))
        (page,) = discover_landing_pages(root)
        assert "300" not in render_listing(page)

    def test_nav_label_wins_over_the_h1(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": _page("Long Page Heading"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", {"Short": "guides/a.md"}]}
        ]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Short](a.md)"

    def test_unlabelled_page_uses_its_frontmatter_title(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": "---\ntitle: Nice Title\n---\n\n# Heading\n",
        }
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/a.md"]}]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Nice Title](a.md)"

    def test_unlabelled_page_h1_skips_comments_and_attr_lists(self, tmp_path):
        text = (
            "---\n# reviewed 2026\ndescription: D.\n---\n\n"
            "```bash\n# install\n```\n\n# Real Heading {#real}\n"
        )
        files = {"docs/guides/index.md": _LANDING, "docs/guides/a.md": text}
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/a.md"]}]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Real Heading](a.md) — D."

    def test_unlabelled_page_h1_skips_a_hash_inside_an_admonition_fence(
        self, tmp_path
    ):
        """A ``# comment`` in a shell block nested under ``!!! note`` is not
        the H1, even though the fence sits four spaces deep (#3685)."""
        text = (
            "---\ndescription: D.\n---\n\n"
            "!!! note\n\n    ```bash\n    # install\n    ```\n\n"
            "# Real Heading\n"
        )
        files = {"docs/guides/index.md": _LANDING, "docs/guides/a.md": text}
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/a.md"]}]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Real Heading](a.md) — D."

    @pytest.mark.parametrize("inner", ["```", "~~~~"])
    def test_unlabelled_page_h1_ignores_a_fence_that_does_not_close(
        self, tmp_path, inner
    ):
        """A shorter run, or the other fence character, inside a longer fence
        is content and does not end the block, so a ``#`` line after it is
        still fenced (#3685)."""
        text = (
            "---\ndescription: D.\n---\n\n"
            f"````markdown\n{inner}\n# Not The Heading\n````\n\n"
            "# Real Heading\n"
        )
        files = {"docs/guides/index.md": _LANDING, "docs/guides/a.md": text}
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/a.md"]}]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Real Heading](a.md) — D."

    def test_non_http_scheme_is_an_external_link(self, tmp_path):
        files = {"docs/guides/index.md": _LANDING}
        nav: list[object] = [
            {"Guides": ["guides/index.md", {"Mail": "mailto:x@example.org"}]}
        ]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Mail](mailto:x@example.org)"

    def test_group_with_an_index_links_to_it(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/sub/index.md": (
                f"---\ndescription: Sub d.\n{CONTENTS_KEY}: routing\n---\n\n"
                "# Sub\n\n[Leaf](leaf.md)\n"
            ),
            "docs/guides/sub/leaf.md": _page("Leaf"),
        }
        nav: list[object] = [
            {
                "Guides": [
                    "guides/index.md",
                    {"Sub": ["guides/sub/index.md", "guides/sub/leaf.md"]},
                ]
            }
        ]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Sub](sub/index.md) — Sub d."

    def test_group_without_an_index_nests_its_members(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/demos/a.md": _page("A demo"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", {"Demos": ["guides/demos/a.md"]}]}
        ]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == (
            "<!-- markdownlint-disable MD007 -->\n"
            "- **Demos**\n    - [A demo](demos/a.md)\n"
            "<!-- markdownlint-enable MD007 -->"
        )

    def test_flat_listing_leaves_md007_on(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        (page,) = discover_landing_pages(root)
        assert "markdownlint" not in render_listing(page)

    def test_link_outside_the_section_is_relative(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/adr/index.md": _page("Decisions"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", {"Decisions": "adr/index.md"}]}
        ]
        (page,) = discover_landing_pages(_repo(tmp_path, files, nav))
        assert render_listing(page) == "- [Decisions](../adr/index.md)"

    def test_section_without_an_index_is_not_a_landing_page(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": _page("A"),
            "docs/about/x.md": _page("X"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", "guides/a.md"]},
            {"About": ["about/x.md"]},
        ]
        pages = discover_landing_pages(_repo(tmp_path, files, nav))
        assert [p.path for p in pages] == ["guides/index.md"]

    def test_blank_description_fails(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A", description="''"))
        with pytest.raises(MetadataLoadError, match="non-blank string"):
            discover_landing_pages(root)

    def test_listed_page_that_does_not_exist_fails(self, tmp_path):
        files = {"docs/guides/index.md": _LANDING}
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/gone.md"]}]
        with pytest.raises(MetadataLoadError, match="does not exist"):
            discover_landing_pages(_repo(tmp_path, files, nav))


@pytest.mark.spec("DF-09-009")
class TestEmptyTargetSet:
    def test_nav_with_no_landing_page_fails(self, tmp_path):
        files = {"docs/about/x.md": _page("X")}
        nav: list[object] = [{"About": ["about/x.md"]}]
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            discover_landing_pages(_repo(tmp_path, files, nav))

    def test_empty_nav_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            discover_landing_pages(_repo(tmp_path, {}, []))

    def test_landing_page_with_nothing_to_list_fails(self, tmp_path):
        files = {"docs/guides/index.md": _LANDING}
        nav: list[object] = [{"Guides": ["guides/index.md"]}]
        with pytest.raises(MetadataLoadError, match="lists nothing else"):
            discover_landing_pages(_repo(tmp_path, files, nav))

    def test_matrix_over_an_empty_tree_fails(self, tmp_path):
        (tmp_path / "docs").mkdir()
        _repo(tmp_path, {}, [])
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            measure_coverage(tmp_path)


@pytest.mark.spec("DF-11-005")
class TestProsePreservation:
    def test_prose_outside_the_markers_survives(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        (page,) = discover_landing_pages(root)
        stale = _LANDING.replace(
            f"{BEGIN_MARKER}\n\n", f"{BEGIN_MARKER}\n\n- [Old](old.md)\n"
        )
        result = splice_listing(stale, page)
        assert result.startswith(
            f"---\n{CONTENTS_KEY}: generated\n---\n\n"
            "# Guides\n\nHand-written framing.\n\n"
        )
        assert result.endswith(f"{END_MARKER}\n\nHand-written see-also.\n")
        assert "old.md" not in result
        assert "- [A](a.md)" in result

    def test_regenerating_is_idempotent(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        (page,) = discover_landing_pages(root)
        once = splice_listing(_LANDING, page)
        assert splice_listing(once, page) == once

    def test_missing_markers_fail_rather_than_append(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        (page,) = discover_landing_pages(root)
        with pytest.raises(ValueError, match="generated-block begin"):
            splice_listing("# Guides\n\n- [A](a.md)\n", page)


@pytest.mark.spec("DF-11-005")
class TestSectionIndexDecisions:
    """Every ``index.md`` that opens a nav group declares how it carries its
    contents; the three shapes are handled as declared (#3617)."""

    def _nested_repo(self, tmp_path, sub_index: str, **extra: str) -> Path:
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": _page("A"),
            "docs/guides/sub/index.md": sub_index,
            "docs/guides/sub/leaf.md": _page("Leaf", description="L."),
            "docs/guides/sub/other.md": _page("Other"),
        }
        files.update(extra)
        nav: list[object] = [
            {
                "Guides": [
                    "guides/index.md",
                    "guides/a.md",
                    {
                        "Sub": [
                            "guides/sub/index.md",
                            "guides/sub/leaf.md",
                            "guides/sub/other.md",
                        ]
                    },
                ]
            }
        ]
        return _repo(tmp_path, files, nav)

    def test_nested_generated_index_is_a_landing_page(self, tmp_path):
        root = self._nested_repo(tmp_path, _SUB_LANDING)
        pages = {p.path: p for p in discover_landing_pages(root)}
        assert set(pages) == {"guides/index.md", "guides/sub/index.md"}
        assert render_listing(pages["guides/sub/index.md"]) == (
            "- [Leaf](leaf.md) — L.\n- [Other](other.md)"
        )

    def test_undeclared_group_index_names_the_page(self, tmp_path):
        root = self._nested_repo(tmp_path, _index(None))
        with pytest.raises(MetadataLoadError) as exc:
            discover_section_indexes(root)
        assert exc.value.path == "docs/guides/sub/index.md"
        assert f"`{CONTENTS_KEY}:`" in str(exc.value)
        assert "generated, routing, rendered" in str(exc.value)

    def test_unknown_declaration_names_the_page(self, tmp_path):
        root = self._nested_repo(tmp_path, _index("themed"))
        with pytest.raises(MetadataLoadError, match="themed") as exc:
            discover_section_indexes(root)
        assert exc.value.path == "docs/guides/sub/index.md"

    def test_rendered_index_is_recorded_and_left_alone(self, tmp_path):
        root = self._nested_repo(tmp_path, _index("rendered"))
        indexes = discover_section_indexes(root)
        assert indexes.rendered == ("guides/sub/index.md",)
        assert [p.path for p in indexes.generated] == ["guides/index.md"]
        assert indexes.routing == ()

    def test_routing_index_must_link_every_nav_member(self, tmp_path):
        body = "# Sub\n\nRead [Leaf](leaf.md) first.\n"
        root = self._nested_repo(tmp_path, _index("routing", body))
        (page,) = discover_section_indexes(root).routing
        assert page.required == ("guides/sub/leaf.md", "guides/sub/other.md")
        (fault,) = routing_faults(root, page)
        assert fault.path == "docs/guides/sub/index.md"
        assert "guides/sub/other.md" in str(fault)

    def test_routing_index_linking_every_member_has_no_fault(self, tmp_path):
        body = "# Sub\n\n[Leaf](leaf.md) then [Other](./other.md#top).\n"
        root = self._nested_repo(tmp_path, _index("routing", body))
        (page,) = discover_section_indexes(root).routing
        assert routing_faults(root, page) == []

    def test_routing_index_reports_every_missing_member(self, tmp_path):
        root = self._nested_repo(tmp_path, _index("routing"))
        (page,) = discover_section_indexes(root).routing
        missing = [str(f) for f in routing_faults(root, page)]
        assert len(missing) == 2

    def test_routing_index_owns_siblings_the_nav_omits(self, tmp_path):
        """A leaf kept out of the nav behind its routing page (DF-11-006) is
        still required, so a page added to the directory without a link is
        caught; a fragment and the working record are not."""
        root = self._nested_repo(
            tmp_path,
            _index("routing", "# Sub\n\n[Leaf](leaf.md) [Other](other.md)\n"),
            **{
                "docs/guides/sub/orphan.md": _page("Orphan"),
                "docs/guides/sub/_fragment.md": "shared text\n",
                "docs/guides/sub/host.md": (
                    "# Host\n\n{% include-markdown './_fragment.md' %}\n"
                ),
            },
        )
        (page,) = discover_section_indexes(root).routing
        assert "guides/sub/orphan.md" in page.required
        assert "guides/sub/host.md" in page.required
        assert "guides/sub/_fragment.md" not in page.required
        assert "guides/sub/index.md" not in page.required
        missing = {
            str(f).split("link ")[1].split(";")[0]
            for f in routing_faults(root, page)
        }
        assert missing == {"guides/sub/orphan.md", "guides/sub/host.md"}

    def test_routing_index_does_not_own_the_working_record(self, tmp_path):
        files = {
            "docs/adr/index.md": _index("routing", "# ADRs\n"),
            "docs/adr/0001-x.md": _page("X"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", "guides/a.md"]},
            {"ADRs": ["adr/index.md"]},
        ]
        files["docs/guides/index.md"] = _LANDING
        files["docs/guides/a.md"] = _page("A")
        root = _repo(tmp_path, files, nav)
        (page,) = discover_section_indexes(root).routing
        assert page.required == ()

    def test_routing_member_group_counts_as_its_index(self, tmp_path):
        files = {
            "docs/guides/index.md": _index(
                "routing", "# G\n\n[S](sub/index.md)\n"
            ),
            "docs/guides/sub/index.md": _SUB_LANDING,
            "docs/guides/sub/leaf.md": _page("Leaf"),
            "docs/guides/loose/x.md": _page("X"),
            "docs/guides/loose/y.md": _page("Y"),
        }
        nav: list[object] = [
            {
                "Guides": [
                    "guides/index.md",
                    {"Sub": ["guides/sub/index.md", "guides/sub/leaf.md"]},
                    {"Loose": ["guides/loose/x.md", "guides/loose/y.md"]},
                    {"Home": "https://example.org/"},
                ]
            }
        ]
        root = _repo(tmp_path, files, nav)
        indexes = discover_section_indexes(root)
        (page,) = indexes.routing
        assert page.required == (
            "guides/sub/index.md",
            "guides/loose/x.md",
            "guides/loose/y.md",
        )
        assert [p.path for p in indexes.generated] == ["guides/sub/index.md"]

    def test_routing_faults_fail_check_and_are_not_written(
        self, tmp_path, monkeypatch, capsys
    ):
        root = self._nested_repo(tmp_path, _index("routing"))
        monkeypatch.setattr(site_sync, "repo_root", lambda: root)
        with pytest.raises(MetadataLoadErrors) as exc:
            site_sync.stale_artifacts(root)
        assert len(exc.value.failures) == 2
        with pytest.raises(SystemExit) as run:
            site_sync.main(["--write"])
        assert run.value.code == 1
        err = capsys.readouterr().err
        assert "routing-page link(s) missing" in err
        assert "guides/sub/other.md" in err
        assert (root / "docs/guides/sub/index.md").read_text() == _index(
            "routing"
        )

    def test_leaf_index_with_orphan_siblings_must_declare(self, tmp_path):
        """A nav leaf ``index.md`` whose directory holds pages the nav omits
        is their door (DF-11-006); leaving it undeclared is a fault."""
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": _page("A"),
            "docs/guides/set/index.md": "# Set\n\n[One](one.md)\n",
            "docs/guides/set/one.md": _page("One"),
        }
        nav: list[object] = [
            {
                "Guides": [
                    "guides/index.md",
                    "guides/a.md",
                    {"Set": "guides/set/index.md"},
                ]
            }
        ]
        with pytest.raises(MetadataLoadError, match="nav omits") as exc:
            discover_section_indexes(_repo(tmp_path, files, nav))
        assert exc.value.path == "docs/guides/set/index.md"
        assert "guides/set/one.md" in str(exc.value)

    def test_declared_leaf_index_routes_its_siblings(self, tmp_path):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/a.md": _page("A"),
            "docs/guides/set/index.md": _index(
                "routing", "# Set\n\n[One](one.md)\n"
            ),
            "docs/guides/set/one.md": _page("One"),
            "docs/guides/set/two.md": _page("Two"),
        }
        nav: list[object] = [
            {
                "Guides": [
                    "guides/index.md",
                    "guides/a.md",
                    {"Set": "guides/set/index.md"},
                ]
            }
        ]
        root = _repo(tmp_path, files, nav)
        (page,) = discover_section_indexes(root).routing
        assert page.required == ("guides/set/one.md", "guides/set/two.md")
        (fault,) = routing_faults(root, page)
        assert "guides/set/two.md" in str(fault)

    def test_undeclared_leaf_index_without_orphans_is_a_content_page(
        self, tmp_path
    ):
        files = {
            "docs/guides/index.md": _LANDING,
            "docs/guides/essay/index.md": _page("Essay"),
        }
        nav: list[object] = [
            {"Guides": ["guides/index.md", "guides/essay/index.md"]}
        ]
        indexes = discover_section_indexes(_repo(tmp_path, files, nav))
        assert indexes.routing == () and indexes.rendered == ()
        assert [p.path for p in indexes.generated] == ["guides/index.md"]

    def test_routing_is_never_the_only_shape(self, tmp_path):
        """A nav whose every group index routes has no generated page, and
        that is the DF-09-009 empty target set, not a pass."""
        files = {
            "docs/guides/index.md": _index("routing", "# G\n\n[A](a.md)\n"),
            "docs/guides/a.md": _page("A"),
        }
        nav: list[object] = [{"Guides": ["guides/index.md", "guides/a.md"]}]
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            discover_section_indexes(_repo(tmp_path, files, nav))


# ---------------------------------------------------------------------------
# Coverage matrix
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-008")
class TestCoverageMatrix:
    def _counted(self, tmp_path: Path, pages: dict[str, str]):
        files = {f"docs/{k}": v for k, v in pages.items()}
        return measure_coverage(_repo(tmp_path, files, list(pages)))

    def test_counts_a_declared_page_in_its_cell(self, tmp_path):
        cov = self._counted(
            tmp_path,
            {
                "a.md": _page(
                    "A", level=200, stakeholder_type="[cvd-practitioner]"
                )
            },
        )
        assert cov.cells[("cvd-practitioner", 200)] == 1
        assert cov.declared == 1

    def test_all_is_its_own_row(self, tmp_path):
        cov = self._counted(
            tmp_path, {"a.md": _page("A", level=100, stakeholder_type="ALL")}
        )
        assert cov.cells[(ALL_STAKEHOLDERS, 100)] == 1
        assert all(
            cov.cells[(member.value, 100)] == 0 for member in StakeholderType
        )
        assert ROWS[-1] == ALL_STAKEHOLDERS

    def test_page_listing_two_types_counts_in_both_rows(self, tmp_path):
        cov = self._counted(
            tmp_path,
            {
                "a.md": _page(
                    "A",
                    level=300,
                    stakeholder_type="[platform-developer, project-contributor]",
                )
            },
        )
        assert cov.cells[("platform-developer", 300)] == 1
        assert cov.cells[("project-contributor", 300)] == 1
        assert cov.declared == 1

    def test_undeclared_and_working_record_pages_are_not_counted(
        self, tmp_path
    ):
        cov = self._counted(
            tmp_path,
            {
                "a.md": _page("A"),
                "adr/0001-x.md": _page(
                    "X", stakeholder_type="[project-contributor]"
                ),
            },
        )
        assert cov.declared == 0
        assert sum(cov.cells.values()) == 0

    def test_adding_an_undeclared_page_does_not_stale_the_matrix(
        self, tmp_path
    ):
        root = _guides_repo(tmp_path, a=_page("A"))
        site_sync.write_artifacts(root)
        (root / "docs/guides/new.md").write_text(_page("New"))
        assert MATRIX_PATH not in site_sync.stale_artifacts(root)

    def test_malformed_declaration_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError):
            self._counted(
                tmp_path,
                {"a.md": _page("A", level=250, stakeholder_type="ALL")},
            )

    def test_empty_cells_render_and_pass(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        text = render_matrix(measure_coverage(root))
        for row in ROWS:
            assert f"| `{row}` | " + " | ".join("0" for _ in LEVELS) in text
        (root / MATRIX_PATH).parent.mkdir(parents=True, exist_ok=True)
        site_sync.write_artifacts(root)
        assert site_sync.stale_artifacts(root) == []

    def test_drift_is_detected(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"))
        site_sync.write_artifacts(root)
        (root / "docs/guides/a.md").write_text(
            _page("A", level=100, stakeholder_type="ALL")
        )
        assert site_sync.stale_artifacts(root) == [MATRIX_PATH]


# ---------------------------------------------------------------------------
# Stakeholder-type fragment
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-011")
class TestStakeholderFragment:
    def test_has_a_row_per_member_then_all(self):
        rows = [
            line.split("|")[1].strip()
            for line in render_fragment().splitlines()
            if line.startswith("| `")
        ]
        assert rows == [f"`{key}`" for key in ROWS]

    def test_uses_the_schema_wording(self):
        text = render_fragment()
        for key, desc in AUDIENCE_DESCRIPTIONS.items():
            assert f"| `{key}` | {desc.who} | {desc.wants} |" in text

    def test_member_without_a_description_fails(self, monkeypatch):
        partial = {
            k: v
            for k, v in AUDIENCE_DESCRIPTIONS.items()
            if k != StakeholderType.PROCESS_RESEARCHER
        }
        monkeypatch.setattr(
            "vultron.metadata.docs.stakeholder_fragment.AUDIENCE_DESCRIPTIONS",
            partial,
        )
        with pytest.raises(ValueError, match="process-researcher"):
            render_fragment()

    def test_drift_is_detected(self, tmp_path, monkeypatch):
        root = _guides_repo(tmp_path, a=_page("A"))
        site_sync.write_artifacts(root)
        changed = dict(AUDIENCE_DESCRIPTIONS)
        changed[ALL_STAKEHOLDERS] = AudienceDescription(who="w", wants="x")
        monkeypatch.setattr(
            "vultron.metadata.docs.stakeholder_fragment.AUDIENCE_DESCRIPTIONS",
            changed,
        )
        assert site_sync.stale_artifacts(root) == [FRAGMENT_PATH]

    def test_every_schema_member_is_described(self):
        assert set(AUDIENCE_DESCRIPTIONS) == {
            *(m.value for m in page_schema.StakeholderType),
            ALL_STAKEHOLDERS,
        }

    def test_keys_are_every_member_then_all(self):
        assert (
            *(m.value for m in page_schema.StakeholderType),
            ALL_STAKEHOLDERS,
        ) == page_schema.AUDIENCE_KEYS


# ---------------------------------------------------------------------------
# Sync command
# ---------------------------------------------------------------------------


@pytest.mark.spec("DF-11-005")
class TestSiteSync:
    def test_hand_edit_to_a_listing_is_stale_and_write_repairs_it(
        self, tmp_path
    ):
        root = _guides_repo(tmp_path, a=_page("A"))
        site_sync.write_artifacts(root)
        landing = root / "docs/guides/index.md"
        landing.write_text(
            landing.read_text().replace("- [A](a.md)", "- [A](a.md) — hand")
        )
        assert site_sync.stale_artifacts(root) == ["docs/guides/index.md"]
        assert site_sync.write_artifacts(root) == ["docs/guides/index.md"]
        assert site_sync.stale_artifacts(root) == []

    def test_nav_change_is_stale(self, tmp_path):
        root = _guides_repo(tmp_path, a=_page("A"), b=_page("B"))
        site_sync.write_artifacts(root)
        (root / "mkdocs.yml").write_text(
            yaml.safe_dump(
                {"nav": [{"Guides": ["guides/index.md", "guides/b.md"]}]}
            )
        )
        assert "docs/guides/index.md" in site_sync.stale_artifacts(root)

    def test_emptied_landing_page_fails_rather_than_regenerates(
        self, tmp_path
    ):
        root = _guides_repo(tmp_path, a=_page("A"))
        (root / "docs/guides/index.md").write_text("")
        with pytest.raises(MetadataLoadError, match="hand-written prose"):
            site_sync.stale_artifacts(root)

    def test_check_exits_nonzero_when_stale(
        self, tmp_path, monkeypatch, capsys
    ):
        root = _guides_repo(tmp_path, a=_page("A"))
        monkeypatch.setattr(site_sync, "repo_root", lambda: root)
        with pytest.raises(SystemExit) as exc:
            site_sync.main(["--check"])
        assert exc.value.code == 1
        assert "docs-site --write" in capsys.readouterr().err
        site_sync.main(["--write"])
        site_sync.main(["--check"])
        assert "in sync" in capsys.readouterr().out

    def test_check_reports_a_generator_error_without_a_traceback(
        self, tmp_path, monkeypatch, capsys
    ):
        root = _repo(tmp_path, {"docs/about/x.md": _page("X")}, ["about/x.md"])
        monkeypatch.setattr(site_sync, "repo_root", lambda: root)
        with pytest.raises(SystemExit) as exc:
            site_sync.main(["--check"])
        assert exc.value.code == 1
        assert "DF-09-009" in capsys.readouterr().err

    def test_committed_site_artifacts_are_in_sync(self):
        """The CI backstop for the ``docs-site-sync`` pre-commit hook."""
        assert site_sync.stale_artifacts(repo_root()) == [], (
            "run 'uv run docs-site --write' and commit the result"
        )

    def test_committed_generated_pages_are_the_decided_set(self):
        """The decision table in ``notes/site-information-architecture.md``
        § "Sub-section index decisions" is what this set pins (#3617)."""
        indexes = discover_section_indexes(repo_root())
        assert {p.path for p in indexes.generated} == {
            "tutorials/index.md",
            "topics/index.md",
            "howto/index.md",
            "reference/index.md",
            "research/index.md",
            "topics/background/index.md",
            "topics/case_lifecycle/index.md",
            "topics/process_models/rm/index.md",
            "topics/process_models/em/index.md",
            "topics/process_models/cs/index.md",
            "topics/process_models/model_interactions/index.md",
            "topics/behavior_logic/use-cases/index.md",
            "topics/future_work/index.md",
            "reference/iso_crosswalks/index.md",
            "reference/formal_protocol/index.md",
            "reference/messages/index.md",
            "topics/measuring_cvd/index.md",
            "topics/other_uses/index.md",
        }
        assert {p.path for p in indexes.routing} == {
            "topics/process_models/index.md",
            "topics/behavior_logic/index.md",
            "howto/activitypub/index.md",
            "howto/activitypub/activities/index.md",
            "reference/specs/index.md",
        }
        assert set(indexes.rendered) == {"topics/scenarios/index.md"}

    def test_committed_routing_pages_link_every_member(self):
        root = repo_root()
        faults = [
            str(fault)
            for page in discover_section_indexes(root).routing
            for fault in routing_faults(root, page)
        ]
        assert faults == []

    def test_the_activity_guides_index_is_required_to_route_its_leaves(self):
        """The thirteen guides are out of the nav (DF-11-006, #3627), so only
        the sibling rule makes their routing page accountable for them."""
        (page,) = [
            p
            for p in discover_section_indexes(repo_root()).routing
            if p.path == "howto/activitypub/activities/index.md"
        ]
        assert "howto/activitypub/activities/establish_embargo.md" in (
            page.required
        )
        assert len(page.required) >= 13
