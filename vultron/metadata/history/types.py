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
    priority = "priority"


class LearningSignalType(StrEnum):
    """Optional signal classification for ``learning`` history entries (BW-07-002).

    Tags the urgency tier of a learning so the ``learn`` skill can triage
    without reading every file body.  ``spec-gap`` and ``spec-contradiction``
    are the highest priority (BW-07-003).
    """

    spec_gap = "spec-gap"
    spec_ambiguity = "spec-ambiguity"
    spec_contradiction = "spec-contradiction"
    design_question = "design-question"
    concern = "concern"
    tooling_issue = "tooling-issue"
    process_issue = "process-issue"
