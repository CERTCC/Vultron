"""Tests for the generated user-story table and traceability matrix.

Requirements: TRACE-01-001 (one entry per story page, citations grouped by
spec file and linked to the page that renders each row), TRACE-01-002 (a story
no requirement cites is flagged in both artifacts), TRACE-03-003 (both are
generated from the registry), DF-09-009 (an empty catalog fails).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vultron.metadata.base import repo_root
from vultron.metadata.docs.story_coverage import (
    UNCITED_NOTE,
    measure_story_coverage,
    render_matrix,
    render_table,
)
from vultron.metadata.docs.story_pages import STORY_ROOT, story_ids
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.specs.registry import SpecRegistry, load_registry
from vultron.metadata.specs.schema import SpecFile

#: A spec-file ID no Requirements Catalog page places, so a `protocol` item in
#: it has no anchor home. Its requirement ID is assembled rather than written
#: whole: SR-04-008 fails a spec-ID literal in a Python file outside
#: `test/metadata/specs/`, and this one resolves to nothing on purpose.
_UNPLACED_FILE = "ZZZ"
_UNPLACED_SPEC = f"{_UNPLACED_FILE}-01-001"

_STORY_PAGE = (
    "---\nstakeholder_type: [project-contributor]\n---\n\n"
    "# User Story `{short}`\n\n"
    "<!-- story-start -->As a Participant, {want}<!-- story-end -->\n"
)


def _write_stories(root: Path, *story_ids_: str) -> None:
    directory = root / STORY_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    for story in story_ids_:
        (directory / f"{story}.md").write_text(
            _STORY_PAGE.format(
                short=story.removeprefix("story_"), want=f"use {story}"
            ),
            encoding="utf-8",
        )


def _spec(spec_id: str, *stories: str, kind: str = "protocol") -> dict:
    spec: dict[str, object] = {
        "id": spec_id,
        "priority": "MUST",
        "kind": kind,
        "statement": f"{spec_id} MUST do the thing",
        "rationale": "Because testing",
    }
    if stories:
        spec["stories"] = list(stories)
    return spec


def _registry(file_id: str, title: str, *specs: dict) -> SpecRegistry:
    group_id = specs[0]["id"].rsplit("-", 1)[0]
    return SpecRegistry(
        files=[
            SpecFile.model_validate(
                {
                    "id": file_id,
                    "title": title,
                    "description": "Test spec file",
                    "scope": ["production"],
                    "groups": [
                        {
                            "id": group_id,
                            "title": "Group",
                            "specs": list(specs),
                        }
                    ],
                }
            )
        ]
    )


@pytest.mark.spec("TRACE-03-001", "DF-09-009")
class TestStoryPageCatalog:
    def test_only_story_stems_are_stories(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001", "story_2026_010")
        (tmp_path / STORY_ROOT / "index.md").write_text("# Stories\n")
        (tmp_path / STORY_ROOT / "table.md").write_text("| a |\n")
        assert story_ids(tmp_path) == ("story_2022_001", "story_2026_010")

    def test_a_missing_directory_fails(self, tmp_path):
        with pytest.raises(MetadataLoadError, match="catalog directory"):
            story_ids(tmp_path)

    def test_an_empty_catalog_fails(self, tmp_path):
        (tmp_path / STORY_ROOT).mkdir(parents=True)
        with pytest.raises(MetadataLoadError, match="DF-09-009"):
            story_ids(tmp_path)


@pytest.mark.spec("TRACE-01-001", "TRACE-03-003")
class TestCoverage:
    def test_the_matrix_has_one_entry_per_story_page(self, tmp_path):
        _write_stories(
            tmp_path, "story_2022_001", "story_2022_002", "story_2026_010"
        )
        registry = _registry(
            "CM", "Case Management", _spec("CM-01-001", "story_2022_001")
        )
        matrix = render_matrix(measure_story_coverage(tmp_path, registry))
        headings = [
            line for line in matrix.splitlines() if line.startswith("## ")
        ]
        assert headings == [
            "## [story_2022_001](story_2022_001.md)",
            "## [story_2022_002](story_2022_002.md)",
            "## [story_2026_010](story_2026_010.md)",
        ]

    @pytest.mark.spec("DF-11-003", "DF-11-006")
    def test_each_entry_links_its_story_page(self, tmp_path):
        """The matrix is what routes the story pages, so each entry links one."""
        _write_stories(tmp_path, "story_2022_001", "story_2022_002")
        registry = _registry(
            "CM", "Case Management", _spec("CM-01-001", "story_2022_001")
        )
        matrix = render_matrix(measure_story_coverage(tmp_path, registry))
        assert "(story_2022_001.md)" in matrix
        assert "(story_2022_002.md)" in matrix

    def test_an_entry_groups_its_citations_by_spec_file(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001")
        registry = SpecRegistry(
            files=[
                *_registry(
                    "CM",
                    "Case Management",
                    _spec("CM-01-002", "story_2022_001"),
                    _spec("CM-01-001", "story_2022_001"),
                ).files,
                *_registry(
                    "EP",
                    "Embargo Policy",
                    _spec("EP-01-001", "story_2022_001"),
                ).files,
            ]
        )
        coverage = measure_story_coverage(tmp_path, registry)
        assert [
            (c.file_id, c.spec_id) for c in coverage.by_story["story_2022_001"]
        ] == [
            ("CM", "CM-01-001"),
            ("CM", "CM-01-002"),
            ("EP", "EP-01-001"),
        ]
        matrix = render_matrix(coverage)
        assert "| CM — Case Management | [CM-01-001]" in matrix
        assert "| EP — Embargo Policy | [EP-01-001]" in matrix

    def test_a_citation_links_the_page_that_defines_its_anchor(self):
        """Over the live corpus: each link is the requirement's own row.

        A ``protocol`` requirement's row is on its Requirements Catalog page,
        any other kind's on its tier page (SR-09-001, SR-09-004), so the two
        assertions below are the two routes.
        """
        root = repo_root()
        coverage = measure_story_coverage(root, load_registry(root / "specs"))
        matrix = render_matrix(coverage)
        assert (
            "[VP-02-001](../vultron-spec/requirements/"
            "vultron-protocol.md#vp-02-001)" in matrix
        )
        assert "[TB-03-001](../specs/project.md#tb-03-001)" in matrix

    def test_every_citation_is_linked(self):
        """No live citation renders as a bare ID with no anchor home."""
        root = repo_root()
        coverage = measure_story_coverage(root, load_registry(root / "specs"))
        unlinked = [
            citation.spec_id
            for citations in coverage.by_story.values()
            for citation in citations
            if not citation.href
        ]
        assert unlinked == []

    def test_the_table_counts_citing_requirements(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry(
            "CM",
            "Case Management",
            _spec("CM-01-001", "story_2022_001"),
            _spec("CM-01-002", "story_2022_001"),
        )
        table = render_table(measure_story_coverage(tmp_path, registry))
        assert "| [2](traceability.md#story_2022_001) |" in table

    def test_a_requirement_with_no_anchor_home_renders_as_a_bare_id(
        self, tmp_path
    ):
        """A protocol requirement no catalog page places has no row to link.

        That is a placement fault `placement_faults` reports (DF-12-015); the
        matrix still names the requirement rather than dropping it.
        """
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry(
            _UNPLACED_FILE,
            "Unplaced File",
            _spec(_UNPLACED_SPEC, "story_2022_001"),
        )
        coverage = measure_story_coverage(tmp_path, registry)
        assert coverage.by_story["story_2022_001"][0].href == ""
        assert (
            f"| {_UNPLACED_FILE} — Unplaced File | {_UNPLACED_SPEC} |"
            in render_matrix(coverage)
        )

    def test_a_story_named_twice_is_counted_once(self, tmp_path):
        """`stories:` constrains each entry's shape, not the list's uniqueness."""
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry(
            "CM",
            "Case Management",
            _spec("CM-01-001", "story_2022_001", "story_2022_001"),
        )
        coverage = measure_story_coverage(tmp_path, registry)
        assert len(coverage.by_story["story_2022_001"]) == 1
        assert render_matrix(coverage).count("[CM-01-001](") == 1

    def test_a_cited_story_with_no_page_raises(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry(
            "CM", "Case Management", _spec("CM-01-001", "story_2022_999")
        )
        with pytest.raises(MetadataLoadError, match="story_2022_999"):
            measure_story_coverage(tmp_path, registry)

    def test_every_dangling_citation_is_named(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry(
            "CM",
            "Case Management",
            _spec("CM-01-001", "story_2022_998"),
            _spec("CM-01-002", "story_2022_999"),
        )
        with pytest.raises(MetadataLoadError) as exc:
            measure_story_coverage(tmp_path, registry)
        assert "story_2022_998" in str(exc.value)
        assert "story_2022_999" in str(exc.value)


@pytest.mark.spec("TRACE-01-002")
class TestUncitedStories:
    def test_an_uncited_story_is_marked_in_the_matrix(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001", "story_2022_002")
        registry = _registry(
            "CM", "Case Management", _spec("CM-01-001", "story_2022_001")
        )
        coverage = measure_story_coverage(tmp_path, registry)
        assert coverage.uncited == ("story_2022_002",)
        entry = render_matrix(coverage).split(
            "## [story_2022_002](story_2022_002.md)", 1
        )[1]
        assert UNCITED_NOTE in entry
        assert "TRACE-01-002" in entry

    def test_an_uncited_story_is_marked_in_the_table(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001", "story_2022_002")
        registry = _registry(
            "CM", "Case Management", _spec("CM-01-001", "story_2022_001")
        )
        table = render_table(measure_story_coverage(tmp_path, registry))
        row = next(
            line
            for line in table.splitlines()
            if line.startswith("| [2022_002]")
        )
        assert f"*{UNCITED_NOTE}*" in row

    def test_the_legend_names_both_cells(self, tmp_path):
        _write_stories(tmp_path, "story_2022_001")
        registry = _registry("CM", "Case Management", _spec("CM-01-001"))
        table = render_table(measure_story_coverage(tmp_path, registry))
        assert "**Coverage**" in table
        assert UNCITED_NOTE in table
        assert "material-check" not in table
