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

"""Shared reads of the committed VINCE fixtures and their translation."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any

from vultron.adapters.connectors.vince import translate_case
from vultron.core.models.case_reading import CaseReading
from vultron.measure.history.derive import derive_case
from vultron.measure.history.model import CaseEventHistory
from vultron.measure.history.reached import ReachedState
from vultron.measure.ledger import (
    LedgerFile,
    LedgerRow,
    case_ledgers_from_files,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES = REPO_ROOT / "test" / "fixtures" / "vince"
CROSSWALK = REPO_ROOT / "docs" / "reference" / "vince_crosswalk.md"
COMM_URL = "https://vince.example.org/vince/comm"

ACTIVE = "999901-active-embargoed"
INACTIVE = "999902-inactive-published"
UNKNOWN = "999903-unknown-values"
CASES = (ACTIVE, INACTIVE, UNKNOWN)


@cache
def _reads_text(stem: str) -> str:
    return (FIXTURES / f"{stem}.json").read_text(encoding="utf-8")


def reads(stem: str) -> dict[str, Any]:
    """A fresh copy of the committed fixture *stem*'s reads."""
    loaded: dict[str, Any] = json.loads(_reads_text(stem))["reads"]
    return loaded


def translate(stem: str) -> CaseReading:
    return translate_case(reads(stem), comm_url=COMM_URL)


def projected(reading: CaseReading) -> tuple[CaseEventHistory, ReachedState]:
    """The event history and reached states the measures project from
    *reading*'s ledger, standing in for the core's projection (CRD-01-003)."""
    path = Path("vince-reading.jsonl")
    rows = [
        LedgerRow(
            path=path,
            line=i + 1,
            data=entry.model_dump(by_alias=True, mode="json"),
        )
        for i, entry in enumerate(reading.ledger)
    ]
    read = case_ledgers_from_files([LedgerFile(path=path, rows=rows)])
    assert read.unusable_rows == []
    return derive_case(read.cases[reading.ledger[0].case_id])


def _records(node: object, kind: str) -> Iterator[Mapping[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _records(item, kind)
    elif isinstance(node, dict):
        if node.get("type") == kind:
            yield node
        for child in node.values():
            yield from _records(child, kind)


def records(reading: CaseReading, kind: str) -> list[Mapping[str, Any]]:
    """Every object of type *kind* any entry's payload carries."""
    return [
        record
        for entry in reading.ledger
        for record in _records(entry.payload_snapshot.get("object"), kind)
    ]


def actors_by_name(reading: CaseReading) -> dict[str, str]:
    """Each seated participant's name and actor id."""
    return {
        record["name"]: record["attributedTo"]
        for record in records(reading, "CaseParticipant")
    }


def crosswalk_rows() -> dict[str, list[str]]:
    """Each row of the crosswalk page's tables: its id and its cells."""
    rows: dict[str, list[str]] = {}
    for line in CROSSWALK.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*(VINCE-[A-Z]{2}-\d{2})\s*\|", line)
        if match:
            rows[match.group(1)] = [
                c.strip() for c in line.strip("|").split("|")
            ]
    return rows


def crosswalk_caveats() -> dict[str, str]:
    """Each row's caveat, as the page quotes it, backticks dropped."""
    text = CROSSWALK.read_text(encoding="utf-8").replace("`", "")
    return dict(
        re.findall(r"(VINCE-[A-Z]{2}-\d{2})[^\n]*?: \"([^\"]+)\"", text)
    )
