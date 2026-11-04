"""Pydantic schema for the declarations in ``docs/`` page frontmatter.

They are the audience, the level, the page type and the subject.

Schema requirements: specs/diataxis-requirements.yaml DF-11-001 (reader-facing
pages), DF-11-018 (page type), DF-11-025 (subject), DF-11-026 (no subject off
reader-facing pages), DF-11-012 (working-record pages), DF-11-003 (which pages
are working record), DF-11-013 (a start page's reading-path thread). Design
rationale: ``notes/site-information-architecture.md`` (ADR-0102, ADR-0136,
ADR-0150).

This module is the single machine source for the ``stakeholder_type`` members,
the ``level`` ladder, the ``page_type`` values and the ``subject`` values.
Anything that needs one —
the validator in :mod:`vultron.metadata.docs.page_frontmatter`, the generated
``docs/includes/stakeholder_types.md`` fragment (DF-11-011), the coverage
matrix (DF-11-008), the page-type badge's tests — imports
:class:`StakeholderType`, :data:`LEVELS`, :data:`AUDIENCE_DESCRIPTIONS`,
:class:`PageType`, :data:`PAGE_TYPE_BADGES` and :class:`Subject` rather than
restating them.

Submodules, by concern: ``frontmatter`` (reader-facing page frontmatter),
``working_record`` (working-record frontmatter and paths) and ``thread``
(the ``thread:`` declaration of a start page).
"""

from vultron.metadata.docs.page_schema.frontmatter import (
    ALL_STAKEHOLDERS,
    AUDIENCE_DESCRIPTIONS,
    AUDIENCE_KEYS,
    LEVELS,
    PAGE_TYPE_BADGES,
    AudienceDeclaration,
    AudienceDescription,
    PageFrontmatter,
    PageType,
    StakeholderType,
    Subject,
    declared_subject,
)
from vultron.metadata.docs.page_schema.thread import (
    START_DIR,
    THREAD_KEY,
    StageKind,
    ThreadDeclaration,
    ThreadMember,
    ThreadStage,
    is_start_page,
)
from vultron.metadata.docs.page_schema.working_record import (
    WorkingRecordFrontmatter,
    WorkingRecordStakeholderTypes,
    is_working_record,
)

__all__ = [
    "ALL_STAKEHOLDERS",
    "AUDIENCE_DESCRIPTIONS",
    "AUDIENCE_KEYS",
    "AudienceDeclaration",
    "AudienceDescription",
    "LEVELS",
    "PAGE_TYPE_BADGES",
    "PageFrontmatter",
    "PageType",
    "START_DIR",
    "StageKind",
    "StakeholderType",
    "Subject",
    "THREAD_KEY",
    "ThreadDeclaration",
    "ThreadMember",
    "ThreadStage",
    "WorkingRecordFrontmatter",
    "WorkingRecordStakeholderTypes",
    "declared_subject",
    "is_start_page",
    "is_working_record",
]
