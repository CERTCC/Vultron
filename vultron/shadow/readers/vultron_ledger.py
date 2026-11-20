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
The reading is built by
:func:`~vultron.shadow.readers.ledger_reading.ledger_reading`, which the live
reader over a running node shares.

The file is read with the measure layer's
:func:`~vultron.measure.ledger.read_ledger_file`.  That reader degrades a
malformed row and reads the rest (CEH-02-008); this one refuses the whole
file instead, naming the file and every bad row, so a case reading is never
a partial ledger.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from vultron.core.models.case_reading import CaseReading, UnobservableFact
from vultron.errors import CaseLedgerFileError, LedgerReadError
from vultron.measure.ledger import read_ledger_file
from vultron.shadow.readers.ledger_reading import (
    _summary,  # noqa: F401  # its tests import it from here
    ledger_reading,
)

logger = logging.getLogger(__name__)


class VultronCaseReader:
    """A ``CaseReader`` over a Vultron case-ledger JSONL file.

    The case id it is given is the file's path.  It reads the file on every
    request and leaves nothing on the host after its process exits (SHD-01-003).

    Args:
        root: The directory every requested file must resolve inside,
            symbolic links followed; a path outside it is refused before it
            is opened, so an analyst's input cannot probe the host's other
            files.  A relative case id is taken relative to it.  When it is
            ``None`` the working directory at construction is the root.
    """

    name = "vultron"
    #: A Vultron ledger records every act the protocol defines, so nothing
    #: is declared unobservable (CRD-02-004).
    unobservable: tuple[UnobservableFact, ...] = ()

    def __init__(self, root: Path | None = None) -> None:
        # The root as a real path, symbolic links resolved, so the check in
        # _confined compares two real paths.
        self._root = os.path.realpath(root if root is not None else Path.cwd())

    def _confined(self, case_id: str) -> Path:
        """The path to open for *case_id*, refused if outside the root.

        Every read is confined: a case id may come from a page an analyst
        types into, so no path reaches the file system unchecked.
        """
        try:
            path = os.path.realpath(os.path.join(self._root, case_id))
        except (OSError, ValueError) as exc:
            raise CaseLedgerFileError(
                case_id, [f"it is not a usable path: {exc}"]
            ) from exc
        # Only a path strictly under the root passes: the root itself is a
        # directory, never a ledger file.
        inside = self._root.rstrip(os.sep) + os.sep
        if not path.startswith(inside):
            raise CaseLedgerFileError(
                case_id, [f"it is outside the ledger directory {self._root}"]
            )
        return Path(path)

    def read_case(self, case_id: str) -> CaseReading:
        """Read the case ledger in the file at path *case_id*.

        Raises:
            CaseLedgerFileError: The path is outside the reader's root, or
                the file is missing or unreadable, holds no ledger entry,
                holds a row that is not a valid ledger entry, or holds
                entries that are not one case's ledger in log-index order.
                The error names the file and carries every problem found.
        """
        path = self._confined(case_id)
        try:
            ledger_file = read_ledger_file(path)
        except LedgerReadError as exc:
            raise CaseLedgerFileError(case_id, [str(exc)]) from exc
        except ValueError as exc:  # a path the OS cannot name, e.g. a NUL
            raise CaseLedgerFileError(
                case_id, [f"it is not a usable path: {exc}"]
            ) from exc

        reading = ledger_reading(
            ledger_file,
            unobservable=self.unobservable,
            refuse=lambda problems: CaseLedgerFileError(case_id, problems),
        )
        logger.debug(
            "Read case %s: %d ledger entries from %s",
            reading.ledger[0].context,
            len(reading.ledger),
            path,
        )
        return reading


__all__ = ["VultronCaseReader"]
