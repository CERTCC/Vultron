"""Tests for the generated docs-site artifacts (``uv run docs-site``).

Requirements: DF-11-005 (landing pages generated and check gated), DF-11-008
(the coverage matrix), DF-11-011 (the stakeholder-type fragment), DF-09-009 (an
empty target set fails), DF-11-004 (a level is never rendered).
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
    END_MARKER,
    Entry,
    discover_landing_pages,
    render_listing,
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
from vultron.metadata.file_loading import MetadataLoadError

_LANDING = (
    "# Guides\n\nHand-written framing.\n\n"
    f"{BEGIN_MARKER}\n\n{END_MARKER}\n\nHand-written see-also.\n"
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
            "docs/guides/sub/index.md": _page("Sub", description="Sub d."),
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
        assert result.startswith("# Guides\n\nHand-written framing.\n\n")
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
        assert page_schema.AUDIENCE_KEYS == (
            *(m.value for m in page_schema.StakeholderType),
            ALL_STAKEHOLDERS,
        )


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
        with pytest.raises(FileNotFoundError, match="hand-written prose"):
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
        assert (
            site_sync.stale_artifacts(repo_root()) == []
        ), "run 'uv run docs-site --write' and commit the result"

    def test_committed_landing_pages_are_the_four_top_level_sections(self):
        paths = {p.path for p in discover_landing_pages(repo_root())}
        assert paths == {
            "tutorials/index.md",
            "topics/index.md",
            "howto/index.md",
            "reference/index.md",
        }
