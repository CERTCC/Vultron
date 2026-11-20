#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University


"""The point picker's words: the points an analyst can pick on the case
narrative, each by its ``#`` and activity, and what the page says above a
picked point's scoreboard (#6671).
"""

from __future__ import annotations

from collections.abc import Sequence

from vultron.measure.history import NarrativeLine

#: The point picker's option for the case as it stands at its last entry,
#: which a followed case moves on with.  No log index is negative.
LATEST_POINT = -1

#: What the point picker says of :data:`LATEST_POINT`.
LATEST_POINT_LABEL = "Now: the latest entry, moving on as entries arrive"


def point_options(lines: Sequence[NarrativeLine]) -> list[int]:
    """The points the analyst can pick: now, then each narrative line's log
    index, in ledger order."""
    return [LATEST_POINT, *(line.log_index for line in lines)]


def point_label(log_index: int, lines: Sequence[NarrativeLine]) -> str:
    """The point picker's words for the point at *log_index*.

    A line reads as its ``#`` and its activity, as the narrative table reads
    it, so it names its actor by display name (DRPT-03-009).
    """
    if log_index == LATEST_POINT:
        return LATEST_POINT_LABEL
    for line in lines:
        if line.log_index == log_index:
            return f"#{line.log_index} · {line.phrase}"
    raise ValueError(f"The narrative holds no line at {log_index}")


def point_note(log_index: int, lines: Sequence[NarrativeLine]) -> str:
    """What the page says above a picked point's scoreboard."""
    shown = sum(1 for line in lines if line.log_index <= log_index)
    return (
        f"Showing the case as it stood just after entry #{log_index}: its"
        f" states, desiderata and move advice read from its first {shown}"
        f" of {len(lines)} entries only. New entries add narrative lines,"
        " and the point stays put; pick Now to see where the case stands."
    )


__all__ = [
    "LATEST_POINT",
    "LATEST_POINT_LABEL",
    "point_label",
    "point_note",
    "point_options",
]
