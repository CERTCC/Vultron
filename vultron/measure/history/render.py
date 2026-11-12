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
"""Render a case event history for a person or a program (CEH-01-005, CEH-01-006).

Two forms, from one library call (:func:`case_history_report`):

* ``json`` — the :class:`~vultron.measure.history.CaseEventHistories` model,
  as JSON, with every id as recorded, for a later tool to consume.
* ``table`` — one Markdown section per case, with a table of its events.  A
  row names its participant, the acting actor and the object by friendly
  display names, through the shared resolver
  (:func:`~vultron.measure.ledger.display_label`), never a bare URI
  (CEH-01-006, DRPT-03-009).  The activity column is the registry phrase of
  the causing entry's semantic type (CEH-01-007, DRPT-03-002).

The section heads each table with what bounds its trust: whether the entries
are one complete copy or a merge, whether the end is confirmed, and every
hole, conflict, unusable row, excluded state and unreadable entry.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from vultron.errors import CaseHistoryInputError
from vultron.measure.history.derive import case_event_history
from vultron.measure.history.model import (
    CaseEvent,
    CaseEventHistories,
    CaseEventHistory,
    EventScope,
)
from vultron.measure.ledger import (
    MISSING_SLOT,
    UNNAMED_ACTOR,
    CaseLedger,
    UnusableRow,
    actor_uri,
    collect_actor_names,
    collect_participant_actors,
    display_label,
    entry_references,
    payload_of,
    read_case_ledgers,
    render_event_phrase,
)


class HistoryFormat(StrEnum):
    """The output forms of the case event history command (CEH-01-005)."""

    #: Machine-readable: the history model as JSON.
    JSON = "json"
    #: Human-readable: one Markdown table per case.
    TABLE = "table"


#: The label of a case-scoped event's participant cell (CEH-03-004).
CASE_SUBJECT = "case"

#: The table's column headers, in order.
TABLE_HEADERS: tuple[str, ...] = (
    "#",
    "Committed",
    "Claimed",
    "Event",
    "Participant",
    "Actor",
    "Object",
    "Activity",
    "Gaps",
)


class EventRow(BaseModel):
    """One event as the table shows it: every cell a friendly label.

    Fields:
        log_index: The causing entry's log index.
        committed: The entry's commit stamp.
        claimed: The time the entry's activity claims, or ``"—"``.
        event: The event kind.
        participant: Whom the event belongs to, or ``"case"``.
        actor: The causing entry's acting actor.
        object: The causing entry's object, and its destination when it
            names one (``object → destination``).
        activity: The registry phrase of the causing entry.
        gaps: The event's data-gap labels and bounding deadline.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    log_index: int
    committed: str
    claimed: str
    event: str
    participant: str
    actor: str
    object: str
    activity: str
    gaps: str

    def cells(self) -> list[str]:
        """The row's cells, in :data:`TABLE_HEADERS` order."""
        return [
            str(self.log_index),
            self.committed,
            self.claimed,
            self.event,
            self.participant,
            self.actor,
            self.object,
            self.activity,
            self.gaps,
        ]


def _one_line(text: str) -> str:
    """Replace each line break in *text* with a space."""
    return text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _md_cell(text: str) -> str:
    """Escape a value for one Markdown table cell or one Markdown line.

    A ``|`` would split the cell and a line break would end the row, and both
    can arrive in a display name taken from a payload.
    """
    return _one_line(text.replace("|", "\\|"))


def _code_span(text: str) -> str:
    """Render *text* as one Markdown code span on one line.

    A line break would end the heading, and a backtick in *text* would close a
    single-backtick span early, so the fence is one backtick longer than the
    longest run in *text*.  A ``|`` cannot break a heading and is kept as is,
    since a backslash inside a code span renders literally.
    """
    flat = _one_line(text)
    runs = [len(m) for m in re.findall(r"`+", flat)]
    fence = "`" * (max(runs, default=0) + 1)
    pad = " " if flat.startswith("`") or flat.endswith("`") else ""
    return f"{fence}{pad}{flat}{pad}{fence}"


def _entries_by_index(ledger: CaseLedger) -> dict[int, dict[str, Any]]:
    """Each log index's entry; the first row wins where copies conflict."""
    entries: dict[int, dict[str, Any]] = {}
    for placed in ledger.rows:
        entries.setdefault(placed.log_index, placed.data)
    return entries


def _object_labels(
    payload: Mapping[str, Any], names: Mapping[str, str], case_id: str
) -> tuple[str | None, str | None]:
    """The friendly labels of one entry's object and of its destination."""
    refs = entry_references(payload)
    obj = display_label(
        refs.object_ref, refs.object_type, names, case_id=case_id
    )
    dest = display_label(
        refs.target_ref, refs.target_type, names, case_id=case_id
    )
    return obj, dest


def _gaps_cell(timed: Mapping[str, Any], event: CaseEvent) -> str:
    """The event's gap labels, and the deadline that bounds it."""
    parts = [str(gap) for gap in event.gaps]
    if event.deadline is not None:
        parts.append(f"deadline {timed['deadline']}")
    return ", ".join(parts) or MISSING_SLOT


def label_names(
    replicas: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, str]:
    """The display name of every id a row may name (DRPT-03-003).

    An actor's ``name`` from the payloads, through the shared resolver
    (:func:`~vultron.measure.ledger.collect_actor_names`), and for each
    ``CaseParticipant`` id the label of the actor it stands for.
    """
    actor_names = collect_actor_names(replicas)
    participants = {
        participant: display_label(actor, "Actor", actor_names)
        or UNNAMED_ACTOR
        for participant, actor in collect_participant_actors(replicas).items()
    }
    return participants | actor_names


def event_row(
    event: CaseEvent,
    entry: Mapping[str, Any] | None,
    names: Mapping[str, str],
    case_id: str,
) -> EventRow:
    """Label one event for the table (CEH-01-006, DRPT-03-004).

    *entry* is the ledger entry at the event's log index, whose actor,
    object and semantic type the actor, object and activity cells read;
    with no entry those cells read ``"—"`` and the activity is the bare
    registry phrase.
    """
    payload = payload_of(entry) if entry is not None else {}
    uri = actor_uri(payload.get("actor"))
    actor = display_label(uri, "Actor", names) if uri else None
    obj, dest = _object_labels(payload, names, case_id)
    object_cell = f"{obj} → {dest}" if obj and dest else obj or dest
    if event.scope is EventScope.CASE:
        participant = CASE_SUBJECT
    else:
        participant = (
            display_label(event.participant, "Actor", names) or MISSING_SLOT
        )
    timed = event.model_dump(
        mode="json", include={"committed_at", "claimed_at", "deadline"}
    )
    return EventRow(
        log_index=event.log_index,
        committed=timed["committed_at"],
        claimed=timed["claimed_at"] or MISSING_SLOT,
        event=str(event.kind),
        participant=participant,
        actor=actor or MISSING_SLOT,
        object=object_cell or MISSING_SLOT,
        activity=render_event_phrase(
            str(event.semantic_type), actor, object_cell
        ),
        gaps=_gaps_cell(timed, event),
    )


def event_rows(
    history: CaseEventHistory, ledger: CaseLedger, names: Mapping[str, str]
) -> list[EventRow]:
    """Label every event of *history*, read against the *ledger* it came from."""
    entries = _entries_by_index(ledger)
    return [
        event_row(event, entries.get(event.log_index), names, history.case_id)
        for event in history.events
    ]


def _indices(indices: Sequence[int]) -> str:
    return ", ".join(str(i) for i in indices) if indices else "none"


def _trust_lines(history: CaseEventHistory) -> list[str]:
    """What bounds a reader's trust in one case's history."""
    lines = [
        f"- Source: {history.source}",
        f"- End confirmed: {'yes' if history.end_confirmed else 'no'}",
        f"- Missing log indices: {_indices(history.missing_log_indices)}",
        "- Conflicting log indices: "
        f"{_indices(history.conflicting_log_indices)}",
        f"- Events: {len(history.events)}",
    ]
    lines.extend(_unusable_lines(history.unusable_rows))
    lines.extend(
        f"- Excluded state at entry {item.log_index}: {item.dimension} "
        f"{item.named} is behind {item.reached}"
        for item in history.excluded
    )
    lines.extend(
        f"- Unreadable entry {item.log_index}: {item.reason}"
        for item in history.unreadable_entries
    )
    return [_md_cell(line) for line in lines]


def _unusable_lines(rows: Iterable[UnusableRow]) -> list[str]:
    return [f"- Unusable row: {row.describe()}" for row in rows]


def render_table(
    cases: Iterable[tuple[CaseEventHistory, CaseLedger]],
    names: Mapping[str, str],
    unplaced: Sequence[UnusableRow] = (),
) -> str:
    """Render one Markdown section per case, each with its event table.

    *unplaced* are the unusable rows that name no case the input holds;
    they are listed first, so with each case's own unusable rows in its
    section the table shows every unusable row the JSON form lists, once.
    """
    lines = ["# Case event history", ""]
    if unplaced:
        lines += [
            "## Rows in no case",
            "",
            *(_md_cell(line) for line in _unusable_lines(unplaced)),
            "",
        ]
    for history, ledger in cases:
        lines += [f"## Case {_code_span(history.case_id)}", ""]
        lines += [*_trust_lines(history), ""]
        lines.append("| " + " | ".join(TABLE_HEADERS) + " |")
        lines.append("| " + " | ".join(["---"] * len(TABLE_HEADERS)) + " |")
        for row in event_rows(history, ledger, names):
            lines.append(
                "| " + " | ".join(_md_cell(c) for c in row.cells()) + " |"
            )
        lines.append("")
    return "\n".join(lines)


def render_json(histories: CaseEventHistories) -> str:
    """Render the histories as JSON, every id as recorded (CEH-01-005)."""
    return histories.model_dump_json(indent=2) + "\n"


def case_history_report(
    paths: Iterable[Path],
    *,
    fmt: HistoryFormat,
    case_id: str | None = None,
) -> str:
    """Read the named ledger files and render each case's event history.

    *case_id* limits the output to one case; without it every case the
    files hold gets its own section.  The files are the whole input: nothing
    is globbed (CEH-02-003).

    Raises:
        LedgerReadError: When a named file cannot be read at all.
        CaseHistoryInputError: When the files hold no case ledger entry, or
            do not hold *case_id* (CEH-01-008).
    """
    paths = list(paths)
    read = read_case_ledgers(paths)
    if not read.cases:
        raise CaseHistoryInputError(
            "no case ledger entry in " + ", ".join(str(path) for path in paths)
        )
    if case_id is not None and case_id not in read.cases:
        raise CaseHistoryInputError(
            f"case {case_id!r} is not in the input; it holds "
            + ", ".join(sorted(read.cases))
        )
    ledgers = (
        {case_id: read.cases[case_id]} if case_id is not None else read.cases
    )
    histories = {cid: case_event_history(lg) for cid, lg in ledgers.items()}
    if fmt is HistoryFormat.JSON:
        return render_json(
            CaseEventHistories(
                histories=histories, unusable_rows=read.unusable_rows
            )
        )
    names = label_names({cid: lg.entries for cid, lg in read.cases.items()})
    in_a_case = {
        (row.path, row.line)
        for ledger in read.cases.values()
        for row in ledger.unusable_rows
    }
    return render_table(
        ((histories[cid], ledgers[cid]) for cid in histories),
        names,
        [
            row
            for row in read.unusable_rows
            if (row.path, row.line) not in in_a_case
        ],
    )
