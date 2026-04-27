"""Tests for vultron.metadata.specs.schema (SR.1.3).

Covers: SpecIdStr validation, StatementSpec, BehavioralSpec, SpecGroup,
SpecFile, SpecRegistry round-trip, and load_registry helpers.
"""

import yaml
import pytest
from pydantic import ValidationError

from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    BehaviorStep,
    LintWarningCode,
    Postcondition,
    Precondition,
    RFC2119Priority,
    RelationType,
    Relationship,
    Scope,
    SpecFile,
    SpecGroup,
    SpecKind,
    SpecTag,
    StatementSpec,
)

# ---------------------------------------------------------------------------
# SpecIdStr pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spec_id",
    [
        "AB",
        "ABCDEFGH",
        "AB-01",
        "AB-01-001",
        "ABCD-99-999",
    ],
)
def test_spec_id_str_valid(spec_id):
    spec = StatementSpec(
        id=spec_id,
        priority=RFC2119Priority.MUST,
        statement="MUST do something",
        rationale="Because testing",
    )
    assert spec.id == spec_id


@pytest.mark.parametrize(
    "spec_id",
    [
        "A",  # too short
        "ABCDEFGHI",  # too long (9 chars)
        "ab-01-001",  # lowercase
        "AB-1-001",  # group with 1 digit
        "AB-01-01",  # spec number with 2 digits
        "",  # empty
        "AB_01",  # underscore
    ],
)
def test_spec_id_str_invalid(spec_id):
    with pytest.raises(ValidationError):
        StatementSpec(
            id=spec_id,
            priority=RFC2119Priority.MUST,
            statement="MUST do something",
            rationale="Because testing",
        )


# ---------------------------------------------------------------------------
# StatementSpec
# ---------------------------------------------------------------------------


def test_statement_spec_defaults():
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST satisfy this",
        rationale="Because testing",
    )
    assert spec.testable is True
    assert spec.kind == SpecKind.GENERAL
    assert spec.scope == [Scope.PRODUCTION]
    assert spec.tags == []
    assert spec.relationships == []
    assert spec.lint_suppress == []


def test_statement_spec_full():
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.SHOULD,
        statement="AB-01-001 SHOULD do the thing",
        rationale="Because it helps",
        testable=False,
        kind=SpecKind.IMPLEMENTATION,
        scope=[Scope.PROTOTYPE],
        tags=[SpecTag.TESTING],
        relationships=[
            Relationship(
                rel_type=RelationType.DEPENDS_ON,
                spec_id="AB-01-002",
                note="needs this first",
            )
        ],
        lint_suppress=[LintWarningCode.TESTABLE_WITHOUT_STEPS],
    )
    assert spec.testable is False
    assert spec.kind == SpecKind.IMPLEMENTATION
    assert spec.scope == [Scope.PROTOTYPE]
    assert len(spec.tags) == 1
    assert len(spec.relationships) == 1
    assert len(spec.lint_suppress) == 1


def test_statement_spec_empty_statement_rejected():
    with pytest.raises(ValidationError):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="",
            rationale="Because testing",
        )


def test_statement_spec_empty_rationale_rejected():
    with pytest.raises(ValidationError):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST satisfy this",
            rationale="",
        )


# ---------------------------------------------------------------------------
# BehavioralSpec
# ---------------------------------------------------------------------------


def test_behavioral_spec_with_steps():
    spec = BehavioralSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST follow this workflow",
        rationale="Protocol requirement",
        preconditions=[Precondition(description="System is ready")],
        steps=[
            BehaviorStep(
                order=1,
                actor="sender",
                action="sends the message",
                expected="message delivered",
            )
        ],
        postconditions=[Postcondition(description="State updated")],
    )
    assert len(spec.steps) == 1
    assert spec.steps[0].order == 1
    assert len(spec.preconditions) == 1
    assert len(spec.postconditions) == 1


def test_behavioral_spec_empty_steps_valid():
    # Steps are optional; an empty BehavioralSpec is still valid
    spec = BehavioralSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST do something",
        rationale="Because testing",
    )
    assert spec.steps == []


# ---------------------------------------------------------------------------
# SpecGroup
# ---------------------------------------------------------------------------


def test_spec_group_valid():
    group = SpecGroup(
        id="AB-01",
        title="Test Group",
        specs=[
            StatementSpec(
                id="AB-01-001",
                priority=RFC2119Priority.MUST,
                statement="AB-01-001 MUST do the thing",
                rationale="Rationale",
            )
        ],
    )
    assert group.id == "AB-01"
    assert len(group.specs) == 1


def test_spec_group_empty_title_rejected():
    with pytest.raises(ValidationError):
        SpecGroup(id="AB-01", title="", specs=[])


# ---------------------------------------------------------------------------
# SpecFile
# ---------------------------------------------------------------------------


def test_spec_file_valid():
    sf = SpecFile(
        id="AB",
        title="Test File",
        description="A test file",
        version="0.1",
        groups=[
            SpecGroup(
                id="AB-01",
                title="Group",
                specs=[
                    StatementSpec(
                        id="AB-01-001",
                        priority=RFC2119Priority.MUST,
                        statement="AB-01-001 MUST work",
                        rationale="Because",
                    )
                ],
            )
        ],
    )
    assert sf.id == "AB"
    assert len(sf.groups) == 1


# ---------------------------------------------------------------------------
# SpecRegistry / load_registry
# ---------------------------------------------------------------------------


def test_registry_duplicate_spec_id_raises(tmp_path):
    dup_data = {
        "id": "DUP",
        "title": "Dup File",
        "description": "Duplicate spec IDs",
        "version": "0.1",
        "groups": [
            {
                "id": "DUP-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "DUP-01-001",
                        "priority": "MUST",
                        "statement": "DUP-01-001 MUST be unique",
                        "rationale": "Uniqueness",
                    },
                    {
                        "id": "DUP-01-001",  # duplicate
                        "priority": "SHOULD",
                        "statement": "DUP-01-001 SHOULD also exist",
                        "rationale": "But is duplicate",
                    },
                ],
            }
        ],
    }
    (tmp_path / "dup.yaml").write_text(yaml.dump(dup_data))
    with pytest.raises(ValueError, match="Duplicate spec ID"):
        load_registry(tmp_path)


def test_load_registry_round_trip(spec_dir):
    registry = load_registry(spec_dir)
    assert len(registry.files) == 1
    spec = registry.get("TST-01-001")
    assert spec.priority == RFC2119Priority.MUST


def test_load_registry_empty_dir(tmp_path):
    registry = load_registry(tmp_path)
    assert registry.files == []


def test_registry_get_unknown_raises(spec_dir):
    registry = load_registry(spec_dir)
    with pytest.raises(KeyError):
        registry.get("XX-99-999")


def test_registry_all_specs(spec_dir):
    registry = load_registry(spec_dir)
    assert "TST-01-001" in registry.all_specs


def test_registry_validate_cross_references_clean(spec_dir):
    registry = load_registry(spec_dir)
    assert registry.validate_cross_references() == []
