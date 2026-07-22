"""Tests for vultron.metadata.specs.schema (SR.1.3).

Covers: SpecIdStr validation, StatementSpec, BehavioralSpec, SpecGroup,
SpecFile, SpecRegistry round-trip, and load_registry helpers.
"""

import yaml
import pytest
from pydantic import ValidationError

from vultron.metadata.specs.registry import load_registry
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
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
    Trigger,
    TriggerType,
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
        kind=SpecKind.PROTOCOL,
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
            kind=SpecKind.PROTOCOL,
        )


# ---------------------------------------------------------------------------
# StatementSpec — absent optional fields are None
# ---------------------------------------------------------------------------


def test_statement_spec_absent_fields():
    """Optional fields default to None when not provided; kind is required."""
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST satisfy this",
        kind=SpecKind.PROTOCOL,
    )
    assert spec.rationale is None
    assert spec.testable is True
    assert spec.scope is None
    assert spec.tags is None
    assert spec.relationships is None
    assert spec.lint_suppress is None


def test_statement_spec_full():
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.SHOULD,
        statement="AB-01-001 SHOULD do the thing",
        rationale="Because it helps",
        testable=False,
        kind=SpecKind.PROJECT,
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
    assert spec.kind == SpecKind.PROJECT
    assert spec.scope == [Scope.PROTOTYPE]
    assert spec.tags is not None and len(spec.tags) == 1
    assert spec.relationships is not None and len(spec.relationships) == 1
    assert spec.lint_suppress is not None and len(spec.lint_suppress) == 1


def test_statement_spec_empty_statement_rejected():
    with pytest.raises(ValidationError):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="",
            rationale="Because testing",
            kind=SpecKind.PROTOCOL,
        )


def test_statement_spec_empty_rationale_rejected():
    with pytest.raises(ValidationError):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST satisfy this",
            rationale="",
            kind=SpecKind.PROTOCOL,
        )


def test_statement_spec_rationale_none_allowed():
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST satisfy this",
        kind=SpecKind.PROTOCOL,
    )
    assert spec.rationale is None


def test_statement_spec_rationale_omitted_allowed():
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST satisfy this",
        rationale=None,
        kind=SpecKind.PROTOCOL,
    )
    assert spec.rationale is None


# ---------------------------------------------------------------------------
# Non-empty-if-present list validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field", ["scope", "tags", "relationships", "lint_suppress"]
)
def test_empty_list_rejected(field: str) -> None:
    """Empty lists are rejected — use None for absent."""
    kwargs: dict = {
        "id": "AB-01-001",
        "priority": RFC2119Priority.MUST,
        "statement": "AB-01-001 MUST pass",
        "kind": SpecKind.PROTOCOL,
        field: [],
    }
    with pytest.raises(ValidationError, match="non-empty"):
        StatementSpec(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# BehavioralSpec
# ---------------------------------------------------------------------------


def test_behavioral_spec_with_steps():
    spec = BehavioralSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST follow this workflow",
        rationale="Protocol requirement",
        kind=SpecKind.PROTOCOL,
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
    assert spec.steps is not None and len(spec.steps) == 1
    assert spec.steps[0].order == 1
    assert spec.preconditions is not None and len(spec.preconditions) == 1
    assert spec.postconditions is not None and len(spec.postconditions) == 1


def test_behavioral_spec_absent_steps_valid():
    spec = BehavioralSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST do something",
        rationale="Because testing",
        kind=SpecKind.PROTOCOL,
    )
    assert spec.steps is None


@pytest.mark.parametrize("field", ["preconditions", "steps", "postconditions"])
def test_behavioral_spec_empty_list_rejected(field: str) -> None:
    kwargs: dict = {
        "id": "AB-01-001",
        "priority": RFC2119Priority.MUST,
        "statement": "AB-01-001 MUST pass",
        "kind": SpecKind.PROTOCOL,
        field: [],
    }
    with pytest.raises(ValidationError, match="non-empty"):
        BehavioralSpec(**kwargs)  # type: ignore[arg-type]


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
                kind=SpecKind.PROTOCOL,
            )
        ],
    )
    assert group.id == "AB-01"
    assert len(group.specs) == 1


def test_spec_group_empty_title_rejected():
    with pytest.raises(ValidationError):
        SpecGroup(
            id="AB-01",
            title="",
            specs=[
                StatementSpec(
                    id="AB-01-001",
                    priority=RFC2119Priority.MUST,
                    statement="AB-01-001 MUST exist",
                    kind=SpecKind.PROTOCOL,
                )
            ],
        )


def test_spec_group_empty_specs_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        SpecGroup(id="AB-01", title="Empty Group", specs=[])


def test_spec_group_description_nonempty_if_present():
    with pytest.raises(ValidationError):
        SpecGroup(
            id="AB-01",
            title="Group",
            description="",
            specs=[
                StatementSpec(
                    id="AB-01-001",
                    priority=RFC2119Priority.MUST,
                    statement="AB-01-001 MUST exist",
                    kind=SpecKind.PROTOCOL,
                )
            ],
        )


def test_spec_group_description_none_allowed():
    group = SpecGroup(
        id="AB-01",
        title="Group",
        specs=[
            StatementSpec(
                id="AB-01-001",
                priority=RFC2119Priority.MUST,
                statement="AB-01-001 MUST exist",
                kind=SpecKind.PROTOCOL,
            )
        ],
    )
    assert group.description is None


def test_spec_group_empty_scope_rejected():
    with pytest.raises(ValidationError, match="non-empty"):
        SpecGroup(
            id="AB-01",
            title="Group",
            scope=[],
            specs=[
                StatementSpec(
                    id="AB-01-001",
                    priority=RFC2119Priority.MUST,
                    statement="AB-01-001 MUST exist",
                    kind=SpecKind.PROTOCOL,
                )
            ],
        )


# ---------------------------------------------------------------------------
# SpecFile
# ---------------------------------------------------------------------------


def test_spec_file_valid():
    sf = SpecFile(
        id="AB",
        title="Test File",
        description="A test file",
        version="0.1",
        scope=[Scope.PRODUCTION],
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
                        kind=SpecKind.PROTOCOL,
                    )
                ],
            )
        ],
    )
    assert sf.id == "AB"
    assert len(sf.groups) == 1


def test_spec_file_no_file_level_kind():
    """SpecFile no longer has a kind field; file-level kind is removed."""
    # SpecFile without kind= at file level is valid (kind lives on spec items)
    sf = SpecFile(
        id="AB",
        title="Test File",
        description="A test file",
        version="0.1",
        scope=[Scope.PRODUCTION],
        groups=[
            SpecGroup(
                id="AB-01",
                title="Group",
                specs=[
                    StatementSpec(
                        id="AB-01-001",
                        priority=RFC2119Priority.MUST,
                        statement="AB-01-001 MUST work",
                        kind=SpecKind.PROTOCOL,
                    )
                ],
            )
        ],
    )
    assert sf.id == "AB"
    assert not hasattr(sf, "kind")


def test_spec_file_requires_scope():
    with pytest.raises(ValidationError):
        SpecFile(  # type: ignore[call-arg]
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
                            kind=SpecKind.PROTOCOL,
                        )
                    ],
                )
            ],
        )


def test_spec_file_empty_scope_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        SpecFile(
            id="AB",
            title="Test File",
            description="A test file",
            version="0.1",
            scope=[],
            groups=[
                SpecGroup(
                    id="AB-01",
                    title="Group",
                    specs=[
                        StatementSpec(
                            id="AB-01-001",
                            priority=RFC2119Priority.MUST,
                            statement="AB-01-001 MUST work",
                            kind=SpecKind.PROTOCOL,
                        )
                    ],
                )
            ],
        )


def test_spec_file_empty_groups_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        SpecFile(
            id="AB",
            title="Test File",
            description="A test file",
            version="0.1",
            scope=[Scope.PRODUCTION],
            groups=[],
        )


# ---------------------------------------------------------------------------
# SpecRegistry / load_registry
# ---------------------------------------------------------------------------


def test_registry_duplicate_spec_id_raises(tmp_path):
    dup_data = {
        "id": "DUP",
        "title": "Dup File",
        "description": "Duplicate spec IDs",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "DUP-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "DUP-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "DUP-01-001 MUST be unique",
                        "rationale": "Uniqueness",
                    },
                    {
                        "id": "DUP-01-001",  # duplicate
                        "priority": "SHOULD",
                        "kind": "protocol",
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


# ---------------------------------------------------------------------------
# Inheritance resolution
# ---------------------------------------------------------------------------


def test_effective_kind_inherits_from_file(spec_dir):
    registry = load_registry(spec_dir)
    assert registry.get_effective_kind("TST-01-001") == SpecKind.PROTOCOL


def test_effective_scope_inherits_from_file(spec_dir):
    registry = load_registry(spec_dir)
    assert registry.get_effective_scope("TST-01-001") == [Scope.PRODUCTION]


def test_effective_tags_file_level_inherited(tmp_path):
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
        "version": "0.1",
        "scope": ["production"],
        "tags": ["protocol"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "TST-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST pass",
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    assert registry.get_effective_tags("TST-01-001") == [SpecTag.PROTOCOL]


def test_effective_tags_spec_overrides_file(tmp_path):
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
        "version": "0.1",
        "scope": ["production"],
        "tags": ["protocol"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "TST-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST pass",
                        "tags": ["testing"],
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    assert registry.get_effective_tags("TST-01-001") == [SpecTag.TESTING]


def test_effective_tags_empty_when_neither_spec_nor_file(tmp_path):
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "TST-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST pass",
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    assert registry.get_effective_tags("TST-01-001") == []


def test_effective_tags_graph_node_populated(tmp_path):
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
        "version": "0.1",
        "scope": ["production"],
        "tags": ["protocol"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "TST-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "TST-01-001 MUST pass",
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    node_tags = registry.graph.nodes["TST-01-001"]["tags"]
    assert node_tags == ["protocol"]


def test_effective_kind_spec_override(tmp_path):
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "TST-01",
                "title": "Group",
                "specs": [
                    {
                        "id": "TST-01-001",
                        "priority": "MUST",
                        "statement": "TST-01-001 MUST pass",
                        "kind": "project",
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    assert registry.get_effective_kind("TST-01-001") == SpecKind.PROJECT


# ---------------------------------------------------------------------------
# RelationType.SATISFIES
# ---------------------------------------------------------------------------


def test_relation_type_satisfies_exists():
    assert RelationType.SATISFIES == "satisfies"


def test_relationship_with_satisfies():
    rel = Relationship(rel_type=RelationType.SATISFIES, spec_id="VP-02-001")
    assert rel.rel_type == RelationType.SATISFIES
    assert rel.spec_id == "VP-02-001"


# ---------------------------------------------------------------------------
# TriggerType and Trigger
# ---------------------------------------------------------------------------


def test_trigger_type_values():
    assert TriggerType.MESSAGE_RECEIVED == "message_received"
    assert TriggerType.STATE_ENTERED == "state_entered"
    assert TriggerType.SCENARIO_START == "scenario_start"


def test_trigger_message_received():
    t = Trigger(type=TriggerType.MESSAGE_RECEIVED, value="EP")
    assert t.type == TriggerType.MESSAGE_RECEIVED
    assert t.value == "EP"


def test_trigger_state_entered():
    t = Trigger(type=TriggerType.STATE_ENTERED, value="RM.VALID")
    assert t.type == TriggerType.STATE_ENTERED
    assert t.value == "RM.VALID"


def test_trigger_scenario_start():
    t = Trigger(type=TriggerType.SCENARIO_START, value="two-actor")
    assert t.type == TriggerType.SCENARIO_START
    assert t.value == "two-actor"


# ---------------------------------------------------------------------------
# Precondition typed fields
# ---------------------------------------------------------------------------


def test_precondition_all_typed_fields():
    p = Precondition(
        rm_state=[RM.VALID, RM.ACCEPTED],
        em_state=[EM.NONE],
        cs_pattern="...pxa",
        role=[CVDRole.VENDOR],
        description="Vendor in RM Valid/Accepted, no embargo",
    )
    assert p.rm_state == [RM.VALID, RM.ACCEPTED]
    assert p.em_state == [EM.NONE]
    assert p.cs_pattern == "...pxa"
    assert p.role == [CVDRole.VENDOR]
    assert p.description == "Vendor in RM Valid/Accepted, no embargo"


def test_precondition_description_required():
    """Precondition requires description; omitting it raises ValidationError."""
    with pytest.raises(ValidationError):
        Precondition()  # pyright: ignore[reportCallIssue]


def test_precondition_description_only_typed_fields_optional():
    """All typed fields are optional; only description is required."""
    p = Precondition(description="No additional constraints")
    assert p.rm_state is None
    assert p.em_state is None
    assert p.cs_pattern is None
    assert p.role is None
    assert p.description == "No additional constraints"


def test_precondition_description_only():
    p = Precondition(description="CS pattern matches ...pxa")
    assert p.description == "CS pattern matches ...pxa"
    assert p.rm_state is None


# ---------------------------------------------------------------------------
# SpecGroup.trigger
# ---------------------------------------------------------------------------


def test_spec_group_with_trigger():
    group = SpecGroup(
        id="AB-01",
        title="Receive EP",
        trigger=Trigger(type=TriggerType.MESSAGE_RECEIVED, value="EP"),
        specs=[
            StatementSpec(
                id="AB-01-001",
                priority=RFC2119Priority.MUST,
                statement="AB-01-001 MUST transition EM to Proposed",
                kind=SpecKind.PROTOCOL,
            )
        ],
    )
    assert group.trigger is not None
    assert group.trigger.type == TriggerType.MESSAGE_RECEIVED
    assert group.trigger.value == "EP"


def test_spec_group_without_trigger():
    group = SpecGroup(
        id="AB-01",
        title="Some Group",
        specs=[
            StatementSpec(
                id="AB-01-001",
                priority=RFC2119Priority.MUST,
                statement="AB-01-001 MUST exist",
                kind=SpecKind.PROTOCOL,
            )
        ],
    )
    assert group.trigger is None


# ---------------------------------------------------------------------------
# BehavioralSpec with all new fields end-to-end
# ---------------------------------------------------------------------------


def test_behavioral_spec_full_new_fields():
    spec = BehavioralSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="On receiving EP while EM is NONE, MUST transition EM to PROPOSED",
        kind=SpecKind.PROTOCOL,
        preconditions=[
            Precondition(
                em_state=[EM.NONE],
                cs_pattern="...pxa",
                description="Embargo not yet started; CS not yet public",
            )
        ],
        steps=[
            BehaviorStep(
                order=1,
                actor="participant",
                action="transition EM NONE -> PROPOSED",
                expected="EM state is PROPOSED",
            ),
            BehaviorStep(
                order=2,
                actor="participant",
                action="emit EK",
                expected="EK queued to sender",
            ),
        ],
        postconditions=[
            Postcondition(description="EM state is PROPOSED; EK queued")
        ],
        relationships=[
            Relationship(
                rel_type=RelationType.SATISFIES,
                spec_id="VP-04-001",
                note="behavioral detail of embargo proposal receipt",
            )
        ],
    )
    assert spec.preconditions is not None
    assert spec.preconditions[0].em_state == [EM.NONE]
    assert spec.steps is not None and len(spec.steps) == 2
    assert spec.postconditions is not None
    assert spec.relationships is not None
    assert spec.relationships[0].rel_type == RelationType.SATISFIES


def test_behavioral_spec_round_trips_through_yaml(tmp_path):
    data = {
        "id": "BTB",
        "title": "Behavioral Test Spec",
        "description": "Tests BehavioralSpec fields round-trip through YAML",
        "version": "0.1",
        "scope": ["prototype", "production"],
        "groups": [
            {
                "id": "BTB-01",
                "title": "Receive EP",
                "trigger": {
                    "type": "message_received",
                    "value": "EP",
                },
                "specs": [
                    {
                        "id": "BTB-01-001",
                        "priority": "MUST",
                        "kind": "protocol",
                        "statement": "MUST transition EM to PROPOSED on EP",
                        "preconditions": [
                            {
                                "em_state": ["NONE"],
                                "cs_pattern": "...pxa",
                                "description": "EM state is None; CS matches pattern ...pxa",
                            }
                        ],
                        "steps": [
                            {
                                "order": 1,
                                "actor": "participant",
                                "action": "transition EM NONE -> PROPOSED",
                                "expected": "EM is PROPOSED",
                            }
                        ],
                        "postconditions": [
                            {"description": "EM state is PROPOSED"}
                        ],
                        "relationships": [
                            {
                                "rel_type": "satisfies",
                                "spec_id": "VP-04-001",
                            }
                        ],
                    }
                ],
            }
        ],
    }
    (tmp_path / "btb.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    spec = registry.get("BTB-01-001")
    assert isinstance(spec, BehavioralSpec)
    assert spec.preconditions is not None
    assert spec.preconditions[0].cs_pattern == "...pxa"
    assert spec.steps is not None and spec.steps[0].order == 1
    assert spec.relationships is not None
    assert spec.relationships[0].rel_type == RelationType.SATISFIES
    group = registry.all_groups["BTB-01"]
    assert group.trigger is not None
    assert group.trigger.type == TriggerType.MESSAGE_RECEIVED
    assert group.trigger.value == "EP"


# ---------------------------------------------------------------------------
# SR-02-005 — SpecKind enum completeness canary
# ---------------------------------------------------------------------------


def test_spec_kind_contains_exactly_four_tiers():
    # SR-02-005 canary: catches silent removal or misspelling of any tier.
    expected = {
        "protocol",
        "architecture",
        "project",
        "process",
    }
    assert set(SpecKind) == expected


# ---------------------------------------------------------------------------
# SpecKind.PROCESS round-trip through StatementSpec / SpecGroup / SpecFile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_cls,kwargs",
    [
        (
            StatementSpec,
            {
                "id": "DP-01-001",
                "priority": RFC2119Priority.MUST,
                "statement": "DP-01-001 MUST document the dev process",
                "kind": SpecKind.PROCESS,
            },
        ),
    ],
    ids=["StatementSpec"],
)
def test_process_kind_round_trip(model_cls, kwargs):
    """kind: process round-trips through StatementSpec (AC-1).

    SpecGroup and SpecFile no longer carry a kind field; kind lives on
    individual spec items only.
    """
    obj = model_cls(**kwargs)
    assert obj.kind == SpecKind.PROCESS
    assert obj.kind == "process"


# ---------------------------------------------------------------------------
# SpecFile with kind: dev-process passes load_registry (AC-3)
# ---------------------------------------------------------------------------


def test_load_registry_process_kind(tmp_path):
    """kind: process round-trips through load_registry; effective kind and priority are correct (AC-3)."""
    data = {
        "id": "DP",
        "title": "Process spec file",
        "description": "Spec file for process kind smoke test",
        "version": "0.1",
        "scope": ["production"],
        "groups": [
            {
                "id": "DP-01",
                "title": "Process group",
                "specs": [
                    {
                        "id": "DP-01-001",
                        "priority": "MUST",
                        "kind": "process",
                        "statement": "DP-01-001 MUST document the dev process",
                        "rationale": "Ensures process specs are loadable",
                    }
                ],
            }
        ],
    }
    (tmp_path / "process.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    spec = registry.get("DP-01-001")
    assert registry.get_effective_kind("DP-01-001") == SpecKind.PROCESS
    assert spec.priority == RFC2119Priority.MUST
