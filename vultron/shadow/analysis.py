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

The case as it stood at an earlier point is the same computation over a
prefix of the reading: :func:`reading_prefix` keeps the reading's first
entries, and :func:`analyse_prefix` analyses that, so the standing at a
point is the standing of a reading that holds only those entries (#6671).
:func:`point_analysis` is that analysis as the dashboard shows it at a
picked entry.  :func:`prefix_advice` is the move advice for a prefix, for a
caller that grades an entry against the advice open before it.

A reading is already one case's ledger in log-index order, refused whole
otherwise (CRD-02-001), so the rows it yields are one complete copy.
Nothing here is written anywhere: the rows live only for the request
(SHD-01-003).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from vultron.core.models.case_reading import CaseReading
from vultron.measure.advice import CaseAdvice, case_advice
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
        narrative=case_narrative(ledger, derived=(history, steps)),
    )


def reading_prefix(reading: CaseReading, count: int) -> CaseReading:
    """*reading* as if it held only its first *count* ledger entries.

    Each kept entry keeps its citation and its inferences.  The facts the
    reader could not translate and its declaration of what the source cannot
    observe are kept whole: neither belongs to an entry, and an unobservable
    event still reads as unknown at every point (CRD-02-005).

    Raises:
        ValueError: When *count* is negative or more than the reading's
            entries.
    """
    if not 0 <= count <= len(reading.ledger):
        raise ValueError(
            f"A prefix of a reading with {len(reading.ledger)} ledger"
            f" entries cannot hold {count}"
        )
    ledger = reading.ledger[:count]
    kept = {entry.id_ for entry in ledger}
    return CaseReading(
        ledger=ledger,
        citations=tuple(c for c in reading.citations if c.entry_id in kept),
        inferences=tuple(i for i in reading.inferences if i.entry_id in kept),
        untranslated=reading.untranslated,
        unobservable=reading.unobservable,
    )


def count_through(reading: CaseReading, log_index: int) -> int:
    """How many of *reading*'s entries come up to and including the entry
    at *log_index*: the prefix that ends with that entry.

    Raises:
        ValueError: When no entry of the reading has *log_index*.
    """
    for count, entry in enumerate(reading.ledger, start=1):
        if entry.log_index == log_index:
            return count
    raise ValueError(f"The reading holds no ledger entry at {log_index}")


def analyse_prefix(reading: CaseReading, count: int) -> CaseAnalysis:
    """The analysis of *reading*'s first *count* entries alone.

    The same computation as :func:`analyse`, over
    :func:`reading_prefix`: the standing is where the case stood just after
    its *count*-th entry, read from those entries only, and a hole after
    them does not reach it.  A *count* of 0 is the reading before its first
    entry, which has no standing.

    Raises:
        ValueError: When *count* is negative or more than the reading's
            entries.
    """
    return analyse(reading_prefix(reading, count))


def point_analysis(analysis: CaseAnalysis, log_index: int) -> CaseAnalysis:
    """*analysis* at the point just after its entry at *log_index*.

    The standing and narrative are :func:`analyse_prefix`'s, over the
    entries up to and including that one.  The actors keep the names the
    whole reading gives them, so a participant an earlier entry names only
    by its id reads as the rest of the page names it (DRPT-03-007).

    Raises:
        ValueError: When no entry of the reading has *log_index*.
    """
    reading = analysis.reading
    at_point = analyse_prefix(reading, count_through(reading, log_index))
    return at_point.model_copy(update={"actor_names": analysis.actor_names})


def prefix_advice(reading: CaseReading, count: int) -> CaseAdvice | None:
    """The move advice open just after *reading*'s *count*-th entry.

    The advice of :func:`analyse_prefix`'s standing (ADR-0200), so the moves
    open before an entry are ``prefix_advice(reading, i)`` for the entry at
    position *i* (from 0).  A prefix with a hole yields only the hole.

    Returns:
        The advice, or ``None`` for the prefix that holds no entry, which
        has no standing to advise from.

    Raises:
        ValueError: When *count* is negative or more than the reading's
            entries.
    """
    standing = analyse_prefix(reading, count).standing
    return None if standing is None else case_advice(standing)


__all__ = [
    "READING_SOURCE",
    "CaseAnalysis",
    "analyse",
    "analyse_prefix",
    "count_through",
    "point_analysis",
    "prefix_advice",
    "reading_ledger",
    "reading_prefix",
]
