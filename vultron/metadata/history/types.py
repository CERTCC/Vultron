"""HistoryEntryType StrEnum for the append-history tool.

Adding a new history entry type requires only adding a member here.
See ``specs/history-management.yaml`` HM-02-002.
"""

from __future__ import annotations

from enum import StrEnum


class HistoryEntryType(StrEnum):
    """Valid ``<type>`` values for the ``append-history`` command."""

    idea = "idea"
    implementation = "implementation"
    learning = "learning"
    note = "note"
    priority = "priority"


class LearningSignalType(StrEnum):
    """Optional signal classification for ``learning`` history entries (BW-07-002).

    Tags the urgency tier of a learning so the ``learn`` skill can triage
    without reading every file body.  ``spec-gap`` and ``spec-contradiction``
    are the highest priority (BW-07-003).

    The four ``RETIRED_SIGNALS`` values are accepted only so that entries
    archived before the BW-07 routing change remain parseable.  New entries
    must not use them: those findings are now routed to a GitHub issue or an
    in-session fix at the moment of discovery (BW-07-004).
    """

    spec_gap = "spec-gap"
    spec_ambiguity = "spec-ambiguity"
    spec_contradiction = "spec-contradiction"
    theme_candidate = "theme-candidate"
    # Retired (BW-07-002) — preserved for historical entries only.
    design_question = "design-question"
    concern = "concern"
    tooling_issue = "tooling-issue"
    process_issue = "process-issue"


RETIRED_SIGNALS: frozenset[LearningSignalType] = frozenset(
    {
        LearningSignalType.design_question,
        LearningSignalType.concern,
        LearningSignalType.tooling_issue,
        LearningSignalType.process_issue,
    }
)
