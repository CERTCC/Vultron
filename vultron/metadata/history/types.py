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
