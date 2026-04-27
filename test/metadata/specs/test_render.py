"""Tests for vultron.metadata.specs.render (SR.5.3).

Covers: render_markdown output structure, export_json validity and filtering,
render_registry_markdown multi-file concatenation.
"""

import json

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render import (
    export_json,
    render_markdown,
    render_registry_markdown,
)

# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def test_render_markdown_includes_title(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "Test Spec File" in md


def test_render_markdown_includes_spec_id(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "TST-01-001" in md


def test_render_markdown_includes_group_title(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "Test Group One" in md


def test_render_markdown_includes_statement(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "MUST satisfy the test" in md


def test_render_markdown_includes_version(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "0.1" in md


def test_render_markdown_includes_rationale(loaded_registry):
    md = render_markdown(loaded_registry.files[0])
    assert "Required for test coverage" in md


# ---------------------------------------------------------------------------
# export_json
# ---------------------------------------------------------------------------


def test_export_json_valid(loaded_registry):
    json_str = export_json(loaded_registry)
    data = json.loads(json_str)
    assert "TST-01-001" in data


def test_export_json_filter_by_priority_match(loaded_registry):
    json_str = export_json(loaded_registry, priority="MUST")
    data = json.loads(json_str)
    assert "TST-01-001" in data


def test_export_json_filter_by_priority_no_match(loaded_registry):
    json_str = export_json(loaded_registry, priority="MAY")
    data = json.loads(json_str)
    assert data == {}


def test_export_json_filter_by_kind(loaded_registry):
    json_str = export_json(loaded_registry, kind="general")
    data = json.loads(json_str)
    assert "TST-01-001" in data


def test_export_json_filter_by_scope(loaded_registry):
    json_str = export_json(loaded_registry, scope="production")
    data = json.loads(json_str)
    assert "TST-01-001" in data


def test_export_json_filter_by_tags_match(loaded_registry):
    json_str = export_json(loaded_registry, tags=["testing"])
    data = json.loads(json_str)
    assert "TST-01-001" in data


def test_export_json_filter_by_tags_no_match(loaded_registry):
    json_str = export_json(loaded_registry, tags=["security"])
    data = json.loads(json_str)
    assert data == {}


# ---------------------------------------------------------------------------
# render_registry_markdown
# ---------------------------------------------------------------------------


def test_render_registry_markdown_multi_file(multi_spec_dir):
    registry = load_registry(multi_spec_dir)
    md = render_registry_markdown(registry)
    assert "Test Spec File" in md
    assert "More Test Specs" in md
    assert "TST-01-001" in md
    assert "MOR-01-001" in md
    assert "---" in md  # files separated by "---"
