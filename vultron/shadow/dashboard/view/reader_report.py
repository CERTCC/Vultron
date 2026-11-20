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


"""The case reader's report, shown beside the analysis: the facts it could
not translate (SHD-01-004), the states and times it inferred (CRD-02-002),
and the facts its source never records (CRD-02-005).
"""

from __future__ import annotations

from vultron.core.models.case_reading import CaseReading
from vultron.core.states.cs_invariants import CSEvent
from vultron.shadow.dashboard.view.labels import EVENT_LABELS, Row

#: What an untranslated or unobservable fact means for the scores.
NOT_TRANSLATED_NOTE = (
    "The case reader could not translate these facts, so the states and"
    " scores above do not count them."
)
UNOBSERVABLE_NOTE = (
    "The source never records these facts, so the page reads each one as"
    " unknown, not as false."
)


def untranslated_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the case reader could not translate (SHD-01-004)."""
    return [
        {
            "Source record": fact.source_record,
            "Fact": fact.fact,
            "Why": fact.reason.value.replace("_", " "),
        }
        for fact in reading.untranslated
    ]


def inference_rows(reading: CaseReading) -> list[Row]:
    """One row per state or time the source implied (CRD-02-002)."""
    return [
        {
            "Entry": inference.entry_id,
            "Rule": inference.rule_id,
            "Caveat": inference.caveat,
        }
        for inference in reading.inferences
    ]


def unobservable_rows(reading: CaseReading) -> list[Row]:
    """One row per fact the source never records, with the case-state
    events it makes the page read as unknown (CRD-02-005)."""
    return [
        {
            "Fact": fact.fact,
            "Why": fact.why,
            "Reads as unknown": ", ".join(
                EVENT_LABELS[event]
                for event in CSEvent
                if event in fact.events
            )
            or "—",
        }
        for fact in reading.unobservable
    ]


__all__ = [
    "NOT_TRANSLATED_NOTE",
    "UNOBSERVABLE_NOTE",
    "inference_rows",
    "unobservable_rows",
    "untranslated_rows",
]
