"""Tests for vultron.metadata.specs.render (SR.5.3).

Covers: render_markdown output structure, export_json validity and filtering,
render_registry_markdown multi-file concatenation, export_yaml round-trip
fidelity.
"""

import json

import yaml
import pytest

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.render import (
    export_json,
    export_yaml,
    render_markdown,
    render_registry_markdown,
)

# ---------------------------------------------------------------------------
# Fixtures for behavioral specs with typed preconditions
# ---------------------------------------------------------------------------

BEHAVIORAL_YAML = {
    "id": "BEH",
    "title": "Behavioral Test Specs",
    "description": "Spec file for testing export_yaml fidelity",
    "version": "0.1",
    "kind": "domain",
    "scope": ["production"],
    "groups": [
        {
            "id": "BEH-01",
            "title": "BEH Group One",
            "trigger": {"type": "message_received", "value": "EP"},
            "specs": [
                {
                    "id": "BEH-01-001",
                    "priority": "MUST",
                    "statement": "BEH-01-001 MUST behave correctly",
                    "preconditions": [
                        {
                            "rm_state": ["START"],
                            "em_state": ["NONE"],
                            "role": ["vendor"],
                            "cs_pattern": "vfd...",
                            "description": "Participant is in RM Start; EM state is None; Participant holds the Vendor role; CS matches pattern vfd...",
                        }
                    ],
                    "postconditions": [
                        {"description": "State has been updated"}
                    ],
                }
            ],
        }
    ],
}


@pytest.fixture
def behavioral_spec_dir(tmp_path):
    """Spec directory with a BehavioralSpec that has typed precondition fields."""
    (tmp_path / "beh_specs.yaml").write_text(yaml.dump(BEHAVIORAL_YAML))
    return tmp_path


@pytest.fixture
def behavioral_registry(behavioral_spec_dir):
    return load_registry(behavioral_spec_dir)


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


# ---------------------------------------------------------------------------
# export_yaml — round-trip fidelity (#1469)
# ---------------------------------------------------------------------------


def test_export_yaml_precondition_typed_fields_preserved(behavioral_registry):
    """export_yaml must not drop typed Precondition fields (fix for #1469)."""
    yaml_str = export_yaml(behavioral_registry.files[0])
    data = yaml.safe_load(yaml_str)
    pc = data["groups"][0]["specs"][0]["preconditions"][0]
    assert pc["rm_state"] == ["START"]
    assert pc["em_state"] == ["NONE"]
    assert pc["role"] == ["vendor"]
    assert pc["cs_pattern"] == "vfd..."
    assert "description" in pc


def test_export_yaml_group_trigger_preserved(behavioral_registry):
    """export_yaml must not drop SpecGroup.trigger (fix for #1469)."""
    yaml_str = export_yaml(behavioral_registry.files[0])
    data = yaml.safe_load(yaml_str)
    trigger = data["groups"][0].get("trigger")
    assert trigger is not None
    assert trigger["type"] == "message_received"
    assert trigger["value"] == "EP"


def test_export_yaml_round_trips_through_schema(behavioral_registry):
    """YAML produced by export_yaml must reload without validation errors."""
    from pathlib import Path
    from vultron.metadata.specs.registry import load_registry

    yaml_str = export_yaml(behavioral_registry.files[0])
    tmp = Path(behavioral_registry.files[0].id)  # just for naming
    _ = tmp  # unused; we load from a tmp directory below

    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "beh.yaml"
        p.write_text(yaml_str)
        reloaded = load_registry(Path(d))

    from vultron.metadata.specs.schema import BehavioralSpec

    spec = reloaded.all_specs["BEH-01-001"]
    assert isinstance(spec, BehavioralSpec)
    assert spec.preconditions is not None
    pc = spec.preconditions[0]
    assert pc.rm_state is not None
    assert len(pc.rm_state) == 1
    assert pc.em_state is not None
    assert pc.role is not None
    assert pc.cs_pattern == "vfd..."
