"""Select the ledger copy a measure trusts, or merge replicas and report the holes (CEH-02).

The caller hands over ledger files; this module groups their entries by case
(CEH-02-007) and, per case, picks one of two sources:

* **A complete copy, as far as the input shows.**  The CASE_MANAGER assigns log
  indices as a gapless sequence from genesis (CLP-14-010) and holds every entry
  of its case, while a participant's replica misses entries in a lapsed-consent
  gap and after its report closes (CM-10-005, CM-23-004).  No entry names the
  copy's holder — a replica's entries are byte-identical to the CASE_MANAGER's
  (CLP-07-013) — so the copy is identified by completeness, from its entries
  alone: one entry at each index from ``0`` up, no gap, and every entry any
  other copy of the case holds (CEH-02-004, CEH-02-009).  The test never reads
  a file or directory name.  The CASE_MANAGER's own copy always passes.
* **A merge of replicas**, when no copy passes that test.  Entries are
  de-duplicated by entry hash (CEH-02-005), and the result records that it was
  merged and names the log indices no copy supplied (CEH-02-006), so a caller
  can refuse a holed history instead of scoring it.

Completeness can only be judged relative to the input: a replica cut off at the
tail passes when no fuller copy is handed over.  So every result also carries
``end_confirmed`` (:mod:`vultron.measure.ledger.ends`), set only when the
entries prove that nothing follows the last one.

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

import json
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vultron.measure.ledger.ends import ends_in_case_closure
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

    #: One copy holding the whole ledger as far as the input shows, read alone
    #: (CEH-02-004).  Whether its end is the case's end is ``end_confirmed``.
    COMPLETE_COPY = "complete_copy"
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
        source: Whether the entries are one complete copy or a merge.
        rows: One row per distinct (log index, entry hash), ordered by log
            index.
        copies: Every file that held an entry of this case, in caller order.
        complete_copy_path: The file read alone, when ``source`` is a
            complete copy; ``None`` for a merge.
        missing_log_indices: Indices from ``0`` through the highest present
            that no copy supplied (CEH-02-006).  Always empty for a complete
            copy, which is gapless by selection.  A tail no copy holds cannot
            be seen here; see ``end_confirmed``.
        conflicting_log_indices: Indices at which the copies disagree: two
            entry hashes at one index, one entry hash at two indices, or
            two rows with one index and hash but different data.  A
            conforming ledger has none (CLP-07-013); a history built over one
            is not trustworthy, so it is reported, not resolved, and no copy
            is complete while any exists.
        unusable_rows: Rows naming this case that could not be placed — a
            missing or invalid log index or entry hash (CEH-02-008).  A copy
            with such a row is never complete, since the row may be the
            entry its index range lacks.
        end_confirmed: Whether the entries prove the last entry is the
            case's last: it is the CASE_MANAGER's own closure entry, or
            another copy ends on the same entry.  ``False`` means the ledger
            may continue past what the input holds, never that it does.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: NonEmptyString
    source: LedgerSource
    rows: list[PlacedRow]
    copies: list[Path]
    complete_copy_path: Path | None = None
    missing_log_indices: list[int] = Field(default_factory=list)
    conflicting_log_indices: list[int] = Field(default_factory=list)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)
    end_confirmed: bool = False

    @property
    def merged(self) -> bool:
        """Whether the entries were merged from replicas (CEH-02-006)."""
        return self.source is LedgerSource.MERGED_REPLICAS

    @property
    def entries(self) -> list[dict[str, Any]]:
        """The entries' JSON objects, ordered by log index."""
        return [placed.data for placed in self.rows]


class LedgerCopy(BaseModel):
    """One file's rows for one case: the unit complete-copy selection judges.

    Fields:
        path: The file.
        rows: The file's placed rows for the case.
        damaged: Whether the file holds an unusable row that names no case.
            Such a row (unparseable, or with no usable case id) may be this
            case's entry; a bad row naming another case cannot be.
        unusable_rows: The file's rows that name this case but could not be
            placed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    rows: list[PlacedRow] = Field(default_factory=list)
    damaged: bool = False
    unusable_rows: list[UnusableRow] = Field(default_factory=list)


class LedgerRead(BaseModel):
    """Every case found in the files a caller handed over.

    Fields:
        cases: One :class:`CaseLedger` per case id, in case-id order.
        unusable_rows: Every row that could not be parsed or placed in a case,
            by file in caller order, then by line (CEH-02-008).  A row that
            names its case is also on that case's :class:`CaseLedger`.
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


def _key(placed: PlacedRow) -> tuple[int, str]:
    """The identity of an entry across copies: its position and its hash."""
    return placed.log_index, placed.entry_hash


def _distinct(rows: Iterable[PlacedRow]) -> list[PlacedRow]:
    """Return *rows* keeping the first row of each (index, hash), ordered."""
    by_key: dict[tuple[int, str], PlacedRow] = {}
    for placed in rows:
        by_key.setdefault(_key(placed), placed)
    return [by_key[key] for key in sorted(by_key)]


def _differing_data_indices(copies: Iterable[LedgerCopy]) -> list[int]:
    """Indices where two rows share an (index, hash) but not their data.

    The reader never recomputes a hash, so such rows disagree about the
    entry.  Keeping either would resolve the disagreement silently, by file
    order.
    """
    data_at: dict[tuple[int, str], set[str]] = {}
    for copy in copies:
        for placed in copy.rows:
            data_at.setdefault(_key(placed), set()).add(
                json.dumps(placed.data, sort_keys=True, default=str)
            )
    return sorted(
        {index for (index, _), seen in data_at.items() if len(seen) > 1}
    )


def _conflicting_indices(keys: Iterable[tuple[int, str]]) -> list[int]:
    """Indices holding two hashes, and every index of a hash seen at two."""
    hashes_at: dict[int, set[str]] = {}
    indices_of: dict[str, set[int]] = {}
    for index, entry_hash in keys:
        hashes_at.setdefault(index, set()).add(entry_hash)
        indices_of.setdefault(entry_hash, set()).add(index)
    conflicts = {i for i, found in hashes_at.items() if len(found) > 1}
    for found in indices_of.values():
        if len(found) > 1:
            conflicts |= found
    return sorted(conflicts)


def _holds_whole_ledger(
    copy: LedgerCopy, rows: list[PlacedRow], all_keys: set[tuple[int, str]]
) -> bool:
    """Whether *copy* alone is the case's whole ledger, judged from its entries.

    It must be undamaged, hold exactly one entry at each index from ``0``
    through its highest (CLP-14-010), and hold every entry any copy of the
    case holds.
    """
    if copy.damaged or copy.unusable_rows:
        return False
    if [p.log_index for p in rows] != list(range(len(rows))):
        return False
    return {_key(p) for p in rows} >= all_keys


def _end_confirmed(
    rows: list[PlacedRow], copies: Mapping[Path, list[PlacedRow]]
) -> bool:
    """Whether the entries prove *rows*' last entry is the case's last.

    Two copies ending on the same entry confirm it, and so does a last entry
    that is the CASE_MANAGER's own closure (:mod:`vultron.measure.ledger.ends`).
    """
    if not rows:
        return False
    last = _key(rows[-1])
    ending_there = sum(
        1 for held in copies.values() if held and _key(held[-1]) == last
    )
    return ending_there >= 2 or ends_in_case_closure([p.data for p in rows])


def _missing_indices(rows: Sequence[PlacedRow]) -> list[int]:
    """Indices from genesis (``0``) through the highest present that are absent."""
    present = {p.log_index for p in rows}
    if not present:
        return []
    return sorted(set(range(max(present) + 1)) - present)


def select_case_ledger(
    case_id: str, copies: Sequence[LedgerCopy]
) -> CaseLedger:
    """Pick a complete copy of one case's ledger, or merge its replicas.

    Args:
        case_id: The case every row in *copies* belongs to.
        copies: Each file's rows for this case, in caller order.  A file
            listed twice is one copy.

    Returns:
        A complete copy read alone when one holds the whole ledger and no
        two copies disagree (CEH-02-004); otherwise the de-duplicated merge,
        marked merged and carrying its holes and conflicts (CEH-02-005,
        CEH-02-006).  The result does not depend on the order of *copies*
        except for which of several identical whole copies is named.
    """
    by_path: dict[Path, LedgerCopy] = {}
    for copy in copies:
        seen = by_path.get(copy.path)
        by_path[copy.path] = (
            copy
            if seen is None
            else LedgerCopy(
                path=copy.path,
                rows=[*seen.rows, *copy.rows],
                damaged=seen.damaged or copy.damaged,
                unusable_rows=[*seen.unusable_rows, *copy.unusable_rows],
            )
        )
    distinct = {path: _distinct(copy.rows) for path, copy in by_path.items()}
    all_keys = {_key(p) for rows in distinct.values() for p in rows}
    conflicts = sorted(
        set(_conflicting_indices(all_keys))
        | set(_differing_data_indices(by_path.values()))
    )
    unusable = sorted(
        {
            (str(row.path), row.line, row.reason): row
            for copy in by_path.values()
            for row in copy.unusable_rows
        }.values(),
        key=lambda r: (str(r.path), r.line),
    )
    paths = list(by_path)

    if not conflicts:
        for path, rows in distinct.items():
            if _holds_whole_ledger(by_path[path], rows, all_keys):
                return CaseLedger(
                    case_id=case_id,
                    source=LedgerSource.COMPLETE_COPY,
                    rows=rows,
                    copies=paths,
                    complete_copy_path=path,
                    unusable_rows=unusable,
                    end_confirmed=_end_confirmed(rows, distinct),
                )

    merged = _distinct(p for rows in distinct.values() for p in rows)
    return CaseLedger(
        case_id=case_id,
        source=LedgerSource.MERGED_REPLICAS,
        rows=merged,
        copies=paths,
        missing_log_indices=_missing_indices(merged),
        conflicting_log_indices=conflicts,
        unusable_rows=unusable,
        end_confirmed=not conflicts and _end_confirmed(merged, distinct),
    )


def case_ledgers_from_files(files: Iterable[LedgerFile]) -> LedgerRead:
    """Group already-read ledger files by case and select each case's source.

    Never interleaves two cases: every row is keyed on its case id before any
    ordering by log index (CEH-02-007, CLP-14-004).  A file handed over twice
    (by the same resolved path) is read once.
    """
    unusable: list[UnusableRow] = []
    per_case: dict[str, list[LedgerCopy]] = {}
    seen_paths: set[Path] = set()
    for ledger_file in files:
        resolved = ledger_file.path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        file_unusable = list(ledger_file.unusable_rows)
        nameless = bool(ledger_file.unusable_rows)
        by_case: dict[str, list[PlacedRow]] = {}
        unusable_by_case: dict[str, list[UnusableRow]] = {}
        for row in ledger_file.rows:
            placed = _place(row)
            if isinstance(placed, UnusableRow):
                file_unusable.append(placed)
                named_case = case_id_of(row.data)
                if named_case is None:
                    nameless = True
                else:
                    unusable_by_case.setdefault(named_case, []).append(placed)
                continue
            by_case.setdefault(placed.case_id, []).append(placed)
        unusable.extend(sorted(file_unusable, key=lambda r: r.line))
        for case_id in sorted(by_case.keys() | unusable_by_case.keys()):
            per_case.setdefault(case_id, []).append(
                LedgerCopy(
                    path=ledger_file.path,
                    rows=by_case.get(case_id, []),
                    damaged=nameless,
                    unusable_rows=unusable_by_case.get(case_id, []),
                )
            )
    cases = {
        case_id: select_case_ledger(case_id, per_case[case_id])
        for case_id in sorted(per_case)
    }
    return LedgerRead(cases=cases, unusable_rows=unusable)


def read_case_ledgers(paths: Iterable[Path]) -> LedgerRead:
    """Read the ledger files the caller names and select each case's source.

    The layer globs for nothing: *paths* is the whole input, whatever the files
    and their directories are called (CEH-02-003, CEH-02-010).  A path named
    twice is read once.

    Raises:
        LedgerReadError: When a named file cannot be read at all.
    """
    unique: dict[Path, Path] = {}
    for path in paths:
        unique.setdefault(path.resolve(), path)
    return case_ledgers_from_files(
        read_ledger_file(path) for path in unique.values()
    )
