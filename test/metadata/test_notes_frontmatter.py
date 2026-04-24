"""Tests for vultron.metadata.notes schema and loader.

Validation test requirement: specs/notes-frontmatter.md NF-04-001.
"""

import pytest
from pydantic import ValidationError

from vultron.metadata.notes.loader import load_notes_registry
from vultron.metadata.notes.schema import NotesFrontmatter, NoteStatus


class TestNotesFrontmatterSchema:
    def test_minimal_valid(self):
        nf = NotesFrontmatter.model_validate(
            {"title": "My Note", "status": "active"}
        )
        assert nf.title == "My Note"
        assert nf.status == NoteStatus.ACTIVE

    def test_all_fields_valid(self):
        nf = NotesFrontmatter.model_validate(
            {
                "title": "Full Note",
                "status": "active",
                "description": "A description.",
                "related_specs": ["specs/some-spec.md"],
                "related_notes": ["notes/other.md"],
                "relevant_packages": ["pydantic"],
            }
        )
        assert nf.description == "A description."
        assert nf.related_specs == ["specs/some-spec.md"]

    def test_superseded_status_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            NotesFrontmatter.model_validate(
                {"title": "Old Note", "status": "superseded"}
            )

    def test_superseded_status_with_superseded_by_valid(self):
        nf = NotesFrontmatter.model_validate(
            {
                "title": "Old Note",
                "status": "superseded",
                "superseded_by": "notes/new-note.md",
            }
        )
        assert nf.superseded_by == "notes/new-note.md"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate(
                {"title": "A Note", "status": "unknown"}
            )

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate({"title": "", "status": "active"})

    def test_empty_list_fields_rejected(self):
        for field in ("related_specs", "related_notes", "relevant_packages"):
            with pytest.raises(ValidationError, match="non-empty"):
                NotesFrontmatter.model_validate(
                    {"title": "A Note", "status": "active", field: []}
                )

    def test_absent_optional_list_fields_ok(self):
        nf = NotesFrontmatter.model_validate(
            {"title": "A Note", "status": "draft"}
        )
        assert nf.related_specs is None
        assert nf.related_notes is None
        assert nf.relevant_packages is None

    def test_all_status_values_accepted(self):
        for status in ("active", "draft", "superseded", "archived"):
            kwargs: dict = {"title": "A Note", "status": status}
            if status == "superseded":
                kwargs["superseded_by"] = "notes/replacement.md"
            nf = NotesFrontmatter.model_validate(kwargs)
            assert nf.status.value == status


def test_all_notes_files_have_valid_frontmatter():
    """Every notes/*.md (except README.md) must have valid frontmatter.

    Satisfies NF-04-001.
    """
    registry = load_notes_registry()
    assert len(registry) > 0, "Notes registry must not be empty"
    # If load_notes_registry() raises a ValueError or ValidationError,
    # the test will fail with that error as the diagnostic message.
