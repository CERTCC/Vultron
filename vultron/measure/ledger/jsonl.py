"""The tolerant case-ledger JSONL reader (CEH-02-001, CEH-02-003, CEH-02-008).

The reader is handed its files by the caller and globs for none itself, so it
opens a committed recording (``case-actor.jsonl``) and a demo dump
(``<actor>-case-ledger.jsonl``) alike (CEH-02-010).  It degrades one malformed
row to one :class:`UnusableRow` and reads the rest; a caller that must refuse a
damaged file, such as ``vultron-demo-report`` (DRPT-01-004), wraps it and raises
when :attr:`LedgerFile.unusable_rows` is non-empty.
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
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vultron.errors import LedgerReadError
from vultron.primitives import NonEmptyString


class UnusableRow(BaseModel):
    """One ledger row the reader could not use, and why (CEH-02-008).

    Fields:
        path: The file the row is in, or the endpoint path that served it.
        line: The row's 1-based line number in that file.
        reason: Why the row is unusable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    line: int = Field(ge=1)
    reason: NonEmptyString

    def describe(self) -> str:
        """Return ``path line N: reason``, the form an error message quotes."""
        return f"{self.path} line {self.line}: {self.reason}"


class LedgerRow(BaseModel):
    """One parsed ledger row and where it was read from.

    Fields:
        path: The file the row is in, or the endpoint path that served it.
        line: The row's 1-based line number in that file.
        data: The row's JSON object, as written.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    line: int = Field(ge=1)
    data: dict[str, Any]

    def unusable(self, reason: str) -> UnusableRow:
        """Return this row reported as unusable for *reason*."""
        return UnusableRow(path=self.path, line=self.line, reason=reason)


class LedgerFile(BaseModel):
    """The rows of one ledger file, and the rows it could not parse.

    Fields:
        path: The file that was read.
        rows: Every row that parsed as a JSON object, in file order.
        unusable_rows: Every non-blank row that did not, in file order.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: Path
    rows: list[LedgerRow] = Field(default_factory=list)
    unusable_rows: list[UnusableRow] = Field(default_factory=list)

    @property
    def entries(self) -> list[dict[str, Any]]:
        """The parsed rows' JSON objects, in file order."""
        return [row.data for row in self.rows]


def read_ledger_file(path: Path) -> LedgerFile:
    """Read one case-ledger JSONL file, tolerating malformed rows.

    Blank lines are skipped.  A non-blank line that is not valid JSON, or is
    valid JSON but not an object, becomes one :class:`UnusableRow`; every
    other row is read (CEH-02-008).

    Raises:
        LedgerReadError: When the file itself cannot be read — a missing path
            is the caller's error, not a malformed row.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LedgerReadError(f"Cannot read {path}: {exc}") from exc
    return parse_ledger_text(text, path)


def parse_ledger_row(
    text: str, path: Path, line: int
) -> LedgerRow | UnusableRow:
    """Parse one non-blank case-ledger row, read from *line* of *path*.

    The one row parser of :func:`parse_ledger_text`, for a caller that
    receives rows one at a time, such as the live Vultron case reader over
    a node's event stream.

    Args:
        text: The row: one JSON object.
        path: Where the row was read from, quoted in its description.
        line: The row's 1-based position in *path*.

    Returns:
        The parsed row, or the row reported as unusable when it is not a
        JSON object (CEH-02-008).
    """
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return UnusableRow(path=path, line=line, reason=f"Parse error: {exc}")
    if not isinstance(parsed, dict):
        return UnusableRow(
            path=path,
            line=line,
            reason=(
                "Parse error: a ledger row must be a JSON object, "
                f"not {type(parsed).__name__}"
            ),
        )
    return LedgerRow(path=path, line=line, data=parsed)


def ledger_from_rows(
    path: Path, parsed: Iterable[LedgerRow | UnusableRow]
) -> LedgerFile:
    """The ledger *parsed* rows make, each sorted into rows or unusable."""
    rows: list[LedgerRow] = []
    unusable: list[UnusableRow] = []
    for row in parsed:
        if isinstance(row, LedgerRow):
            rows.append(row)
        else:
            unusable.append(row)
    return LedgerFile(path=path, rows=rows, unusable_rows=unusable)


def parse_ledger_text(text: str, path: Path) -> LedgerFile:
    """Parse case-ledger JSONL *text*, tolerating malformed rows.

    The parsing half of :func:`read_ledger_file`, for a caller that holds
    the text already, such as a node's NDJSON answer.  Blank lines are
    skipped; a non-blank line that is not a JSON object becomes one
    :class:`UnusableRow` (CEH-02-008).

    Args:
        text: The JSONL text, one ledger row per line.
        path: Where the text was read from, quoted in each row's
            description: a file, or the path of the endpoint that served it.
    """
    return ledger_from_rows(
        path,
        (
            parse_ledger_row(line.strip(), path, lineno)
            for lineno, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ),
    )
