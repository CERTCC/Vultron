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

"""A case reading built from a Vultron case ledger's parsed rows (#6530).

Both Vultron case readers, the one over a case-ledger file and the one over a
running node, get the same thing from their source: case-ledger JSONL text,
untranslated.  :func:`ledger_reading` turns its parsed rows into a
:class:`~vultron.core.models.case_reading.CaseReading`, so the two readers
make one set of checks (CS-22-001).

Each entry cites itself, by its ledger id, as its source record: a native
entry has no outside record behind it (CRD-01-004).  The reading carries no
inferences and no untranslated facts.

A row that is not a valid ledger entry refuses the whole reading, never only
the row, so a reading is never a partial ledger that looks whole.  Every
problem found is reported, not only the first (EH-07-001).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from operator import attrgetter

from pydantic import ValidationError

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    UnobservableFact,
    ledger_problems,
)
from vultron.measure.ledger import LedgerFile, UnusableRow

#: The problem reported for a source that holds no row at all.
NO_ENTRY = "it holds no ledger entry"


def _summary(exc: ValidationError) -> str:
    """*exc*'s errors on one line, each with the field it is about."""
    return "; ".join(
        (
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            if error["loc"]
            else error["msg"]
        )
        for error in exc.errors()
    )


def ledger_reading(
    ledger: LedgerFile,
    *,
    unobservable: Sequence[UnobservableFact],
    refuse: Callable[[list[str]], Exception],
) -> CaseReading:
    """The case reading *ledger*'s rows make, or the reader's refusal.

    Args:
        ledger: The parsed rows of the source's case-ledger JSONL, with the
            rows that did not parse.
        unobservable: The reader's declaration of what its source cannot
            observe, copied into the reading (CRD-02-004).
        refuse: Builds the reader's own error from every problem found; it
            names the source, which this function does not know.

    Raises:
        Exception: The error *refuse* builds, when a row is not a valid
            ledger entry, the source holds no row, or the entries are not
            one case's ledger in log-index order.  Each problem with a row
            names it.
    """
    bad_rows: list[UnusableRow] = list(ledger.unusable_rows)
    entries: list[CaseLedgerEntry] = []
    for row in ledger.rows:
        try:
            entries.append(CaseLedgerEntry.model_validate(row.data))
        except ValidationError as exc:
            bad_rows.append(
                row.unusable(f"not a case ledger entry: {_summary(exc)}")
            )
    problems = [
        row.describe() for row in sorted(bad_rows, key=attrgetter("line"))
    ]
    # The citations are built one per entry, so only the ledger can
    # disagree with itself (EH-07-002).
    problems += ledger_problems(entries)
    if not entries and not bad_rows:
        problems.append(NO_ENTRY)
    if problems:
        raise refuse(problems)
    return CaseReading(
        ledger=tuple(entries),
        citations=tuple(
            EntryCitation(entry_id=entry.id_, source_record=entry.id_)
            for entry in entries
        ),
        unobservable=tuple(unobservable),
    )


__all__ = ["NO_ENTRY", "ledger_reading"]
