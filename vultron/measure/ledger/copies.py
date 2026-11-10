"""Select the ledger copy a measure trusts, or merge replicas and report the holes (CEH-02).

The caller hands over ledger files; this module groups their entries by case
(CEH-02-007) and, per case, picks one of two sources:

* **The canonical copy.**  The CASE_MANAGER assigns log indices as a gapless
  sequence from genesis (CLP-14-010) and holds every entry of its case, while a
  participant's replica misses entries in a lapsed-consent gap and after its
  report closes (CM-10-005, CM-23-004).  So a copy is canonical when its
  entries alone show it: one entry at each index from ``0`` up, no gap, and
  every entry any other copy of the case holds (CEH-02-004, CEH-02-009).  The
  test reads the entries only — never a file or directory name.  A replica
  that happens to hold the whole ledger is byte-identical to the CASE_MANAGER's
  copy entry for entry (CLP-07-013), so selecting it yields the same history.
* **A merge of replicas**, when no copy passes that test.  Entries are
  de-duplicated by entry hash (CEH-02-005), and the result records that it was
  merged and names the log indices no copy supplied (CEH-02-006), so a caller
  can refuse a holed history instead of scoring it.

A row that cannot be placed in a case — no case id, no usable log index, or no
entry hash — is reported as unusable and the rest are read (CEH-02-008).
"""

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

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vultron.measure.ledger.fields import (
    case_id_of,
    entry_hash_of,
    log_index_of,
)
from vultron.measure.ledger.jsonl import (
    LedgerFile,
    LedgerRow,
    UnusableRow,
    read_ledger_file,
)
from vultron.primitives import NonEmptyString


class LedgerSource(StrEnum):
    """Where a case's entries came from."""

    #: One copy holding the whole ledger, read alone (CEH-02-004).
    CANONICAL_COPY = "canonical_copy"
    #: The de-duplicated union of partial replicas (CEH-02-005).
    MERGED_REPLICAS = "merged_replicas"


class PlacedRow(BaseModel):
    """A ledger row whose case, position and identity are known.

    Fields:
        row: The row as read, with its file and line.
        case_id: The case the entry belongs to.
        log_index: The entry's position in that case's ledger.
        entry_hash: The entry's hash, which names it across copies.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    row: LedgerRow
    case_id: NonEmptyString
    log_index: int = Field(ge=0)
    entry_hash: NonEmptyString

    @property
    def data(self) -> dict[str, Any]:
        """The entry's JSON object, as written."""
        return self.row.data


class CaseLedger(BaseModel):
    """One case's ledger entries, from the source a measure should trust.

    Fields:
        case_id: The case.
        source: Whether the entries are one canonical copy or a merge.
        rows: One row per entry hash, ordered by log index.
        copies: Every file that held an entry of this case, in caller order.
        canonical_path: The file read alone, when ``source`` is the
            canonical copy; ``None`` for a merge.
        missing_log_indices: Indices from ``0`` through the highest present
            that no copy supplied (CEH-02-006).  Always empty for a canonical
            copy, which is gapless by selection.
        conflicting_log_indices: Indices at which two copies hold different
            entries.  A conforming ledger has none (CLP-07-013); a history
            built over one is not trustworthy, so it is reported, not resolved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    source: LedgerSource
    rows: list[PlacedRow]
    copies: list[Path]
    canonical_path: Path | None = None
    missing_log_indices: list[int] = Field(default_factory=list)
    conflicting_log_indices: list[int] = Field(default_factory=list)

    @property
    def merged(self) -> bool:
        """Whether the entries were merged from replicas (CEH-02-006)."""
        return self.source is LedgerSource.MERGED_REPLICAS

    @property
    def entries(self) -> list[dict[str, Any]]:
        """The entries' JSON objects, ordered by log index."""
        return [placed.data for placed in self.rows]


class LedgerRead(BaseModel):
    """Every case found in the files a caller handed over.

    Fields:
        cases: One :class:`CaseLedger` per case id, in case-id order.
        unusable_rows: Every row that could not be parsed or placed in a case,
            by file in caller order, then by line (CEH-02-008).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cases: dict[str, CaseLedger] = Field(default_factory=dict)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)


def _place(row: LedgerRow) -> PlacedRow | UnusableRow:
    """Return *row* placed in its case, or reported as unusable."""
    case_id = case_id_of(row.data)
    log_index = log_index_of(row.data)
    entry_hash = entry_hash_of(row.data)
    missing = [
        name
        for name, value in (
            ("caseId", case_id),
            ("logIndex", log_index),
            ("entryHash", entry_hash),
        )
        if value is None
    ]
    if case_id is None or log_index is None or entry_hash is None:
        return row.unusable(
            "no usable "
            + ", ".join(missing)
            + " (a ledger entry needs all three)"
        )
    return PlacedRow(
        row=row, case_id=case_id, log_index=log_index, entry_hash=entry_hash
    )


def _distinct_by_hash(rows: Iterable[PlacedRow]) -> list[PlacedRow]:
    """Return *rows* keeping the first row of each entry hash, in input order."""
    seen: set[str] = set()
    distinct: list[PlacedRow] = []
    for placed in rows:
        if placed.entry_hash not in seen:
            seen.add(placed.entry_hash)
            distinct.append(placed)
    return distinct


def _ordered(rows: Iterable[PlacedRow]) -> list[PlacedRow]:
    """Return *rows* ordered by log index, then entry hash."""
    return sorted(rows, key=lambda p: (p.log_index, p.entry_hash))


def _holds_whole_ledger(copy: list[PlacedRow], all_hashes: set[str]) -> bool:
    """Whether *copy* alone is the case's whole ledger, judged from its entries.

    It must hold exactly one entry at each index from ``0`` through its highest
    (CLP-14-010), and every entry hash any copy of the case holds.
    """
    indices = sorted(p.log_index for p in copy)
    if indices != list(range(len(indices))):
        return False
    return {p.entry_hash for p in copy} >= all_hashes


def _missing_indices(rows: Sequence[PlacedRow]) -> list[int]:
    """Indices from genesis (``0``) through the highest present that are absent."""
    present = {p.log_index for p in rows}
    if not present:
        return []
    return sorted(set(range(max(present) + 1)) - present)


def _conflicting_indices(rows: Sequence[PlacedRow]) -> list[int]:
    """Indices at which more than one distinct entry hash appears."""
    hashes: dict[int, set[str]] = {}
    for placed in rows:
        hashes.setdefault(placed.log_index, set()).add(placed.entry_hash)
    return sorted(index for index, found in hashes.items() if len(found) > 1)


def select_case_ledger(
    case_id: str, copies: Sequence[tuple[Path, list[PlacedRow]]]
) -> CaseLedger:
    """Pick the canonical copy of one case's ledger, or merge its replicas.

    Args:
        case_id: The case every row in *copies* belongs to.
        copies: Each file's rows for this case, in caller order.  A file
            listed twice is one copy.

    Returns:
        The canonical copy read alone when one holds the whole ledger
        (CEH-02-004); otherwise the de-duplicated merge, marked merged and
        carrying its holes (CEH-02-005, CEH-02-006).
    """
    by_path: dict[Path, list[PlacedRow]] = {}
    for path, rows in copies:
        by_path.setdefault(path, []).extend(rows)
    distinct_copies = {
        path: _distinct_by_hash(rows) for path, rows in by_path.items()
    }
    all_hashes = {
        p.entry_hash for rows in distinct_copies.values() for p in rows
    }
    paths = list(distinct_copies)

    for path, rows in distinct_copies.items():
        if _holds_whole_ledger(rows, all_hashes):
            return CaseLedger(
                case_id=case_id,
                source=LedgerSource.CANONICAL_COPY,
                rows=_ordered(rows),
                copies=paths,
                canonical_path=path,
            )

    merged = _ordered(
        _distinct_by_hash(p for rows in distinct_copies.values() for p in rows)
    )
    return CaseLedger(
        case_id=case_id,
        source=LedgerSource.MERGED_REPLICAS,
        rows=merged,
        copies=paths,
        missing_log_indices=_missing_indices(merged),
        conflicting_log_indices=_conflicting_indices(merged),
    )


def case_ledgers_from_files(files: Iterable[LedgerFile]) -> LedgerRead:
    """Group already-read ledger files by case and select each case's source.

    Never interleaves two cases: every row is keyed on its case id before any
    ordering by log index (CEH-02-007, CLP-14-004).
    """
    unusable: list[UnusableRow] = []
    per_case: dict[str, list[tuple[Path, list[PlacedRow]]]] = {}
    for ledger_file in files:
        file_unusable = list(ledger_file.unusable_rows)
        by_case: dict[str, list[PlacedRow]] = {}
        for row in ledger_file.rows:
            placed = _place(row)
            if isinstance(placed, UnusableRow):
                file_unusable.append(placed)
                continue
            by_case.setdefault(placed.case_id, []).append(placed)
        unusable.extend(sorted(file_unusable, key=lambda r: r.line))
        for case_id, rows in by_case.items():
            per_case.setdefault(case_id, []).append((ledger_file.path, rows))
    cases = {
        case_id: select_case_ledger(case_id, per_case[case_id])
        for case_id in sorted(per_case)
    }
    return LedgerRead(cases=cases, unusable_rows=unusable)


def read_case_ledgers(paths: Iterable[Path]) -> LedgerRead:
    """Read the ledger files the caller names and select each case's source.

    The layer globs for nothing: *paths* is the whole input, whatever the files
    and their directories are called (CEH-02-003, CEH-02-010).

    Raises:
        LedgerReadError: When a named file cannot be read at all.
    """
    return case_ledgers_from_files(read_ledger_file(path) for path in paths)
