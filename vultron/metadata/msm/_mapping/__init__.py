"""MSM mapping facts derived from the occasions on ``SEMANTIC_REGISTRY``.

Each ``SemanticEntry`` declares its occasions and its message page (ADR-0128).
This module derives what the occasions already say, so nothing here is typed
by hand:

- the mapping status of an entry (MSM-06-003, MSM-08-006);
- the "Distinguished by" value of an occasion, the field value, state
  context or sender standing that tells it apart from its entry's other
  occasions;
- the "Sent by" value of an occasion, from the side of the sender rule its
  received use case declares that matches the occasion's addressee, worded by
  each kind (MSM-08-005, MSM-08-010);
- the "Send to" value of an occasion, from its addressee (MSM-08-009).

:class:`RowSpec` is the derived view of one entry that the MSM-06-002 ratchet
reads.

Submodules, by concern: ``status`` (mapping status, section headings and
row specs), ``wording`` (the "Sent by", "Send to" and "Distinguished by"
wording) and ``table`` (the occasion table model and its loader).
"""

from vultron.metadata.msm._mapping.status import (
    EXEMPTED_SEMANTICS,
    PAGE_SLUGS,
    ROW_SPECS,
    SEMANTICS_TO_ROW,
    MappingStatus,
    RowSpec,
    entry_shorthands,
    mapping_status,
    section_heading,
    shorthand_is_shared,
)
from vultron.metadata.msm._mapping.table import (
    OCCASION_TABLE_FORMAT_VERSION,
    OCCASION_TABLE_PATH,
    OccasionGroup,
    OccasionRow,
    OccasionTable,
    PageLink,
    load_occasion_table,
)
from vultron.metadata.msm._mapping.wording import (
    CASE_MANAGER_INTERNAL,
    NO_SENDER_CHECK,
    NOT_YET_CHECKED,
    answered_request,
    distinguished_by,
    rule_wording,
    send_to,
    sent_by,
)

__all__ = [
    "CASE_MANAGER_INTERNAL",
    "EXEMPTED_SEMANTICS",
    "MappingStatus",
    "NOT_YET_CHECKED",
    "NO_SENDER_CHECK",
    "OCCASION_TABLE_FORMAT_VERSION",
    "OCCASION_TABLE_PATH",
    "OccasionGroup",
    "OccasionRow",
    "OccasionTable",
    "PAGE_SLUGS",
    "PageLink",
    "ROW_SPECS",
    "RowSpec",
    "SEMANTICS_TO_ROW",
    "answered_request",
    "distinguished_by",
    "entry_shorthands",
    "load_occasion_table",
    "mapping_status",
    "rule_wording",
    "section_heading",
    "send_to",
    "sent_by",
    "shorthand_is_shared",
]
