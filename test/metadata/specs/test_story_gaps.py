"""Tests for the protocol story-gap report (``uv run story-gaps``).

Requirements: TRACE-03-004 — every ``kind: protocol`` requirement with no
``stories:`` entry, grouped by spec file then priority, suppression carriers
marked, one summary line per spec file by default, narrowable by spec file or
requirement-ID prefix.
"""

from __future__ import annotations

import pytest

from vultron.metadata.specs import story_gaps as story_gaps_module
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import SpecFile
from vultron.metadata.specs.story_gaps import (
    SUPPRESSED_MARK,
    gap_report,
    listing_lines,
    main,
    story_gaps,
    summary_lines,
    unmatched_selectors,
)


def _spec(
    spec_id: str,
    priority: str = "MUST",
    *,
    kind: str = "protocol",
    stories: list[str] | None = None,
    suppressed: bool = False,
) -> dict:
    spec: dict[str, object] = {
        "id": spec_id,
        "priority": priority,
        "kind": kind,
        "statement": f"{spec_id} states the thing",
        "rationale": "Because testing",
    }
    if stories:
        spec["stories"] = stories
    if suppressed:
        spec["lint_suppress"] = ["missing_story_reference"]
    return spec


def _spec_file(file_id: str, *specs: dict) -> SpecFile:
    groups: dict[str, list[dict]] = {}
    for spec in specs:
        groups.setdefault(str(spec["id"]).rsplit("-", 1)[0], []).append(spec)
    return SpecFile.model_validate(
        {
            "id": file_id,
            "title": f"{file_id} Title",
            "description": "Test spec file",
            "scope": ["production"],
            "groups": [
                {"id": group_id, "title": "Group", "specs": items}
                for group_id, items in groups.items()
            ],
        }
    )


@pytest.fixture
def registry() -> SpecRegistry:
    """Two spec files: gaps at several priorities, plus three non-gaps."""
    return SpecRegistry(
        files=[
            _spec_file(
                "CM",
                _spec("CM-01-002", "MAY"),
                _spec("CM-01-001", "MUST", suppressed=True),
                _spec("CM-23-004", "MUST"),
                _spec("CM-23-005", "MUST_NOT"),
                _spec("CM-23-006", stories=["story_2022_001"]),
            ),
            _spec_file(
                "AKM",
                _spec("AKM-01-001", "MUST_NOT"),
                # Not protocol, so not in the gap whatever its stories.
                _spec("AKM-01-002", "MUST", kind="project"),
            ),
            # File ID that CM is a prefix of: selecting CM must not reach it.
            _spec_file("CMX", _spec("CMX-01-001", "MUST")),
        ]
    )


@pytest.mark.spec("TRACE-03-004")
class TestSelection:
    def test_gaps_are_grouped_by_spec_file_and_priority(self, registry):
        assert [(g.file_id, g.spec_id) for g in story_gaps(registry)] == [
            ("AKM", "AKM-01-001"),
            ("CM", "CM-01-001"),
            ("CM", "CM-23-004"),
            ("CM", "CM-23-005"),
            ("CM", "CM-01-002"),
            ("CMX", "CMX-01-001"),
        ]

    def test_a_requirement_with_a_story_is_not_a_gap(self, registry):
        assert "CM-23-006" not in {g.spec_id for g in story_gaps(registry)}

    def test_only_protocol_requirements_are_gaps(self, registry):
        assert "AKM-01-002" not in {g.spec_id for g in story_gaps(registry)}

    def test_a_spec_file_selector_narrows_the_report(self, registry):
        assert {g.file_id for g in story_gaps(registry, ("CM",))} == {"CM"}

    def test_an_id_prefix_selector_narrows_the_report(self, registry):
        assert [g.spec_id for g in story_gaps(registry, ("CM-23",))] == [
            "CM-23-004",
            "CM-23-005",
        ]

    def test_a_selector_is_case_insensitive(self, registry):
        assert story_gaps(registry, ("cm-23",)) == story_gaps(
            registry, ("CM-23",)
        )

    def test_selectors_combine_as_a_union(self, registry):
        assert {g.spec_id for g in story_gaps(registry, ("AKM", "CM-01"))} == {
            "AKM-01-001",
            "CM-01-001",
            "CM-01-002",
        }

    def test_a_file_selector_does_not_reach_a_file_it_prefixes(self, registry):
        """`CM` must not collect CMX's gaps: the CS/CSB, MS/MSM shape."""
        assert {g.file_id for g in story_gaps(registry, ("CM",))} == {"CM"}
        assert {g.file_id for g in story_gaps(registry, ("CMX",))} == {"CMX"}

    def test_an_id_prefix_does_not_reach_a_prefix_it_extends(self, registry):
        assert [g.spec_id for g in story_gaps(registry, ("CM-01",))] == [
            "CM-01-001",
            "CM-01-002",
        ]

    def test_an_unmatched_selector_selects_nothing(self, registry):
        assert story_gaps(registry, ("ZZZ",)) == ()

    def test_an_unmatched_selector_is_reported(self, registry):
        assert unmatched_selectors(registry, ("ZZZ", "CM")) == ("ZZZ",)

    def test_a_selector_matching_a_gapless_area_is_not_unmatched(
        self, registry
    ):
        """CM-23-006 has a story, so CM-23-006 matches but yields no gap."""
        assert unmatched_selectors(registry, ("CM-23-006",)) == ()
        assert story_gaps(registry, ("CM-23-006",)) == ()


@pytest.mark.spec("TRACE-03-004")
class TestRendering:
    def test_the_default_report_is_one_line_per_spec_file(self, registry):
        lines = gap_report(registry)
        assert [line.split()[0] for line in lines[:-1]] == [
            "AKM",
            "CM",
            "CMX",
        ]
        assert lines[-1].startswith("6 requirement(s) in 3 spec file(s)")

    def test_a_summary_line_counts_by_priority(self, registry):
        line = next(
            line
            for line in summary_lines(story_gaps(registry))
            if line.startswith("CM")
        )
        assert "MUST 2, MUST_NOT 1, MAY 1" in line
        assert "1 suppressed" in line

    def test_a_suppression_carrier_is_marked(self, registry):
        lines = listing_lines(story_gaps(registry))
        marked = [line for line in lines if SUPPRESSED_MARK in line]
        assert marked == [f"    CM-01-001 {SUPPRESSED_MARK}"]

    def test_the_listing_nests_requirements_under_file_then_priority(
        self, registry
    ):
        lines = listing_lines(story_gaps(registry, ("CM",)))
        assert lines[:7] == [
            "CM (4)",
            "  MUST (2)",
            f"    CM-01-001 {SUPPRESSED_MARK}",
            "    CM-23-004",
            "  MUST_NOT (1)",
            "    CM-23-005",
            "  MAY (1)",
        ]

    def test_a_gapless_area_says_so(self, registry):
        """A real selector with no gaps reads as done, in both modes."""
        done = ["No kind: protocol requirement is missing a story."]
        assert gap_report(registry, ("CM-23-006",)) == done
        assert gap_report(registry, ("CM-23-006",), detail=True) == done

    def test_an_unmatched_selector_raises_rather_than_reading_as_done(
        self, registry
    ):
        with pytest.raises(ValueError, match="ZZZ"):
            gap_report(registry, ("ZZZ",))


@pytest.mark.spec("TRACE-03-004")
class TestCli:
    def test_the_cli_prints_the_summary_and_exits_zero(
        self, monkeypatch, capsys, registry, tmp_path
    ):
        monkeypatch.setattr(
            story_gaps_module, "load_registry", lambda _dir: registry
        )
        assert main(["--spec-dir", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "AKM" in out
        assert "CM-23-004" not in out

    def test_the_list_flag_prints_the_worklist(
        self, monkeypatch, capsys, registry, tmp_path
    ):
        monkeypatch.setattr(
            story_gaps_module, "load_registry", lambda _dir: registry
        )
        assert main(["--list", "CM-23", "--spec-dir", str(tmp_path)]) == 0
        out = capsys.readouterr().out
        assert "CM-23-004" in out
        assert "AKM-01-001" not in out

    def test_an_unmatched_selector_exits_two_naming_it(
        self, monkeypatch, capsys, registry, tmp_path
    ):
        monkeypatch.setattr(
            story_gaps_module, "load_registry", lambda _dir: registry
        )
        assert main(["ZZZ", "--spec-dir", str(tmp_path)]) == 2
        captured = capsys.readouterr()
        assert "ZZZ" in captured.err
        assert captured.out == ""
