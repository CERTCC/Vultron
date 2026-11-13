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

"""An in-memory fake ``CaseReader``, to prove the port's shape (#6358).

The fake "outside system" holds each case as a list of
:class:`OutsideRecord` values.  The fake reader translates a record by its
``kind`` through :data:`FAKE_RULES`, into one core ledger entry whose actor is
the record's actor and whose times are the record's own (CRD-01-006,
CRD-02-006).  A record of a kind no rule names, or with no time, comes back
untranslated with the matching reason (CRD-01-005, CRD-02-003).

The payload objects come from the measures' hand-built ledger builders, so
the fake's ledger is one the event-history projection reads.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from test.support.objects import make
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    Inference,
    UnobservableFact,
    UntranslatedFact,
    UntranslatedReason,
)
from vultron.errors import VultronNotFoundError

FAKE_CASE = "urn:uuid:case-1"


@dataclass(frozen=True)
class OutsideRecord:
    """One record of the fake outside system.

    Attributes:
        record_id: The record's id in the outside system.
        kind: What the record says happened.
        actor: Who did it, as the outside system names them.
        at: When, as the outside system states it, or ``None``.
        value: The object the act is about, as a ledger payload object.
    """

    record_id: str
    kind: str
    actor: str
    at: datetime | None
    value: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FakeRule:
    """How the fake reader translates one record kind.

    ``rule_id`` and ``caveat`` are set when the rule infers rather than
    states the entry's state.
    """

    semantic_type: str
    activity_type: str
    rule_id: str | None = None
    caveat: str | None = None


#: The fake reader's mapping, keyed by record kind.
FAKE_RULES: Mapping[str, FakeRule] = {
    "case_opened": FakeRule("create_case", "Create"),
    "vendor_listed": FakeRule(
        "create_case_participant",
        "Create",
        rule_id="FAKE-RM-01",
        caveat="The source lists the vendor; it does not record the notice.",
    ),
    "vendor_status": FakeRule("add_participant_status_to_participant", "Add"),
}

#: What the fake source can never observe.
FAKE_UNOBSERVABLE: tuple[UnobservableFact, ...] = (
    UnobservableFact(
        fact="Fix deployed (D)", why="The fake source has no such field."
    ),
)


def _entry(
    case_id: str,
    index: int,
    record: OutsideRecord,
    rule: FakeRule,
    at: datetime,
) -> CaseLedgerEntry:
    activity_id = f"{case_id}/activity/{record.record_id}"
    return make(
        CaseLedgerEntry,
        case_id=case_id,
        log_index=index,
        log_object_id=activity_id,
        semantic_type=rule.semantic_type,
        payload_snapshot={
            "id": activity_id,
            "type": rule.activity_type,
            "actor": record.actor,
            "object": dict(record.value),
            "published": at.isoformat(),
        },
        entry_hash=f"hash-{index}",
        published=at,
        received_at=at,
    )


class FakeCaseReader:
    """A ``CaseReader`` over an in-memory fake outside system."""

    name = "fake"
    unobservable: tuple[UnobservableFact, ...] = FAKE_UNOBSERVABLE

    def __init__(self, cases: Mapping[str, Sequence[OutsideRecord]]) -> None:
        self._cases = dict(cases)

    def read_case(self, case_id: str) -> CaseReading:
        """Translate the fake case *case_id*, record by record."""
        if case_id not in self._cases:
            raise VultronNotFoundError("fake outside case", case_id)
        ledger: list[CaseLedgerEntry] = []
        citations: list[EntryCitation] = []
        inferences: list[Inference] = []
        untranslated: list[UntranslatedFact] = []
        for record in self._cases[case_id]:
            rule = FAKE_RULES.get(record.kind)
            if rule is None:
                untranslated.append(
                    UntranslatedFact(
                        source_record=record.record_id,
                        fact=f"kind = {record.kind}",
                        reason=UntranslatedReason.UNKNOWN_VALUE,
                    )
                )
                continue
            if record.at is None:
                untranslated.append(
                    UntranslatedFact(
                        source_record=record.record_id,
                        fact=f"{record.kind} with no time",
                        reason=UntranslatedReason.NO_TIME,
                    )
                )
                continue
            entry = _entry(case_id, len(ledger), record, rule, record.at)
            ledger.append(entry)
            citations.append(
                EntryCitation(
                    entry_id=entry.id_, source_record=record.record_id
                )
            )
            if rule.rule_id is not None and rule.caveat is not None:
                inferences.append(
                    Inference(
                        entry_id=entry.id_,
                        rule_id=rule.rule_id,
                        caveat=rule.caveat,
                    )
                )
        return CaseReading(
            ledger=tuple(ledger),
            citations=tuple(citations),
            inferences=tuple(inferences),
            untranslated=tuple(untranslated),
            unobservable=self.unobservable,
        )
