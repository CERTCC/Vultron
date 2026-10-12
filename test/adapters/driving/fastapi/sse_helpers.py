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

"""Shared helpers for the demo case ledger stream tests (#3641).

Parses server-sent events the way a client reads them, and stores bare
``CaseLedgerEntry`` records for read-endpoint tests.  Not a test module.
"""

from collections.abc import Iterable, Iterator

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.datalayer import DataLayer


def parse_sse_fields(lines: Iterable[str]) -> dict[str, str]:
    """Map each ``name: value`` line of one event to its field."""
    fields: dict[str, str] = {}
    for line in lines:
        name, _, value = line.partition(": ")
        fields[name] = value
    return fields


def parse_sse_body(body: str) -> list[dict[str, str]]:
    """Split a complete SSE body into one field map per event."""
    return [
        parse_sse_fields(block.split("\n"))
        for block in body.split("\n\n")
        if block.strip()
    ]


def read_sse_event(lines: Iterator[str]) -> dict[str, str]:
    """Read lines from an open stream up to the blank line ending one event."""
    block: list[str] = []
    for line in lines:
        if line == "":
            if block:
                return parse_sse_fields(block)
            continue
        block.append(line)
    raise AssertionError(f"stream ended mid-event: {block}")


def save_ledger_entry(
    dl: DataLayer,
    case_id: str,
    log_index: int,
    event_type: str | None = None,
) -> CaseLedgerEntry:
    """Store a bare ledger entry for *case_id* directly in *dl*."""
    entry = CaseLedgerEntry(
        case_id=case_id,
        log_index=log_index,
        log_object_id=f"{case_id}/objects/{log_index}",
        event_type=event_type or f"test_event_{log_index}",
    )
    dl.save(entry)
    return entry
