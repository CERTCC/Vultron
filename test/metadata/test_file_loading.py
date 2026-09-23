"""Tests for the shared loader failure attribution in ``file_loading.py``.

Requirements: MS-17-001 through MS-17-004, SR-03-009, NF-03-006. The spec
registry's adoption (SR-03-008, SR-04-002) is tested in
``test/metadata/specs/test_registry_attribution.py``, where synthetic spec IDs
are allowed.

Each adopting loader gets a parse failure and a validation failure, and every
assertion checks the raised error names the offending file — the property the
hand-written copies each got differently, or not at all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, ValidationError

from vultron.metadata.adr.index_gen import generate_index
from vultron.metadata.adr.loader import load_adr_registry
from vultron.metadata.file_loading import (
    FailureCollector,
    MetadataLoadError,
    MetadataLoadErrors,
    display_path,
    load_frontmatter,
    load_yaml,
    loads_frontmatter,
    validate,
)
from vultron.metadata.history.cli import _validate_frontmatter
from vultron.metadata.history.incoming import validate_incoming_learnings
from vultron.metadata.history.readme_gen import _parse_entry
from vultron.metadata.notes.loader import load_notes_registry

# ``statement: a: b`` — the unquoted ": " inside a plain scalar, the most
# common way this fault is introduced while editing spec prose (#3324 AC-2).
_UNQUOTED_COLON = "statement: the actor: sends it\n"


class _Model(BaseModel):
    title: str
    count: int


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The helper itself
# ---------------------------------------------------------------------------


@pytest.mark.spec("MS-17-004")
class TestExceptionContract:
    def test_error_is_a_value_error(self):
        assert issubclass(MetadataLoadError, ValueError)
        assert issubclass(MetadataLoadErrors, ValueError)

    def test_documented_guard_catches_a_parse_failure(self, tmp_path):
        path = _write(tmp_path / "x.yaml", "a: 1\n" + _UNQUOTED_COLON)

        try:
            load_yaml(path)
        except (ValidationError, ValueError) as exc:
            caught: Exception = exc
        else:  # pragma: no cover - the assertion below reports it
            pytest.fail("parse failure was not raised")

        assert isinstance(caught, MetadataLoadError)

    def test_error_is_not_the_protocol_hierarchy(self):
        from vultron.errors import VultronError

        assert not issubclass(MetadataLoadError, VultronError)


@pytest.mark.spec("MS-17-001")
class TestYamlAttribution:
    def test_names_path_line_and_column(self, tmp_path):
        path = _write(
            tmp_path / "specs" / "x.yaml", "a: 1\n" + _UNQUOTED_COLON
        )

        with pytest.raises(MetadataLoadError) as info:
            load_yaml(path, root=tmp_path)

        err = info.value
        assert err.path == "specs/x.yaml"
        assert (err.line, err.column) == (2, 21)
        assert str(err).startswith("specs/x.yaml:2:21 — YAML parse error:")

    def test_no_unicode_string_marker(self, tmp_path):
        path = _write(tmp_path / "x.yaml", "a: 1\n" + _UNQUOTED_COLON)

        with pytest.raises(MetadataLoadError) as info:
            load_yaml(path)

        assert "<unicode string>" not in str(info.value)
        assert "<file>" not in str(info.value)

    @pytest.mark.parametrize(
        "loader",
        [yaml.SafeLoader, getattr(yaml, "CSafeLoader", yaml.SafeLoader)],
        ids=["python", "libyaml"],
    )
    def test_unquoted_colon_gets_the_quoting_hint(self, tmp_path, loader):
        """Both parsers word this fault differently; both get the hint."""
        path = _write(tmp_path / "x.yaml", "a: 1\n" + _UNQUOTED_COLON)

        with pytest.raises(MetadataLoadError) as info:
            load_yaml(path, loader=loader)

        assert 'containing ": " must be quoted' in str(info.value)

    def test_unlisted_problem_gets_no_hint(self, tmp_path):
        path = _write(tmp_path / "x.yaml", "a: [1, 2\n")

        with pytest.raises(MetadataLoadError) as info:
            load_yaml(path)

        assert "hint" not in str(info.value)

    def test_undecodable_file_is_attributed(self, tmp_path):
        path = tmp_path / "x.yaml"
        path.write_bytes(b"a: \xff\n")

        with pytest.raises(MetadataLoadError, match=r"x\.yaml — not valid"):
            load_yaml(path)

    def test_missing_file_is_not_swallowed(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_yaml(tmp_path / "absent.yaml")


@pytest.mark.spec("MS-17-001")
class TestFrontmatterAttribution:
    def test_line_is_file_relative(self, tmp_path):
        """The mark is counted from the file's first line, fence included."""
        path = _write(
            tmp_path / "n.md", "---\ntitle: ok\n" + _UNQUOTED_COLON + "---\n"
        )

        with pytest.raises(MetadataLoadError) as info:
            load_frontmatter(path, root=tmp_path)

        assert info.value.line == 3
        assert str(info.value).startswith(
            "n.md:3:21 — malformed YAML frontmatter:"
        )

    def test_no_path_form_carries_position_only(self):
        with pytest.raises(MetadataLoadError) as info:
            loads_frontmatter("---\ntitle: ok\n" + _UNQUOTED_COLON + "---\n")

        assert info.value.path is None
        assert info.value.location is None
        assert str(info.value).startswith("malformed YAML frontmatter:")
        assert "<unicode string>" not in str(info.value)


@pytest.mark.spec("MS-17-001")
class TestValidateAttribution:
    def test_names_the_file_and_every_field(self, tmp_path):
        with pytest.raises(MetadataLoadError) as info:
            validate(
                _Model, {"count": "x"}, path=tmp_path / "m.md", root=tmp_path
            )

        message = str(info.value)
        assert message.startswith("m.md — ")
        assert "title: Field required" in message
        assert "count:" in message
        assert "_Model" not in message

    def test_prefix_is_kept(self):
        with pytest.raises(MetadataLoadError, match="^invalid thing: title"):
            validate(_Model, {"count": 1}, prefix="invalid thing")

    def test_key_lines_locate_the_failing_key(self, tmp_path):
        with pytest.raises(MetadataLoadError) as info:
            validate(
                _Model,
                {"title": "t", "count": "x"},
                path=tmp_path / "m.md",
                root=tmp_path,
                key_lines={"title": 2, "count": 3},
            )

        assert info.value.location == "m.md:3"

    def test_valid_data_round_trips(self):
        assert validate(_Model, {"title": "t", "count": 1}).count == 1


class TestDisplayPath:
    def test_relative_under_root(self, tmp_path):
        assert display_path(tmp_path / "a" / "b.md", tmp_path) == "a/b.md"

    def test_outside_root_shown_as_given(self, tmp_path):
        outside = Path("/elsewhere/b.md")
        assert display_path(outside, tmp_path) == str(outside)


@pytest.mark.spec("SR-03-009")
class TestFailureCollector:
    def test_collects_every_failure_as_structured_data(self):
        collector = FailureCollector()
        for name in ("a.md", "b.md"):
            with collector.attempt():
                raise MetadataLoadError("bad", path=name)

        with pytest.raises(MetadataLoadErrors) as info:
            collector.raise_if_any(summary="2 bad:", footer="fix them")

        assert [f.path for f in info.value.failures] == ["a.md", "b.md"]
        assert (
            str(info.value) == "2 bad:\n  a.md — bad\n  b.md — bad\n\nfix them"
        )

    def test_no_failures_raises_nothing(self):
        FailureCollector().raise_if_any()

    def test_other_exceptions_are_not_absorbed(self):
        """Only attributed failures are collected; a bug still surfaces."""
        collector = FailureCollector()
        with pytest.raises(KeyError):
            with collector.attempt():
                raise KeyError("loader bug")


# ---------------------------------------------------------------------------
# Adopting loaders
# ---------------------------------------------------------------------------


@pytest.mark.spec("NF-03-006")
class TestNotesLoader:
    def test_parse_fault_names_the_file(self, tmp_path):
        _write(
            tmp_path / "notes" / "n.md", "---\n" + _UNQUOTED_COLON + "---\n"
        )

        with pytest.raises(ValueError, match=r"^notes/n\.md:2:"):
            load_notes_registry(tmp_path)

    def test_invalid_status_names_the_file(self, tmp_path):
        _write(
            tmp_path / "notes" / "n.md", "---\ntitle: T\nstatus: wip\n---\n"
        )

        with pytest.raises(ValueError, match=r"^notes/n\.md — status"):
            load_notes_registry(tmp_path)

    def test_missing_frontmatter_names_the_file(self, tmp_path):
        _write(tmp_path / "notes" / "n.md", "# no frontmatter\n")

        with pytest.raises(ValueError, match=r"^notes/n\.md — missing"):
            load_notes_registry(tmp_path)


_ADR = """\
---
title: T
status: accepted
date: 2026-01-01
---
# ADR-0001 T
"""


@pytest.mark.spec("MS-17-001")
class TestAdrLoaders:
    def test_parse_fault_names_the_file(self, tmp_path):
        _write(
            tmp_path / "docs" / "adr" / "0001-t.md",
            "---\n" + _UNQUOTED_COLON + "---\n",
        )

        with pytest.raises(ValueError, match=r"^docs/adr/0001-t\.md:2:"):
            load_adr_registry(tmp_path)

    def test_invalid_status_names_the_file(self, tmp_path):
        _write(
            tmp_path / "docs" / "adr" / "0001-t.md",
            _ADR.replace("status: accepted", "status: maybe"),
        )

        with pytest.raises(ValueError, match=r"^docs/adr/0001-t\.md — status"):
            load_adr_registry(tmp_path)

    def test_index_generator_names_the_file(self, tmp_path):
        """``index_gen`` validated with a bare ``model_validate`` before."""
        _write(tmp_path / "docs" / "adr" / "index.md", "# ADRs\n")
        _write(
            tmp_path / "docs" / "adr" / "0001-t.md",
            _ADR.replace("status: accepted", "status: maybe"),
        )

        with pytest.raises(ValueError, match=r"^docs/adr/0001-t\.md — status"):
            generate_index(tmp_path)


_ENTRY = """\
---
title: T
type: implementation
timestamp: "2026-09-01T00:00:00Z"
source: ISSUE-1
---
body
"""


@pytest.mark.spec("MS-17-001")
class TestHistoryLoaders:
    def test_readme_entry_parse_fault_names_the_file(self, tmp_path):
        path = _write(tmp_path / "e.md", "---\n" + _UNQUOTED_COLON + "---\n")

        with pytest.raises(ValueError, match=r"e\.md:2:\d+ — malformed YAML"):
            _parse_entry(path)

    def test_readme_entry_invalid_field_names_the_file(self, tmp_path):
        path = _write(tmp_path / "e.md", _ENTRY.replace("ISSUE-1", ""))

        with pytest.raises(
            ValueError, match=r"e\.md — invalid history frontmatter: source"
        ):
            _parse_entry(path)

    def test_cli_no_path_form(self):
        with pytest.raises(ValueError) as info:
            _validate_frontmatter("---\n" + _UNQUOTED_COLON + "---\n")

        assert isinstance(info.value, MetadataLoadError)
        assert info.value.path is None
        assert "<unicode string>" not in str(info.value)

    def test_cli_invalid_field(self):
        with pytest.raises(ValueError, match="^invalid history frontmatter"):
            _validate_frontmatter(_ENTRY.replace("ISSUE-1", ""))

    def test_incoming_collects_parse_and_validation_faults(self, tmp_path):
        learnings = tmp_path / "plan" / "incoming" / "learnings"
        _write(learnings / "a.md", "---\n" + _UNQUOTED_COLON + "---\n")
        _write(learnings / "b.md", _ENTRY.replace("ISSUE-1", ""))

        with pytest.raises(MetadataLoadErrors) as info:
            validate_incoming_learnings(tmp_path)

        assert [f.path for f in info.value.failures] == [
            "plan/incoming/learnings/a.md",
            "plan/incoming/learnings/b.md",
        ]
        assert "Common fixes" in str(info.value)
