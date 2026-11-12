"""Tests for vultron.metadata.specs.schema (SR.1.3).

Covers: SpecIdStr validation, StatementSpec, BehavioralSpec, SpecGroup,
SpecFile, SpecRegistry round-trip, and load_registry helpers.
"""

import uuid

import pytest
import yaml
from pydantic import ValidationError

from test.support.objects import with_times
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.metadata.specs.registry import load_registry
from vultron.metadata.specs.schema import (
    FOUNDATION_STANDARD_TAGS,
    RELATION_DEFINITIONS,
    AdrStatus,
    BehavioralSpec,
    BehaviorStep,
    LintWarningCode,
    Postcondition,
    Precondition,
    RelationEnd,
    Relationship,
    RelationType,
    RFC2119Priority,
    RFC2119Tier,
    Scope,
    SeeAlso,
    SpecFile,
    SpecGroup,
    SpecKind,
    SpecTag,
    StatementSpec,
    StoryIdStr,
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
        "AB-01-001b",  # lowercase suffix introduced in SpecIdStr regex update
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
        "AB-01-001B",  # uppercase suffix — only lowercase [a-z] is permitted
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
    """Optional fields default to None when not provided."""
    spec = StatementSpec(
        id="AB-01-001",
        priority=RFC2119Priority.MUST,
        statement="AB-01-001 MUST satisfy this",
        rationale="Because testing",
        kind=SpecKind.PROTOCOL,
    )
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


def test_statement_spec_extra_field_rejected():
    """ConfigDict(extra='forbid') rejects unknown fields (SR-02-022)."""
    with pytest.raises(ValidationError):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST do something",
            rationale="Because testing.",
            kind=SpecKind.PROTOCOL,
            unknown_field="should raise",  # type: ignore[call-arg]
        )


@pytest.mark.spec("SR-02-021")
@pytest.mark.parametrize("model", [StatementSpec, BehavioralSpec])
def test_statement_spec_optional_field_set(model):
    """The SR-02-021 annotations are optional fields; no lifecycle field exists.

    A superseded requirement is removed and archived, so no field marks one
    in place (MS-09-001).
    """
    optional = {
        "verification",
        "note",
        "tracking_issue",
        "verification_debt",
        "references",
        "exceptions",
        "trigger",
        "see_also",
    }
    fields = model.model_fields
    assert optional <= set(fields)
    assert not any(fields[name].is_required() for name in optional)
    assert not {"deprecated", "superseded_by"} & set(fields)


_SPEC_ITEM = {
    "id": "AB-01-001",
    "priority": "MUST",
    "statement": "AB-01-001 MUST do something",
    "rationale": "Because testing.",
    "kind": "protocol",
}


@pytest.mark.spec("SR-02-021")
def test_see_also_defaults_to_empty_and_loads_entries():
    bare = StatementSpec.model_validate(_SPEC_ITEM)
    listed = StatementSpec.model_validate(
        {
            **_SPEC_ITEM,
            "see_also": [{"spec_id": "AB-01-002", "reason": "an example"}],
        }
    )

    assert bare.see_also == []
    assert listed.see_also == [
        SeeAlso(spec_id="AB-01-002", reason="an example")
    ]


@pytest.mark.spec("SR-02-021")
@pytest.mark.parametrize(
    "entry",
    [
        {"spec_id": "AB-01-002"},
        {"spec_id": "AB-01-002", "reason": ""},
        {"spec_id": "not an id", "reason": "an example"},
        {"spec_id": "AB-01-002", "reason": "an example", "note": "extra"},
    ],
    ids=["no-reason", "empty-reason", "bad-id", "extra-key"],
)
def test_see_also_entry_refuses_a_malformed_entry(entry):
    with pytest.raises(ValidationError):
        SeeAlso.model_validate(entry)


@pytest.mark.spec("MS-09-001")
@pytest.mark.parametrize(
    "extra",
    [
        {"deprecated": True},
        {"superseded_by": "AB-01-002"},
        {
            "steps": [{"order": 1, "actor": "a", "action": "b"}],
            "deprecated": True,
        },
    ],
)
def test_lifecycle_key_refused_once_with_retirement_pointer(extra):
    """The refusal names the rule and the archive command, exactly once.

    Statement and behavioral items alike; the check runs before the ``Spec``
    union, so its two branches do not each repeat it.
    """
    with pytest.raises(ValidationError) as exc_info:
        SpecGroup.model_validate(
            {"id": "AB-01", "title": "T", "specs": [{**_SPEC_ITEM, **extra}]}
        )
    message = str(exc_info.value)
    key = "superseded_by" if "superseded_by" in extra else "deprecated"
    assert f"'{key}:'" in message
    assert message.count("uv run spec-retire AB-01-001") == 1
    assert "MS-09-001" in message


@pytest.mark.parametrize("model", [StatementSpec, BehavioralSpec])
def test_lifecycle_key_rejected_on_direct_model_construction(model):
    """Outside a group, ``extra="forbid"`` still refuses the key (SR-02-022)."""
    with pytest.raises(ValidationError):
        model.model_validate(
            with_times(model, {**_SPEC_ITEM, "deprecated": True})
        )


@pytest.mark.parametrize("specs", [["AB-01-001"], "AB-01-001"])
def test_non_mapping_spec_input_gets_the_model_type_error(specs):
    """A bare-string item or list fails as a type error, not as a refusal."""
    with pytest.raises(ValidationError) as exc_info:
        SpecGroup.model_validate({"id": "AB-01", "title": "T", "specs": specs})
    assert "spec-retire" not in str(exc_info.value)


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


def test_statement_spec_kind_omitted_rejected():
    """``kind`` is required on every requirement (SR-02-009)."""
    with pytest.raises(ValidationError, match="kind"):
        StatementSpec(  # type: ignore[call-arg]
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST satisfy this",
            rationale="Because testing.",
        )


@pytest.mark.spec("MS-10-012")
def test_statement_spec_rationale_omitted_rejected():
    """A requirement with no rationale fails validation (SR-02-009)."""
    with pytest.raises(ValidationError, match="rationale"):
        StatementSpec(  # type: ignore[call-arg]
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST satisfy this",
            kind=SpecKind.PROTOCOL,
        )


@pytest.mark.spec("MS-10-012")
def test_statement_spec_rationale_none_rejected():
    with pytest.raises(ValidationError, match="rationale"):
        StatementSpec(
            id="AB-01-001",
            priority=RFC2119Priority.MUST,
            statement="AB-01-001 MUST satisfy this",
            rationale=None,  # type: ignore[arg-type]
            kind=SpecKind.PROTOCOL,
        )


# ---------------------------------------------------------------------------
# Non-empty-if-present list validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "scope",
        "tags",
        "references",
        "exceptions",
        "relationships",
        "lint_suppress",
        "stories",
    ],
)
def test_empty_list_rejected(field: str) -> None:
    """Empty lists are rejected — use None for absent."""
    kwargs: dict = {
        "id": "AB-01-001",
        "priority": RFC2119Priority.MUST,
        "statement": "AB-01-001 MUST pass",
        "rationale": "Because testing.",
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
        "rationale": "Because testing.",
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
                    rationale="Because testing.",
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
                    rationale="Because testing.",
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
                rationale="Because testing.",
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
                    rationale="Because testing.",
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
                        rationale="Because testing.",
                        kind=SpecKind.PROTOCOL,
                    )
                ],
            )
        ],
    )
    assert sf.id == "AB"
    assert not hasattr(sf, "kind")


@pytest.mark.spec("SR-02-025")
def test_spec_file_rejects_version_field():
    with pytest.raises(ValidationError, match="version"):
        SpecFile.model_validate(
            {
                "id": "AB",
                "title": "Test File",
                "description": "A test file",
                "version": "1.0.0",
                "scope": ["production"],
                "groups": [
                    {
                        "id": "AB-01",
                        "title": "Group",
                        "specs": [
                            {
                                "id": "AB-01-001",
                                "priority": "MUST",
                                "statement": "AB-01-001 MUST work",
                                "rationale": "Because testing.",
                                "kind": "protocol",
                            }
                        ],
                    }
                ],
            }
        )


def test_spec_file_requires_scope():
    with pytest.raises(ValidationError):
        SpecFile(  # type: ignore[call-arg]
            id="AB",
            title="Test File",
            description="A test file",
            groups=[
                SpecGroup(
                    id="AB-01",
                    title="Group",
                    specs=[
                        StatementSpec(
                            id="AB-01-001",
                            priority=RFC2119Priority.MUST,
                            statement="AB-01-001 MUST work",
                            rationale="Because testing.",
                            kind=SpecKind.PROTOCOL,
                        )
                    ],
                )
            ],
        )


def _spec_file_kwargs() -> dict[str, object]:
    """A ``SpecFile`` that validates, for a test that empties one field."""
    return {
        "id": "AB",
        "title": "Test File",
        "description": "A test file",
        "scope": [Scope.PRODUCTION],
        "tags": [SpecTag.TESTING],
        "relationships": [
            Relationship(rel_type=RelationType.REFINES, spec_id="AB-01-002")
        ],
        "groups": [
            SpecGroup(
                id="AB-01",
                title="Group",
                specs=[
                    StatementSpec(
                        id="AB-01-001",
                        priority=RFC2119Priority.MUST,
                        statement="AB-01-001 MUST work",
                        rationale="Because testing.",
                        kind=SpecKind.PROTOCOL,
                    )
                ],
            )
        ],
    }


def test_spec_file_empty_scope_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        SpecFile.model_validate({**_spec_file_kwargs(), "scope": []})


def test_spec_file_empty_groups_rejected():
    with pytest.raises(ValidationError, match="must not be empty"):
        SpecFile.model_validate({**_spec_file_kwargs(), "groups": []})


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("tags", "tags must be non-empty if present"),
        ("relationships", "relationships must be non-empty if present"),
        ("scope", "scope must not be empty"),
        ("groups", "groups must not be empty"),
    ],
)
def test_an_empty_list_rejection_names_the_field(
    field: str, expected: str
) -> None:
    """Every empty-list rejection names the field, not "list field".

    Each optional-list validator carried its own copy of the rule, and the
    ``SpecFile.tags``/``relationships`` copy lost the field name because it
    never read it.  They now delegate to the one shared validator, so a
    lint failure on a spec file with sixty keys says which key to look at.

    Asserted on the message pydantic built, not on the whole
    ``ValidationError`` string: that string already carries the field's
    location on its own line, so ``match=field`` would pass against the old
    wording and pin nothing.
    """
    with pytest.raises(ValidationError) as raised:
        SpecFile.model_validate({**_spec_file_kwargs(), field: []})

    assert [error["msg"] for error in raised.value.errors()] == [
        f"Value error, {expected}"
    ]


# ---------------------------------------------------------------------------
# SpecRegistry / load_registry
# ---------------------------------------------------------------------------


def test_registry_duplicate_spec_id_raises(tmp_path):
    dup_data = {
        "id": "DUP",
        "title": "Dup File",
        "description": "Duplicate spec IDs",
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


def test_registry_get_file_id_names_the_holding_file(multi_spec_dir):
    registry = load_registry(multi_spec_dir)
    assert registry.get_file_id("TST-01-001") == "TST"
    assert registry.get_file_id("MOR-01-001") == "MOR"


def test_registry_get_file_id_raises_for_unknown_id(spec_dir):
    with pytest.raises(KeyError):
        load_registry(spec_dir).get_file_id("XX-99-999")


def test_reloading_an_unchanged_spec_dir_parses_each_file_once(
    multi_spec_dir, monkeypatch
):
    """A growth guard loads the tree twice; the second load re-parses
    nothing, yet the registries share no model (#5880)."""
    parsed: list[str] = []
    real_load = yaml.load

    def counting_load(stream, Loader):
        parsed.append(stream)
        return real_load(stream, Loader=Loader)

    # Unique text, so no earlier test in this process warmed the cache.
    for path in multi_spec_dir.glob("*.yaml"):
        path.write_text(path.read_text() + f"# {path.name} {uuid.uuid4()}\n")
    monkeypatch.setattr(yaml, "load", counting_load)
    first = load_registry(multi_spec_dir)
    second = load_registry(multi_spec_dir)
    assert len(parsed) == 2
    spec = first.get("TST-01-001")
    assert spec is not second.get("TST-01-001")
    assert spec.tags is not None
    spec.tags.clear()
    assert load_registry(multi_spec_dir).get("TST-01-001").tags


def test_reloading_an_edited_spec_file_sees_the_edit(spec_dir):
    """The cache is keyed by text, so a drift check sees an edit."""
    load_registry(spec_dir)
    path = next(spec_dir.glob("*.yaml"))
    path.write_text(path.read_text().replace("satisfy the test", "pass it"))
    assert load_registry(spec_dir).get("TST-01-001").statement == (
        "TST-01-001 MUST pass it"
    )


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
                        "rationale": "Because testing.",
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
                        "rationale": "Because testing.",
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
                        "rationale": "Because testing.",
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
                        "rationale": "Because testing.",
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
                        "rationale": "Because testing.",
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
# RelationType definitions (SR-13-001..011, SR-13-016, SR-13-017)
# ---------------------------------------------------------------------------


def _sr_13_definitions(registry) -> dict[str, str]:
    """SR-13 definition statements keyed by the type each one defines.

    A definition is the SR-13 statement that opens by naming one type in
    backticks and saying what a relationship of it recorded on A means.
    """
    return {
        spec.statement.split("`")[1]: " ".join(spec.statement.split())
        for spec_id, spec in registry.all_specs.items()
        if spec_id.startswith("SR-13-")
        and spec.statement.startswith(("A `", "An `"))
        and "relationship recorded on A naming B MUST mean"
        in " ".join(spec.statement.split())
    }


def test_every_relation_type_has_a_definition():
    assert set(RELATION_DEFINITIONS) == set(RelationType)
    for member in RelationType:
        assert member.definition.startswith(
            ("A `" + member.value, "An `" + member.value)
        )


def _end_named_by(statement: str) -> RelationEnd:
    """The upstream end an SR-13 definition names in its closing clause."""
    clause = statement.rsplit(";", 1)[1].strip()
    if clause.startswith("B is the"):
        return RelationEnd.TARGET
    if clause.startswith("A is the"):
        return RelationEnd.SOURCE
    assert clause == "neither end is upstream.", clause
    return RelationEnd.NEITHER


@pytest.mark.spec("SR-13-021")
@pytest.mark.spec_corpus
def test_upstream_end_matches_the_end_sr_13_names(real_registry):
    for value, statement in _sr_13_definitions(real_registry).items():
        assert RelationType(value).upstream_end is _end_named_by(statement)


@pytest.mark.spec("SR-13-021")
@pytest.mark.spec_corpus
def test_relation_definitions_match_sr_13(real_registry):
    assert _sr_13_definitions(real_registry) == {
        member.value: member.definition for member in RelationType
    }


@pytest.mark.spec("SR-13-016")
def test_relation_type_docstring_lists_every_definition():
    doc = " ".join((RelationType.__doc__ or "").split())
    for member in RelationType:
        assert f"``{member.value}``: {member.definition}" in doc


def test_only_constrains_and_conflicts_leave_the_target_upstream_end():
    assert {
        m for m in RelationType if m.upstream_end is not RelationEnd.TARGET
    } == {RelationType.CONSTRAINS, RelationType.CONFLICTS}


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
    t = Trigger(type=TriggerType.SCENARIO_START, value="rv")
    assert t.type == TriggerType.SCENARIO_START
    assert t.value == "rv"


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
                rationale="Because testing.",
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
                rationale="Because testing.",
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
        rationale="Because testing.",
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
                        "rationale": "Because testing.",
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


def test_spec_kind_contains_exactly_five_tiers():
    # SR-02-005 canary: catches silent removal or misspelling of any tier.
    expected = {
        "protocol",
        "foundation",
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
                "rationale": "Because testing.",
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


def test_load_registry_foundation_kind_with_standard_tag(tmp_path):
    """kind: foundation and its standard tag load through load_registry (ADR-0134)."""
    data = {
        "id": "FD",
        "title": "Foundation spec file",
        "description": "Spec file for foundation kind smoke test",
        "scope": ["production"],
        "groups": [
            {
                "id": "FD-01",
                "title": "Foundation group",
                "specs": [
                    {
                        "id": "FD-01-001",
                        "priority": "MUST",
                        "kind": "foundation",
                        "statement": "Object IDs MUST be treated as opaque URIs.",
                        "rationale": "Because testing.",
                        "tags": ["as2"],
                    }
                ],
            }
        ],
    }
    (tmp_path / "foundation.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    assert registry.get_effective_kind("FD-01-001") == SpecKind.FOUNDATION
    assert registry.get_effective_tags("FD-01-001") == [SpecTag.AS2]


def test_foundation_standard_tags_name_the_three_standards():
    """MS-12-009: the source-standard tags are exactly as2, activitypub, http."""
    assert {tag.value for tag in FOUNDATION_STANDARD_TAGS} == {
        "as2",
        "activitypub",
        "http",
    }
    assert set(SpecTag) >= FOUNDATION_STANDARD_TAGS


# ---------------------------------------------------------------------------
# AdrStatus vocabulary (MS-14-001, ADR-0043)
# ---------------------------------------------------------------------------


def test_adr_status_values():
    """AdrStatus enumerates exactly the valid ADR status vocabulary."""
    assert {s.value for s in AdrStatus} == {
        "proposed",
        "accepted",
        "accepted-provisional",
        "deprecated",
        "rejected",
        "superseded",
    }


def test_adr_status_lookup_by_value():
    """String values round-trip to enum members (used by the linter)."""
    assert AdrStatus("accepted-provisional") is AdrStatus.ACCEPTED_PROVISIONAL
    assert AdrStatus("superseded") is AdrStatus.SUPERSEDED


def test_adr_status_rejects_unknown():
    """An unknown status value is not a member (linter raises MS-14-001)."""
    with pytest.raises(ValueError):
        AdrStatus("kinda-accepted")


# ---------------------------------------------------------------------------
# Structured adr: field (SR-02-020)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("adr_id", ["ADR-0001", "ADR-0043", "ADR-9999"])
def test_statement_spec_adr_field_valid(adr_id):
    spec = StatementSpec(
        id="TST-01-001",
        priority=RFC2119Priority.MUST,
        kind=SpecKind.PROCESS,
        statement="TST-01-001 MUST do the thing",
        rationale="Because testing.",
        adr=[adr_id],
    )
    assert spec.adr == [adr_id]


@pytest.mark.parametrize("adr_id", ["ADR-1", "ADR-00001", "0043", "adr-0043"])
def test_statement_spec_adr_field_invalid_pattern(adr_id):
    with pytest.raises(ValidationError):
        StatementSpec(
            id="TST-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROCESS,
            statement="TST-01-001 MUST do the thing",
            rationale="Because testing.",
            adr=[adr_id],
        )


def test_statement_spec_adr_field_empty_list_rejected():
    with pytest.raises(ValidationError):
        StatementSpec(
            id="TST-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROCESS,
            statement="TST-01-001 MUST do the thing",
            rationale="Because testing.",
            adr=[],
        )


# ---------------------------------------------------------------------------
# StoryIdStr pattern (SR-11-002)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "story_id",
    ["story_2022_001", "story_2022_042", "story_2022_999", "story_9999_000"],
)
def test_story_id_str_valid(story_id):
    spec = StatementSpec(
        id="TST-01-001",
        priority=RFC2119Priority.MUST,
        kind=SpecKind.PROTOCOL,
        statement="TST-01-001 MUST do the thing",
        rationale="Because testing.",
        stories=[story_id],
    )
    assert spec.stories == [story_id]


@pytest.mark.parametrize(
    "story_id",
    [
        "story_22_001",  # year only 2 digits
        "story_2022_01",  # seq only 2 digits
        "story_2022_0001",  # seq 4 digits
        "STORY_2022_001",  # uppercase prefix
        "story-2022-001",  # dashes instead of underscores
        "2022_001",  # missing 'story_' prefix
        "",  # empty
    ],
)
def test_story_id_str_invalid(story_id):
    with pytest.raises(ValidationError):
        StatementSpec(
            id="TST-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="TST-01-001 MUST do the thing",
            rationale="Because testing.",
            stories=[story_id],
        )


# ---------------------------------------------------------------------------
# stories: field on StatementSpec (SR-11-001)
# ---------------------------------------------------------------------------


def test_statement_spec_stories_defaults_to_none():
    spec = StatementSpec(
        id="TST-01-001",
        priority=RFC2119Priority.MUST,
        kind=SpecKind.PROTOCOL,
        statement="TST-01-001 MUST do the thing",
        rationale="Because testing.",
    )
    assert spec.stories is None


def test_statement_spec_stories_round_trip():
    spec = StatementSpec(
        id="TST-01-001",
        priority=RFC2119Priority.MUST,
        kind=SpecKind.PROTOCOL,
        statement="TST-01-001 MUST do the thing",
        rationale="Because testing.",
        stories=["story_2022_001", "story_2022_042"],
    )
    assert spec.stories == ["story_2022_001", "story_2022_042"]


def test_statement_spec_stories_empty_list_rejected():
    with pytest.raises(ValidationError, match="non-empty"):
        StatementSpec(
            id="TST-01-001",
            priority=RFC2119Priority.MUST,
            kind=SpecKind.PROTOCOL,
            statement="TST-01-001 MUST do the thing",
            rationale="Because testing.",
            stories=[],
        )


def test_statement_spec_stories_none_allowed():
    spec = StatementSpec(
        id="TST-01-001",
        priority=RFC2119Priority.MUST,
        kind=SpecKind.PROTOCOL,
        statement="TST-01-001 MUST do the thing",
        rationale="Because testing.",
        stories=None,
    )
    assert spec.stories is None


def test_statement_spec_stories_yaml_round_trip(tmp_path):
    """stories: field round-trips through YAML load_registry."""
    data = {
        "id": "TST",
        "title": "Test",
        "description": "Test",
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
                        "statement": "TST-01-001 MUST do the thing",
                        "rationale": "Because testing.",
                        "stories": ["story_2022_001", "story_2022_042"],
                    }
                ],
            }
        ],
    }
    (tmp_path / "test.yaml").write_text(yaml.dump(data))
    registry = load_registry(tmp_path)
    spec = registry.get("TST-01-001")
    assert spec.stories == ["story_2022_001", "story_2022_042"]


def test_story_id_str_type_is_exported():
    """StoryIdStr is importable from schema (SR-11-002)."""
    assert StoryIdStr is not None


# ---------------------------------------------------------------------------
# RFC2119Priority.tier — the shared tiering (MS-02-003, MS-02-004)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("priority", "tier", "is_must"),
    [
        (RFC2119Priority.MUST, RFC2119Tier.MUST, True),
        (RFC2119Priority.MUST_NOT, RFC2119Tier.MUST, True),
        (RFC2119Priority.SHOULD, RFC2119Tier.SHOULD, False),
        (RFC2119Priority.SHOULD_NOT, RFC2119Tier.SHOULD, False),
        (RFC2119Priority.MAY, RFC2119Tier.MAY, False),
    ],
)
@pytest.mark.spec("MS-02-004")
def test_priority_tier_pairs_each_negation_with_its_positive(
    priority, tier, is_must
):
    """A negative keyword is the same tier as its positive (MS-02-003)."""
    assert priority.tier is tier
    assert priority.is_must_tier is is_must


@pytest.mark.spec("MS-02-004")
def test_priority_tier_mapping_is_total():
    """Every member has a tier (a missing one raises KeyError here, not at the
    first spec that carries it) and every tier has a member."""
    assert {p.tier for p in RFC2119Priority} == set(RFC2119Tier)
