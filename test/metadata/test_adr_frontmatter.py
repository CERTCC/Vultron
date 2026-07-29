"""Tests for vultron.metadata.adr schema and loader.

Validation test requirement: specs/meta-specifications.yaml MS-14 (ADR-0043).
"""

import pytest
from pydantic import ValidationError

from vultron.metadata.adr.loader import load_adr_registry
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.specs.schema import AdrStatus


class TestAdrFrontmatterSchema:
    def test_minimal_valid(self):
        fm = AdrFrontmatter.model_validate({"status": "accepted"})
        assert fm.status is AdrStatus.ACCEPTED

    def test_all_status_values_accepted(self):
        for status in (
            "proposed",
            "accepted",
            "accepted-provisional",
            "rejected",
        ):
            fm = AdrFrontmatter.model_validate({"status": status})
            assert fm.status.value == status

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            AdrFrontmatter.model_validate({"status": "kinda-accepted"})

    def test_deciders_accepts_string_or_list(self):
        assert (
            AdrFrontmatter.model_validate(
                {"status": "accepted", "deciders": "adh"}
            ).deciders
            == "adh"
        )
        assert AdrFrontmatter.model_validate(
            {"status": "accepted", "deciders": ["adh", "Copilot"]}
        ).deciders == ["adh", "Copilot"]

    def test_date_parsed(self):
        fm = AdrFrontmatter.model_validate(
            {"status": "accepted", "date": "2026-07-29"}
        )
        assert fm.date is not None and fm.date.year == 2026

    def test_superseded_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            AdrFrontmatter.model_validate({"status": "superseded"})

    def test_deprecated_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            AdrFrontmatter.model_validate({"status": "deprecated"})

    def test_superseded_with_target_valid(self):
        fm = AdrFrontmatter.model_validate(
            {"status": "superseded", "superseded_by": "0041-next.md"}
        )
        assert fm.status is AdrStatus.SUPERSEDED
        assert fm.superseded_by == "0041-next.md"

    def test_inline_superseded_form_normalised(self):
        """'superseded by <link>' collapses to superseded + superseded_by."""
        fm = AdrFrontmatter.model_validate(
            {"status": "superseded by 0041-next.md"}
        )
        assert fm.status is AdrStatus.SUPERSEDED
        assert fm.superseded_by == "0041-next.md"

    def test_lint_suppress_valid_code(self):
        fm = AdrFrontmatter.model_validate(
            {
                "status": "accepted",
                "lint_suppress": ["status_prose_contradiction"],
            }
        )
        assert fm.lint_suppress is not None

    def test_lint_suppress_unknown_code_rejected(self):
        with pytest.raises(ValidationError):
            AdrFrontmatter.model_validate(
                {"status": "accepted", "lint_suppress": ["bogus_code"]}
            )

    def test_lint_suppress_empty_list_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            AdrFrontmatter.model_validate(
                {"status": "accepted", "lint_suppress": []}
            )


def test_all_adr_files_have_valid_frontmatter():
    """Every docs/adr/*.md (excluding index/README/template) validates.

    Also asserts every ``superseded_by`` target resolves to a real ADR.
    """
    registry = load_adr_registry()
    assert len(registry) > 0, "ADR registry must not be empty"
    # If load_adr_registry() raises, the test fails with that diagnostic.


def test_loader_rejects_dangling_superseded_by(tmp_path):
    """A superseded_by that resolves to no file is a load error."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-x.md").write_text(
        "---\nstatus: superseded\nsuperseded_by: 9999-nope.md\n---\n# x\n"
    )
    with pytest.raises(ValueError, match="superseded_by"):
        load_adr_registry(tmp_path)


def test_loader_raises_valueerror_on_malformed_yaml(tmp_path):
    """A malformed YAML frontmatter block surfaces as ValueError, not a raw
    parser traceback — so spec-lint and the pre-commit hooks report a clean,
    file-attributed error (MS-14-001) instead of crashing.
    """
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    # Unclosed flow sequence → yaml.parser.ParserError inside frontmatter.load.
    (adr_dir / "0001-broken.md").write_text(
        "---\nstatus: accepted\ndeciders: [unclosed\n---\n# broken\n"
    )
    with pytest.raises(ValueError, match="malformed YAML frontmatter"):
        load_adr_registry(tmp_path)
