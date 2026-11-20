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

"""The acts a VINCE translation finds, and the case reading they make.

An :class:`Act` is one ledger entry before it takes its log index.
:func:`render_reading` puts the acts in time order, ties kept in the order
the translation found them, and renders each as a
:class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry` whose
payload is the dump of the act's core activity (ADR-0191 point 2), with its
citation and its inferences.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import JsonValue

from vultron.adapters.connectors.vince.crosswalk import (
    INFERRED_ROWS,
    VINCE_UNOBSERVABLE,
)
from vultron.adapters.connectors.vince.ids import CaseIds
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_reading import (
    CaseReading,
    EntryCitation,
    Inference,
    UntranslatedFact,
)
from vultron.core.models.embargo_termination import TerminationCause
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus

#: The RM states a participant passes through on its way to each state a
#: row sets: a step that skips a state passes through it at the same time
#: (crosswalk § Report management).
RM_PATH: dict[str, tuple[str, ...]] = {
    "RECEIVED": ("RECEIVED",),
    "VALID": ("RECEIVED", "VALID"),
    "ACCEPTED": ("RECEIVED", "VALID", "ACCEPTED"),
    "INVALID": ("RECEIVED", "INVALID"),
    "CLOSED": ("CLOSED",),
}


@dataclass
class Act:
    """One act the translation found, before it takes its log index.

    Attributes:
        rules: The inferred crosswalk rows behind the act, each listed as an
            inference of its entry (CRD-02-002).
        termination_cause: The ``terminationCause`` a
            ``Remove(EmbargoEvent)`` carries (EMB-13-005).
    """

    at: datetime
    semantic_type: MessageSemantics
    activity_type: str
    actor: str
    object_: CoreObject | str
    source_record: str
    label: str
    rules: list[str] = field(default_factory=list)
    target: str | None = None
    termination_cause: TerminationCause | None = None


@dataclass
class Participant:
    """A participant the translation seated, and its RM steps so far."""

    actor: str
    roles: tuple[str, ...]
    vendor: bool = False
    rm: list[tuple[datetime, str]] = field(default_factory=list)
    statuses: list[ParticipantStatus] = field(default_factory=list)

    def rm_at(self, at: datetime) -> str:
        """The participant's RM state at *at*, from the steps so far."""
        reached = [state for when, state in self.rm if when <= at]
        return reached[-1] if reached else "START"


def render_reading(
    ids: CaseIds,
    acts: Sequence[Act],
    untranslated: Sequence[UntranslatedFact],
) -> CaseReading:
    """*acts* in time order, as a case reading with *untranslated*."""
    ledger: list[CaseLedgerEntry] = []
    citations: list[EntryCitation] = []
    inferences: list[Inference] = []
    for index, act in enumerate(sorted(acts, key=lambda a: a.at)):
        entry = _entry(ids, index, act)
        ledger.append(entry)
        citations.append(
            EntryCitation(entry_id=entry.id_, source_record=act.source_record)
        )
        inferences.extend(
            Inference(
                entry_id=entry.id_, rule_id=rule, caveat=INFERRED_ROWS[rule]
            )
            for rule in act.rules
        )
    return CaseReading(
        ledger=tuple(ledger),
        citations=tuple(citations),
        inferences=tuple(inferences),
        untranslated=tuple(untranslated),
        unobservable=VINCE_UNOBSERVABLE,
    )


def _entry(ids: CaseIds, index: int, act: Act) -> CaseLedgerEntry:
    """*act* as the entry at *index*; its activity id names its actor, so
    two participants' acts under one label never share an id."""
    activity = VultronActivity(
        id_=ids.minted(f"activity:{act.actor}:{act.label}"),
        type_=act.activity_type,
        actor=act.actor,
        object_=act.object_,
        target=act.target,
        termination_cause=act.termination_cause,
        context=ids.case_id,
        published=act.at,
        updated=act.at,
    )
    payload: dict[str, JsonValue] = activity.model_dump(
        by_alias=True, mode="json", exclude_none=True
    )
    return CaseLedgerEntry(
        context=ids.case_id,
        log_index=index,
        log_object_id=activity.id_,
        semantic_type=act.semantic_type.value,
        payload_snapshot=payload,
        entry_hash=_content_digest(
            ids.case_id, index, act.semantic_type.value, act.at, payload
        ),
        published=act.at,
        received_at=act.at,
    )


def _content_digest(
    case_id: str,
    log_index: int,
    semantic_type: str,
    at: datetime,
    payload: dict[str, JsonValue],
) -> str:
    """The SHA-256 digest, in hex, of what one translated entry says.

    A reading's entries are never committed, so they carry no CASE_MANAGER
    chain hash: the hash chain is the core ledger's, which a connector may
    not use (ARCH-05-002), and ``prev_log_hash`` stays empty.  The digest
    stands in its place, because a reader of the ledger tells two copies of
    an entry apart by their hashes, and two translations of the same records
    give the same digest.
    """
    content = {
        "context": case_id,
        "logIndex": log_index,
        "semanticType": semantic_type,
        "published": at.isoformat(),
        "payloadSnapshot": payload,
    }
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = ["RM_PATH", "Act", "Participant", "render_reading"]
