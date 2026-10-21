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

"""Judge a received case copy by the ledger tail it names (SYNC-16-006).

A full-case announcement names the ledger position the copy reflects
(SYNC-16-005).  A replica that already holds the case compares that tail with
its own position before it replaces anything:

- it holds a different entry at the tail's index: the chains conflict, and no
  copy repairs that;
- it is already past the tail: the copy is stale, and replacing with it would
  drop the effects of the entries it holds past it;
- otherwise the copy is current, and replaces the case.

The replica's position is its stored chain, or the tail of the copy that last
replaced its case when the chain has not caught up with it yet: that copy
already reflects the entries up to its tail (SYNC-16-007), so a copy behind it
is stale too.

After a replacement whose tail is ahead of the chain, every entry the replica
stores at or before that tail is already reflected in the case, and is stored
as a no-op (:func:`entry_reflected_by_case_copy`).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from vultron.core.models._helpers import _as_id, project_wire_snapshot_to_core
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_copy_position import CaseCopyPosition
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.models.ledger_position import (
    EMPTY_LEDGER_LOG_INDEX,
    LedgerPosition,
)
from vultron.core.models.note import VultronNote
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.sync_helpers import recorded_entries_for_case

logger = logging.getLogger(__name__)


class CaseCopyVerdict(StrEnum):
    """What a replica holding the case does with a copy (SYNC-16-006)."""

    CURRENT = "current"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class CaseCopyJudgement:
    """A copy's verdict, the replica's chain tail, and why."""

    verdict: CaseCopyVerdict
    #: The last entry the replica's own chain stores, or ``None`` when it
    #: stores none for the case.
    chain_tail: CaseLedgerEntry | None
    reason: str

    @property
    def chain_index(self) -> int:
        """``log_index`` of the chain tail, ``-1`` for an empty chain."""
        if self.chain_tail is None:
            return EMPTY_LEDGER_LOG_INDEX
        return self.chain_tail.log_index


def _stored_entries(
    case_id: str, dl: CasePersistence
) -> dict[int, CaseLedgerEntry]:
    return {
        entry.log_index: entry
        for entry in recorded_entries_for_case(case_id=case_id, dl=dl)
    }


def case_copy_position(
    case_id: str, dl: CasePersistence
) -> LedgerPosition | None:
    """The tail of the copy that last replaced *case_id*, or ``None``."""
    record = dl.read(CaseCopyPosition.build_id(case_id))
    if isinstance(record, CaseCopyPosition):
        return record.position
    return None


def judge_case_copy(
    case_id: str, tail: LedgerPosition, dl: CasePersistence
) -> CaseCopyJudgement:
    """Judge a copy of *case_id* that names *tail*, against *dl*'s chain.

    A conflict is checked first: a replica already past the tail that holds a
    different entry at its index disagrees with the copy's chain, not only
    with its age, and that is the fault to report (SYNC-16-006).

    Reads only *dl*.
    """
    entries = _stored_entries(case_id, dl)
    chain_tail = entries[max(entries)] if entries else None
    chain_index = (
        chain_tail.log_index if chain_tail else EMPTY_LEDGER_LOG_INDEX
    )
    replaced_at = case_copy_position(case_id, dl)
    position = max(
        chain_index,
        replaced_at.log_index if replaced_at else EMPTY_LEDGER_LOG_INDEX,
    )

    held_hash: str | None = None
    if tail.log_index == EMPTY_LEDGER_LOG_INDEX:
        case = dl.read_case(case_id)
        held_hash = case.genesis_hash if case and case.genesis_hash else None
    elif tail.log_index in entries:
        held_hash = entries[tail.log_index].entry_hash
    elif replaced_at is not None and replaced_at.log_index == tail.log_index:
        held_hash = replaced_at.entry_hash

    def judged(verdict: CaseCopyVerdict, reason: str) -> CaseCopyJudgement:
        return CaseCopyJudgement(
            verdict=verdict, chain_tail=chain_tail, reason=reason
        )

    if held_hash is not None and held_hash != tail.entry_hash:
        return judged(
            CaseCopyVerdict.CONFLICT,
            f"the copy names entry {tail.log_index} as {tail.entry_hash:.16}…"
            f" but this replica holds {held_hash:.16}… there: the chains"
            " conflict (SYNC-16-006)",
        )
    if position > tail.log_index:
        return judged(
            CaseCopyVerdict.STALE,
            f"the copy reflects entry {tail.log_index} and this replica is"
            f" already at {position}: the copy is stale (SYNC-16-006)",
        )
    return judged(
        CaseCopyVerdict.CURRENT,
        f"the copy reflects entry {tail.log_index} and this replica is at"
        f" {position} (SYNC-16-006)",
    )


def entry_reflected_by_case_copy(
    entry: CaseLedgerEntry, dl: CasePersistence
) -> bool:
    """Whether the copy that replaced *entry*'s case already reflects it.

    True for an entry at or before the tail of the copy that last replaced
    the case (SYNC-16-007): its effects are already in the case file, so it
    is stored without applying them again.  The entry at the tail's index is
    reflected only when it is the entry the copy named; any other entry there
    is not, and is applied, or refused, as any entry is.
    """
    replaced_at = case_copy_position(entry.case_id, dl)
    if replaced_at is None:
        return False
    if entry.log_index < replaced_at.log_index:
        return True
    return (
        entry.log_index == replaced_at.log_index
        and entry.entry_hash == replaced_at.entry_hash
    )


#: The record types a case copy names by id but does not carry, by wire
#: ``type``: an entry that creates one is the only way a replica holds it.
_NAMED_RECORD_TYPES: dict[str, type[CoreObject]] = {
    "Note": VultronNote,
    "CaseStatus": CaseStatus,
    "EmbargoEvent": EmbargoEvent,
}


def _named_by(case: VulnerabilityCase) -> set[str]:
    """The ids of the records *case* names but a copy of it does not carry."""
    named = {str(n) for n in case.notes}
    named |= {
        str(i) for ref in case.case_statuses if (i := _as_id(ref)) is not None
    }
    named |= {entry.embargo_id for entry in case.embargo_register}
    named |= {str(v) for v in case.pending_embargo_proposal_index.values()}
    return named


def _snapshot_objects(value: Any) -> Iterator[dict[str, Any]]:
    """Every object dict, with an id and a type, inside *value*."""
    if isinstance(value, dict):
        if isinstance(value.get("id"), str) and isinstance(
            value.get("type"), str
        ):
            yield value
        for child in value.values():
            yield from _snapshot_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _snapshot_objects(child)


def records_a_reflected_entry_adds(
    entry: CaseLedgerEntry, dl: CasePersistence
) -> list[CoreObject]:
    """The records *entry* carries that the replaced case names and *dl* lacks.

    A case copy carries its participants, reports and active embargo
    inline, but names its notes, statuses and other embargoes by id.  An
    entry the copy reflects is stored as a no-op (SYNC-16-007), so the
    records it carries would otherwise never reach the replica, and the
    replica would end short of where seed-plus-replay leaves it (ADR-0142).
    Copying each one, unchanged, is the copy model (CM-23-016): nothing is
    minted, no clock is read and the case file is not touched.

    An object the case no longer names, such as a note removed later, is
    left out; one that does not validate as its type is left out with a
    WARNING.
    """
    case = dl.read_case(entry.case_id)
    if case is None:
        return []
    named = _named_by(case)
    found: dict[str, CoreObject] = {}
    for data in _snapshot_objects(entry.payload_snapshot):
        record_id = data["id"]
        cls = _NAMED_RECORD_TYPES.get(data["type"])
        if (
            cls is None
            or record_id not in named
            or record_id in found
            or dl.read(record_id) is not None
        ):
            continue
        try:
            found[record_id] = cls.model_validate(
                project_wire_snapshot_to_core(cls, data)
            )
        except ValidationError as exc:
            logger.warning(
                "entry '%s' carries %s '%s' that does not validate, so the"
                " replica cannot store it: %s",
                entry.id_,
                data["type"],
                record_id,
                exc,
            )
    return list(found.values())


__all__ = [
    "CaseCopyJudgement",
    "CaseCopyVerdict",
    "case_copy_position",
    "entry_reflected_by_case_copy",
    "judge_case_copy",
    "records_a_reflected_entry_adds",
]
