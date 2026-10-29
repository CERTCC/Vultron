"""Tests for vultron.metadata.notes schema and loader.

Validation test requirement: specs/notes-frontmatter.yaml NF-04-001;
kind/tracks: NF-01-009 to NF-01-015; report: NF-09.
"""

import subprocess
from pathlib import Path

import frontmatter
import pytest
from pydantic import ValidationError

from vultron.metadata.docs.coverage_matrix import Coverage, render_matrix
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.notes import tracks as tracks_module
from vultron.metadata.notes.loader import load_notes_registry
from vultron.metadata.notes.schema import (
    GENERATED_MARKER,
    NoteKind,
    NotesFrontmatter,
    NoteStatus,
)
from vultron.metadata.notes.tracks import IssueState, plan_findings


class TestNotesFrontmatterSchema:
    def test_minimal_valid(self):
        nf = NotesFrontmatter.model_validate(
            {"title": "My Note", "status": "active", "kind": "guidance"}
        )
        assert nf.title == "My Note"
        assert nf.status == NoteStatus.ACTIVE

    def test_all_fields_valid(self):
        nf = NotesFrontmatter.model_validate(
            {
                "title": "Full Note",
                "status": "active",
                "kind": "guidance",
                "description": "A description.",
                "related_specs": ["specs/some-spec.yaml"],
                "related_notes": ["notes/other.md"],
                "relevant_packages": ["pydantic"],
            }
        )
        assert nf.description == "A description."
        assert nf.related_specs == ["specs/some-spec.yaml"]

    def test_superseded_status_requires_superseded_by(self):
        with pytest.raises(ValidationError, match="superseded_by"):
            NotesFrontmatter.model_validate(
                {
                    "title": "Old Note",
                    "status": "superseded",
                    "kind": "guidance",
                }
            )

    def test_superseded_status_with_superseded_by_valid(self):
        nf = NotesFrontmatter.model_validate(
            {
                "title": "Old Note",
                "status": "superseded",
                "kind": "guidance",
                "superseded_by": "notes/new-note.md",
            }
        )
        assert nf.superseded_by == "notes/new-note.md"

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate(
                {"title": "A Note", "status": "unknown", "kind": "guidance"}
            )

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate(
                {"title": "", "status": "active", "kind": "guidance"}
            )

    def test_empty_list_fields_rejected(self):
        for field in ("related_specs", "related_notes", "relevant_packages"):
            with pytest.raises(ValidationError, match="non-empty"):
                NotesFrontmatter.model_validate(
                    {
                        "title": "A Note",
                        "status": "active",
                        "kind": "guidance",
                        field: [],
                    }
                )

    def test_empty_superseded_by_rejected(self):
        """``superseded_by`` names a file, so an empty string fails (NF-01-012)."""
        with pytest.raises(ValidationError, match="superseded_by"):
            NotesFrontmatter.model_validate(
                {
                    "title": "Old Note",
                    "status": "superseded",
                    "kind": "guidance",
                    "superseded_by": "",
                }
            )

    def test_empty_package_name_rejected(self):
        """Each ``relevant_packages`` entry is a non-empty string (NF-01-013)."""
        with pytest.raises(ValidationError, match="relevant_packages"):
            NotesFrontmatter.model_validate(
                {
                    "title": "A Note",
                    "status": "active",
                    "kind": "guidance",
                    "relevant_packages": ["vultron.core", ""],
                }
            )

    def test_absent_optional_list_fields_ok(self):
        nf = NotesFrontmatter.model_validate(
            {"title": "A Note", "status": "draft", "kind": "guidance"}
        )
        assert nf.related_specs is None
        assert nf.related_notes is None
        assert nf.relevant_packages is None

    def test_all_status_values_accepted(self):
        for status in ("active", "draft", "superseded", "archived"):
            kwargs: dict = {
                "title": "A Note",
                "status": status,
                "kind": "guidance",
            }
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


def _note(**fields: object) -> dict[str, object]:
    return {"title": "A Note", "status": "active", **fields}


class TestNoteKind:
    """NF-01-009 through NF-01-011: ``kind`` and ``tracks``."""

    def test_kind_is_required(self):
        with pytest.raises(ValidationError, match="kind"):
            NotesFrontmatter.model_validate(_note())

    def test_unknown_kind_rejected(self):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate(_note(kind="design"))

    def test_plan_requires_tracks(self):
        with pytest.raises(ValidationError, match="'tracks' is required"):
            NotesFrontmatter.model_validate(_note(kind="plan"))

    def test_plan_with_tracks_valid(self):
        nf = NotesFrontmatter.model_validate(
            _note(kind="plan", tracks=["#1156", "#4492"])
        )
        assert nf.kind == NoteKind.PLAN
        assert nf.tracks == ["#1156", "#4492"]

    @pytest.mark.parametrize("kind", ["guidance", "generated"])
    def test_tracks_forbidden_off_plan(self, kind):
        with pytest.raises(ValidationError, match="only allowed"):
            NotesFrontmatter.model_validate(_note(kind=kind, tracks=["#1"]))

    @pytest.mark.parametrize("kind", ["guidance", "generated"])
    def test_bare_tracks_key_forbidden_off_plan(self, kind):
        """A ``tracks:`` line with no value parses to None but is present."""
        with pytest.raises(ValidationError, match="only allowed"):
            NotesFrontmatter.model_validate(_note(kind=kind, tracks=None))

    def test_empty_tracks_rejected(self):
        with pytest.raises(ValidationError, match="non-empty"):
            NotesFrontmatter.model_validate(_note(kind="plan", tracks=[]))

    @pytest.mark.parametrize("ref", ["1156", "#0", "#12a", "GH-12", ""])
    def test_malformed_issue_ref_rejected(self, ref):
        with pytest.raises(ValidationError):
            NotesFrontmatter.model_validate(_note(kind="plan", tracks=[ref]))


def _write_note(root: Path, name: str, front: str, body: str) -> None:
    (root / "notes").mkdir(exist_ok=True)
    (root / "notes" / name).write_text(f"---\n{front}---\n{body}")


class TestGeneratedMarker:
    """NF-01-011: a ``generated`` note's body starts with the marker."""

    _FRONT = "title: Gen\nstatus: active\nkind: generated\n"

    def test_generated_with_marker_loads(self, tmp_path):
        _write_note(
            tmp_path, "gen.md", self._FRONT, "<!-- GENERATED by x -->\n# Gen\n"
        )
        registry = load_notes_registry(tmp_path)
        assert registry["notes/gen.md"].kind == NoteKind.GENERATED

    def test_generated_without_marker_names_the_file(self, tmp_path):
        _write_note(tmp_path, "gen.md", self._FRONT, "# Gen\n")
        with pytest.raises(MetadataLoadError, match=r"notes/gen\.md"):
            load_notes_registry(tmp_path)

    @pytest.mark.parametrize(
        "marker", ["<!-- GENERATED -->", "<!-- GENERATEDfoo by x -->"]
    )
    def test_marker_must_be_the_word_then_a_generator(self, tmp_path, marker):
        _write_note(tmp_path, "gen.md", self._FRONT, f"{marker}\n# Gen\n")
        with pytest.raises(MetadataLoadError, match="naming its generator"):
            load_notes_registry(tmp_path)

    def test_marker_not_required_off_generated(self, tmp_path):
        _write_note(
            tmp_path,
            "g.md",
            "title: G\nstatus: active\nkind: guidance\n",
            "# G\n",
        )
        assert "notes/g.md" in load_notes_registry(tmp_path)


def test_coverage_matrix_render_is_a_valid_generated_note():
    """The generator's own output satisfies NF-01-011."""
    text = render_matrix(Coverage())
    post = frontmatter.loads(text)
    nf = NotesFrontmatter.model_validate(post.metadata)
    assert nf.kind == NoteKind.GENERATED
    assert post.content.startswith(GENERATED_MARKER)


class TestPlanFindings:
    """NF-09-001: flag plan notes whose tracked issues are all closed."""

    @staticmethod
    def _registry(**tracks: list[str]) -> dict[str, NotesFrontmatter]:
        registry = {
            f"notes/{name}.md": NotesFrontmatter.model_validate(
                _note(kind="plan", tracks=refs)
            )
            for name, refs in tracks.items()
        }
        registry["notes/rules.md"] = NotesFrontmatter.model_validate(
            _note(kind="guidance")
        )
        return registry

    def test_flags_only_all_closed(self):
        states = {1: IssueState.CLOSED, 2: IssueState.OPEN}
        findings = plan_findings(
            self._registry(done=["#1"], live=["#1", "#2"]), states
        )
        assert [f.path for f in findings] == ["notes/done.md"]
        assert "every tracked issue is closed" in findings[0].reason

    def test_open_parent_epic_keeps_note_unflagged(self):
        """A closed leaf under an open epic is not a retirement signal."""
        states = {10: IssueState.CLOSED, 99: IssueState.OPEN}
        assert plan_findings(self._registry(p=["#10", "#99"]), states) == []

    def test_unknown_issue_is_flagged(self):
        findings = plan_findings(
            self._registry(p=["#7"]), {1: IssueState.OPEN}
        )
        assert len(findings) == 1
        assert "unknown" in findings[0].reason

    def test_guidance_notes_never_flagged(self):
        assert plan_findings(self._registry(), {}) == []


def test_notes_tracks_cli_reports_and_never_edits(
    tmp_path, monkeypatch, capsys
):
    """NF-09-002: a flagged note is printed, exit is 0, the file is untouched."""
    _write_note(
        tmp_path,
        "p.md",
        "title: P\nstatus: active\nkind: plan\ntracks:\n  - '#5'\n",
        "# P\n",
    )
    before = (tmp_path / "notes" / "p.md").read_text()
    monkeypatch.setattr(
        tracks_module, "fetch_issue_states", lambda: {5: IssueState.CLOSED}
    )
    monkeypatch.setattr(
        tracks_module,
        "load_notes_registry",
        lambda: load_notes_registry(tmp_path),
    )
    tracks_module.main([])
    assert (
        "notes/p.md: every tracked issue is closed" in capsys.readouterr().out
    )
    assert (tmp_path / "notes" / "p.md").read_text() == before


def _fake_gh(
    monkeypatch, returncode: int = 0, stdout: str = "", stderr: str = ""
) -> None:
    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, returncode, stdout, stderr)

    monkeypatch.setattr(tracks_module.subprocess, "run", run)


class TestFetchIssueStates:
    """NF-09-002: every lookup failure surfaces as ``RuntimeError``."""

    def test_parses_gh_output(self, monkeypatch):
        _fake_gh(
            monkeypatch,
            stdout='[{"number": 1, "state": "OPEN"},'
            ' {"number": 2, "state": "CLOSED"}]',
        )
        assert tracks_module.fetch_issue_states() == {
            1: IssueState.OPEN,
            2: IssueState.CLOSED,
        }

    def test_nonzero_exit_raises(self, monkeypatch):
        _fake_gh(monkeypatch, returncode=1, stderr="auth required")
        with pytest.raises(RuntimeError, match="auth required"):
            tracks_module.fetch_issue_states()

    @pytest.mark.parametrize(
        "stdout", ["not json", '[{"number": 1, "state": "MERGED"}]', "[{}]"]
    )
    def test_unexpected_output_raises(self, monkeypatch, stdout):
        _fake_gh(monkeypatch, stdout=stdout)
        with pytest.raises(RuntimeError, match="unexpected output"):
            tracks_module.fetch_issue_states()

    def test_missing_gh_raises(self, monkeypatch):
        def run(args, **kwargs):
            raise FileNotFoundError("gh")

        monkeypatch.setattr(tracks_module.subprocess, "run", run)
        with pytest.raises(RuntimeError, match="could not run"):
            tracks_module.fetch_issue_states()


def test_notes_tracks_cli_exits_2_when_lookup_fails(monkeypatch, capsys):
    """NF-09-002: the command fails only when the issue lookup fails."""
    _fake_gh(monkeypatch, returncode=1, stderr="boom")
    with pytest.raises(SystemExit) as exc_info:
        tracks_module.main([])
    assert exc_info.value.code == 2
    assert "[ERROR]" in capsys.readouterr().err
