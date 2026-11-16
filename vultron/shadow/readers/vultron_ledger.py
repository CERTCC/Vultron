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

"""The Vultron case reader: a case-ledger file, read as it is (#6441).

A Vultron case needs no translation: a CASE_MANAGER's case ledger is already
the case ledger a :class:`~vultron.core.ports.case_reader.CaseReader`
returns (ADR-0191).  This reader takes the path of a case-ledger JSONL file,
such as a demo run's dump or a committed recording, as its case id and
returns every entry of the file, unchanged and in file order.

Each entry cites itself, by its ledger id, as its source record: a native
entry has no outside record behind it (CRD-01-004).  The reading carries no
inferences, no untranslated facts and declares nothing unobservable, so the
dashboard shows the full display for a source with nothing left untranslated.

The file is read with the measure layer's
:func:`~vultron.measure.ledger.read_ledger_file`.  That reader degrades a
malformed row and reads the rest (CEH-02-008); this one refuses the whole
file instead, naming the file and every bad row, so a case reading is never
a partial ledger.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import ValidationError

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    UnobservableFact,
)
from vultron.errors import CaseLedgerFileError, LedgerReadError
from vultron.measure.ledger import UnusableRow, read_ledger_file

logger = logging.getLogger(__name__)


def _summary(exc: ValidationError) -> str:
    """*exc*'s errors on one line, each with the field it is about."""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc']) or 'entry'}: "
        f"{error['msg']}"
        for error in exc.errors()
    )


class VultronCaseReader:
    """A ``CaseReader`` over a Vultron case-ledger JSONL file.

    The case id it is given is the file's path.  It reads the file on every
    request and keeps nothing between requests (ADR-0190 rule 3).
    """

    name = "vultron"
    #: A Vultron ledger records every act the protocol defines, so nothing
    #: is declared unobservable (CRD-02-004).
    unobservable: tuple[UnobservableFact, ...] = ()

    def read_case(self, case_id: str) -> CaseReading:
        """Read the case ledger in the file at path *case_id*.

        Raises:
            CaseLedgerFileError: The file is missing or unreadable, holds no
                ledger entry, holds a row that is not a valid ledger entry,
                or holds entries that are not one case's ledger in
                log-index order.  The error names the file and every
                problem found.
        """
        path = Path(case_id)
        try:
            ledger_file = read_ledger_file(path)
        except LedgerReadError as exc:
            raise CaseLedgerFileError(case_id, [str(exc)]) from exc

        bad_rows: list[UnusableRow] = list(ledger_file.unusable_rows)
        entries: list[CaseLedgerEntry] = []
        for row in ledger_file.rows:
            try:
                entries.append(CaseLedgerEntry.model_validate(row.data))
            except ValidationError as exc:
                bad_rows.append(
                    row.unusable(f"not a case ledger entry: {_summary(exc)}")
                )
        if bad_rows:
            raise CaseLedgerFileError(
                case_id,
                [row.describe() for row in sorted(bad_rows, key=_line)],
            )
        if not entries:
            raise CaseLedgerFileError(case_id, ["it holds no ledger entry"])

        try:
            reading = CaseReading(
                ledger=tuple(entries),
                citations=tuple(
                    EntryCitation(entry_id=entry.id_, source_record=entry.id_)
                    for entry in entries
                ),
                unobservable=self.unobservable,
            )
        except ValidationError as exc:
            raise CaseLedgerFileError(case_id, [_summary(exc)]) from exc
        logger.info(
            "Read case %s: %d ledger entries from %s",
            entries[0].case_id,
            len(entries),
            path,
        )
        return reading


def _line(row: UnusableRow) -> int:
    return row.line


__all__ = ["VultronCaseReader"]
