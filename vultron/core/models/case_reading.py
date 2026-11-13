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

"""What a case reader returns for one case: a case reading (ADR-0197).

A :class:`CaseReading` has five parts (CRD-02-001):

1. ``ledger`` — the case ledger, as core
   :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry` objects,
   unmarked, so the projection reads it as a native ledger (ADR-0191);
2. ``citations`` — one :class:`EntryCitation` per entry, naming the
   outside-system record it was translated from (CRD-01-004);
3. ``inferences`` — an :class:`Inference` for each state or time of an
   entry that the source implied rather than stated (CRD-02-002, CRD-02-006);
4. ``untranslated`` — one :class:`UntranslatedFact` per fact the reader saw
   and did not translate, each with an :class:`UntranslatedReason`
   (CRD-01-005, CRD-02-003);
5. ``unobservable`` — the :class:`UnobservableFact` declarations the reader
   makes once for its source and copies into every reading (CRD-02-004).

This is a first cut (#6358): each part holds only what a reader has needed
so far, so the Vultron and VINCE case readers can reshape it cheaply.
"""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from itertools import pairwise
from typing import Self

from pydantic import ConfigDict, model_validator

from vultron.core.models.base import ValidatedAssignmentMixin
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.primitives import NonEmptyString


class _ReadingPart(ValidatedAssignmentMixin):
    """A part of a case reading.

    Plain, not a ``CoreObject`` or ``CoreRecord``: a reading is a transient
    answer to one request, never stored and never sent on the wire
    (ADR-0190, ARCH-12-019).  Frozen, because a reading reports what a
    source said and nothing downstream may edit it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class EntryCitation(_ReadingPart):
    """The outside-system record one ledger entry was translated from.

    Attributes:
        entry_id: The cited entry's id (its ledger coordinates).
        source_record: The outside-system record, in a form an analyst can
            find there, such as an API path or URL (CRD-01-004).
    """

    entry_id: NonEmptyString
    source_record: NonEmptyString


class Inference(_ReadingPart):
    """A ledger entry whose state the source implied rather than stated.

    Attributes:
        entry_id: The inferred entry's id.
        rule_id: The identifier of the mapping rule that produced it, as the
            reader's mapping defines it (ADR-0197 point 2).
        caveat: What the source did not say, in words (CRD-02-002).
    """

    entry_id: NonEmptyString
    rule_id: NonEmptyString
    caveat: NonEmptyString


class UntranslatedReason(StrEnum):
    """Why a reader could not turn a fact into a ledger entry (CRD-02-003)."""

    UNKNOWN_VALUE = "unknown_value"
    """The field holds a value no mapping rule names."""

    NO_COUNTERPART = "no_counterpart"
    """The fact has no Vultron counterpart."""

    RULE_CONFLICT = "rule_conflict"
    """The mapping rule's inputs contradict each other."""

    NO_TIME = "no_time"
    """No time the source states can place the fact."""


class UntranslatedFact(_ReadingPart):
    """A fact the source holds for this case that the reader did not translate.

    Attributes:
        source_record: The outside-system record holding the fact.
        fact: The fact, naming its field and value.
        reason: Why it was not translated.
    """

    source_record: NonEmptyString
    fact: NonEmptyString
    reason: UntranslatedReason


class UnobservableFact(_ReadingPart):
    """A fact the source never exposes, for any case (ADR-0197 point 3).

    A consumer reads it as unknown, never as false (CRD-02-005).

    Attributes:
        fact: The state dimension or event the source cannot observe.
        why: Why the source cannot observe it.
    """

    fact: NonEmptyString
    why: NonEmptyString


class CaseReading(_ReadingPart):
    """One outside case, as a case reader returns it (CRD-02-001).

    Built whole or refused: the entries belong to one case, in strictly
    increasing log-index order, each has exactly one citation, and every
    citation and inference names an entry in the ledger, so a consumer never
    meets a dangling reference.

    Attributes:
        ledger: The case ledger entries, in log-index order.
        citations: One per ledger entry.
        inferences: Each state or time the source implied rather than
            stated; an entry may carry more than one.
        untranslated: Each fact the reader saw and did not translate.
        unobservable: The reader's declaration of what its source cannot
            observe, the same in every reading it returns.
    """

    ledger: tuple[CaseLedgerEntry, ...]
    citations: tuple[EntryCitation, ...]
    inferences: tuple[Inference, ...] = ()
    untranslated: tuple[UntranslatedFact, ...] = ()
    unobservable: tuple[UnobservableFact, ...] = ()

    @model_validator(mode="after")
    def _parts_agree(self) -> Self:
        """Refuse a reading whose parts name entries the ledger lacks."""
        problems: list[str] = []
        case_ids = sorted({entry.case_id for entry in self.ledger})
        if len(case_ids) > 1:
            problems.append(f"the ledger holds entries of {case_ids}")
        entry_ids = [entry.id_ for entry in self.ledger]
        repeated = sorted(
            entry_id
            for entry_id, count in Counter(entry_ids).items()
            if count > 1
        )
        if repeated:
            problems.append(f"the ledger repeats entries {repeated}")
        indices = [entry.log_index for entry in self.ledger]
        if any(later <= earlier for earlier, later in pairwise(indices)):
            problems.append(f"the ledger is not in log-index order: {indices}")
        known = set(entry_ids)
        cited = [citation.entry_id for citation in self.citations]
        uncited = sorted(known - set(cited))
        if uncited:
            problems.append(f"entries {uncited} have no citation")
        twice = sorted(
            entry_id for entry_id, count in Counter(cited).items() if count > 1
        )
        if twice:
            problems.append(f"entries {twice} are cited more than once")
        dangling = sorted(
            {entry_id for entry_id in cited if entry_id not in known}
            | {
                inference.entry_id
                for inference in self.inferences
                if inference.entry_id not in known
            }
        )
        if dangling:
            problems.append(f"{dangling} name no entry in the ledger")
        if problems:
            raise ValueError(
                "Inconsistent case reading: " + "; ".join(problems)
            )
        return self


__all__ = [
    "CaseReading",
    "EntryCitation",
    "Inference",
    "UnobservableFact",
    "UntranslatedFact",
    "UntranslatedReason",
]
