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
CRD-02-006).  A record whose rule names an undated fallback, and that states
no time, takes the case's opening time and is listed as an inference
(CRD-02-006).  Every other record comes back untranslated with one reason
each (CRD-01-005, CRD-02-003): a kind no rule names (unknown value), a kind
in :data:`FAKE_NO_COUNTERPART` (no counterpart), a vendor status dated before
the vendor's listing (rule conflict), and a timeless record with no fallback
(no time).

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
    UntranslatedReason as Reason,
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
class FakeInference:
    """A mapping rule's identifier and the caveat it states."""

    rule_id: str
    caveat: str


@dataclass(frozen=True)
class FakeRule:
    """How the fake reader translates one record kind.

    ``inferred`` is set when the rule infers rather than states the entry's
    state; ``undated`` when a record with no time of its own takes the
    case's opening time.
    """

    semantic_type: str
    activity_type: str
    inferred: FakeInference | None = None
    undated: FakeInference | None = None


#: The fake reader's mapping, keyed by record kind.
FAKE_RULES: Mapping[str, FakeRule] = {
    "case_opened": FakeRule("create_case", "Create"),
    "vendor_listed": FakeRule(
        "create_case_participant",
        "Create",
        inferred=FakeInference(
            "FAKE-RM-01",
            "The source lists the vendor; it does not record the notice.",
        ),
        undated=FakeInference(
            "FAKE-TIME-01",
            "The source does not date the listing; the case's opening time"
            " stands in for it.",
        ),
    ),
    "vendor_status": FakeRule("add_participant_status_to_participant", "Add"),
}

#: Record kinds the fake source holds that have no Vultron counterpart.
FAKE_NO_COUNTERPART: frozenset[str] = frozenset({"pinned_post"})

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


def _refusal(
    record: OutsideRecord,
    rule: FakeRule | None,
    at: datetime | None,
    listed_at: Mapping[str, datetime],
) -> UntranslatedFact | None:
    """*record* as an untranslated fact, or ``None`` when it translates."""
    fact, reason = f"kind = {record.kind}", None
    if record.kind in FAKE_NO_COUNTERPART:
        reason = Reason.NO_COUNTERPART
    elif rule is None:
        reason = Reason.UNKNOWN_VALUE
    elif at is None:
        fact, reason = f"{record.kind} with no time", Reason.NO_TIME
    elif record.kind == "vendor_status" and at < listed_at.get(
        record.actor, at
    ):
        fact = f"{record.kind} dated before the vendor's listing"
        reason = Reason.RULE_CONFLICT
    if reason is None:
        return None
    return UntranslatedFact(
        source_record=record.record_id, fact=fact, reason=reason
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
        opened_at: datetime | None = None
        listed_at: dict[str, datetime] = {}

        for record in self._cases[case_id]:
            rule = FAKE_RULES.get(record.kind)
            at = record.at
            implied: list[FakeInference] = []
            if rule and at is None and rule.undated and opened_at:
                at = opened_at
                implied.append(rule.undated)
            refusal = _refusal(record, rule, at, listed_at)
            if refusal is not None:
                untranslated.append(refusal)
                continue
            assert rule is not None and at is not None
            if record.kind == "case_opened":
                opened_at = at
            if record.kind == "vendor_listed":
                listed_at[str(record.value.get("attributedTo"))] = at
            entry = _entry(case_id, len(ledger), record, rule, at)
            ledger.append(entry)
            citations.append(
                EntryCitation(
                    entry_id=entry.id_, source_record=record.record_id
                )
            )
            if rule.inferred is not None:
                implied.insert(0, rule.inferred)
            inferences.extend(
                Inference(
                    entry_id=entry.id_,
                    rule_id=rule_.rule_id,
                    caveat=rule_.caveat,
                )
                for rule_ in implied
            )
        return CaseReading(
            ledger=tuple(ledger),
            citations=tuple(citations),
            inferences=tuple(inferences),
            untranslated=tuple(untranslated),
            unobservable=self.unobservable,
        )
