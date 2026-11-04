"""Pydantic schema for ``specs/*.yaml`` structured requirement files.

Schema requirements: specs/spec-registry.yaml SR-02.

Design principle: YAML is the authoritative data source.  The schema
validates what is present but does **not** silently inject defaults for
absent fields.  ``kind`` is required on every individual spec item;
``scope`` is required at the file level and optional at the group level.

Submodules, by concern: ``ids`` (requirement, ADR, story and issue identifier
shapes and citation parsing), ``vocabulary`` (the controlled-vocabulary
enums and relation definitions) and ``models`` (the Pydantic models for a
spec file, its groups and its items).
"""

from vultron.metadata.specs.schema.ids import (
    SPEC_GROUP_PATTERN,
    SPEC_ID_CITATION_RE,
    SPEC_ID_PATTERN,
    STORY_ID_PATTERN,
    AdrIdStr,
    IssueRefStr,
    SpecIdStr,
    StoryIdStr,
    cited_spec_ids,
)
from vultron.metadata.specs.schema.models import (
    BehavioralSpec,
    BehaviorStep,
    Postcondition,
    Precondition,
    Relationship,
    Spec,
    SpecFile,
    SpecGroup,
    StatementSpec,
    Trigger,
)
from vultron.metadata.specs.schema.vocabulary import (
    FOUNDATION_STANDARD_TAGS,
    IMPLEMENTER_KINDS,
    RELATION_DEFINITIONS,
    AdrStatus,
    LintWarningCode,
    RelationEnd,
    RelationType,
    RFC2119Priority,
    RFC2119Tier,
    Scope,
    SpecKind,
    SpecTag,
    TriggerType,
)

__all__ = [
    "AdrIdStr",
    "AdrStatus",
    "BehaviorStep",
    "BehavioralSpec",
    "FOUNDATION_STANDARD_TAGS",
    "IMPLEMENTER_KINDS",
    "IssueRefStr",
    "LintWarningCode",
    "Postcondition",
    "Precondition",
    "RELATION_DEFINITIONS",
    "RFC2119Priority",
    "RFC2119Tier",
    "RelationEnd",
    "RelationType",
    "Relationship",
    "SPEC_GROUP_PATTERN",
    "SPEC_ID_CITATION_RE",
    "SPEC_ID_PATTERN",
    "STORY_ID_PATTERN",
    "Scope",
    "Spec",
    "SpecFile",
    "SpecGroup",
    "SpecIdStr",
    "SpecKind",
    "SpecTag",
    "StatementSpec",
    "StoryIdStr",
    "Trigger",
    "TriggerType",
    "cited_spec_ids",
]
