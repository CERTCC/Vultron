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

"""A case reading's standing: what the dashboard shows for one case.

A :class:`~vultron.core.models.case_reading.CaseReading` holds its ledger as
core :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry` objects;
the measure layer reads a case from ledger rows.  :func:`reading_ledger`
turns the one into the other, and :func:`analyse` reads the standing record
(:func:`~vultron.measure.standing.case_standing`) from it, so the dashboard
shows the reader's own result beside the analysis (SHD-01-004).  It reads
the case narrative from the same ledger
(:func:`~vultron.measure.history.case_narrative`): one line per entry,
naming who did what, when, and which states the entry changed.

A reading is already one case's ledger in log-index order, refused whole
otherwise (CRD-02-001), so the rows it yields are one complete copy.
Nothing here is written anywhere: the rows live only for the request
(SHD-01-003).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models.case_reading import CaseReading
from vultron.measure.history import (
    NarrativeLine,
    case_narrative,
    derive_case_steps,
)
from vultron.measure.ledger import (
    CaseLedger,
    LedgerFile,
    LedgerRow,
    case_ledgers_from_files,
    collect_actor_names,
)
from vultron.measure.standing import StandingRecord, case_standing

#: The name a reading's rows carry as their source.  No file is opened: the
#: measure layer names every row's source, and a reading has none on disk.
READING_SOURCE = Path("<case reading>")


def _rows(reading: CaseReading) -> list[LedgerRow]:
    return [
        LedgerRow(
            path=READING_SOURCE,
            line=line,
            data=entry.model_dump(by_alias=True, mode="json"),
        )
        for line, entry in enumerate(reading.ledger, start=1)
    ]


def reading_ledger(reading: CaseReading) -> CaseLedger | None:
    """*reading*'s ledger as the measure layer reads a case.

    Returns:
        The case's ledger, or ``None`` when the reading holds no entry, as
        an outside-system reading that translated nothing does.
    """
    if not reading.ledger:
        return None
    read = case_ledgers_from_files(
        [LedgerFile(path=READING_SOURCE, rows=_rows(reading))]
    )
    return read.cases[reading.ledger[0].case_id]


class CaseAnalysis(BaseModel):
    """One case reading, and the standing the dashboard reads from it.

    Fields:
        reading: The case reading, as the case reader returned it.
        standing: Where the case stands at its last entry; ``None`` when the
            reading holds no ledger entry to read it from.
        actor_names: The display name each actor's payload gives it, by
            actor id, for labels that read better than a URI.
        narrative: The case narrative: one line per ledger entry of the
            reading, in log-index order; empty when the reading holds none.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reading: CaseReading
    standing: StandingRecord | None
    actor_names: dict[str, str] = Field(default_factory=dict)
    narrative: tuple[NarrativeLine, ...] = ()


def analyse(reading: CaseReading) -> CaseAnalysis:
    """Read *reading*'s standing record (ADR-0190, level 1).

    Each case-state event the reading declares unobservable is read as
    unknown, never as not happened (CRD-02-005): a desideratum that orders
    one is unknown, and a move whose change rests on one carries a reason
    instead of a number.
    """
    ledger = reading_ledger(reading)
    if ledger is None:
        return CaseAnalysis(reading=reading, standing=None)
    # One walk of the ledger serves both the standing and the narrative.
    history, steps = derive_case_steps(ledger)
    return CaseAnalysis(
        reading=reading,
        standing=case_standing(
            ledger, reading.unobservable_events, derived=(history, steps[-1])
        ),
        actor_names=collect_actor_names({ledger.case_id: ledger.entries}),
        narrative=case_narrative(ledger, (history, steps)),
    )


__all__ = ["READING_SOURCE", "CaseAnalysis", "analyse", "reading_ledger"]
