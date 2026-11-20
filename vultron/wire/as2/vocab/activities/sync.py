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
"""Wire-layer AS2 activity classes for LedgerFanout/LedgerReconciliation log replication.

Provides :class:`_AddLogEntryActivity` used by the CASE_MANAGER to fan
out canonical log entries to participant actors (ADR-0204), and
:class:`_RejectLogEntryActivity` used by participants to report hash-chain
mismatches back to the CaseActor, and :class:`_ReadLedgerActivity` used by
participants to state their ledger position (SYNC-17-001).
"""

from typing import ClassVar, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_serializer,
    model_validator,
)

from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import case_ledger_id
from vultron.core.models.ledger_position import (
    LEDGER_POSITION_PROPERTY,
    LedgerPosition,
)
from vultron.errors import VultronCanonicalEntryError
from vultron.primitives import NonEmptyString
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Add,
    as_Read,
    as_Reject,
)
from vultron.wire.as2.vocab.base.objects.collections import (
    as_OrderedCollection,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry,
)


class _AddLogEntryActivity(as_Add):
    """The CASE_MANAGER commits an entry: ``Add(CaseLedgerEntry)`` to the ledger.

    Sent to each active participant after the entry is committed to the case
    ledger (SYNC-09-002).  The ``Add`` says the entry was added to the case's
    ledger, ``<case>/ledger``, an ordered collection with identity only
    (ADR-0204).  It is also the positive acknowledgement of the act the entry
    commits, which it names in ``inReplyTo``; it lists nothing in
    ``result``, because each act a commit causes names its cause in its own
    ``inReplyTo``.

    object_: the :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`
        being replicated, inline (SYNC-02-005).
    target: the case's ledger, ``case_ledger_id(entry.case_id)``.
    context: the entry's case.
    in_reply_to: the committed act, the id of the entry's snapshot.

    Spec: SYNC-02-001, SYNC-02-006, SYNC-02-007, SYNC-02-009, MSM-05-009.
    """

    object_: as_CaseLedgerEntry = Field(
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )
    in_reply_to: NonEmptyString = Field(default=...)

    @model_validator(mode="after")
    def _names_the_ledger_the_case_and_the_act(self) -> Self:
        """Refuse an ``Add`` that misnames its ledger, case or act (ADR-0204)."""
        entry = self.object_
        ledger = case_ledger_id(entry.case_id)
        if _as_id(self.target) != ledger:
            raise ValueError(
                f"Add(CaseLedgerEntry) {self.id_!r}: target must be the"
                f" case's ledger {ledger!r}, not {_as_id(self.target)!r}"
                " (SYNC-02-006)"
            )
        if _as_id(self.context) != entry.case_id:
            raise ValueError(
                f"Add(CaseLedgerEntry) {self.id_!r}: context must be the"
                f" entry's case {entry.case_id!r}, not"
                f" {_as_id(self.context)!r} (SYNC-02-006)"
            )
        try:
            act_id = entry.committed_act_id()
        except VultronCanonicalEntryError as exc:
            raise ValueError(str(exc)) from exc
        if self.in_reply_to != act_id:
            raise ValueError(
                f"Add(CaseLedgerEntry) {self.id_!r}: inReplyTo must be the"
                f" committed act {act_id!r}, not {self.in_reply_to!r}"
                " (SYNC-02-007)"
            )
        if self.result is not None:
            raise ValueError(
                f"Add(CaseLedgerEntry) {self.id_!r} lists a result; an act a"
                " commit causes names its cause in its own inReplyTo instead"
                " (SYNC-02-009, ADR-0204)"
            )
        return self


class _RejectLogEntryActivity(as_Reject):
    """Participant rejects an ``Add(CaseLedgerEntry)`` it cannot apply: the gap NAK.

    Sent by a participant actor to the CaseActor when the incoming
    ``Add(CaseLedgerEntry)``'s ``prev_log_hash`` does not match the
    participant's local tail hash.

    The sender's ledger tail, which tells the CaseActor which entries to
    replay (SYNC-03-002), is the activity's ``ledgerPosition``, as on every
    case activity (SYNC-18-001); ``context`` names the case.  A sender that
    does not hold the case yet holds no ledger and states no position.

    object_: :class:`~vultron.wire.as2.vocab.objects.case_ledger_entry.as_CaseLedgerEntry`
        the receiver could not apply.  A replica that holds no entry to
        name states its position with ``Read(<case>/ledger)`` at index -1
        instead (SYNC-16-027, ADR-0204).
    in_reply_to: the id of the inbound activity that prompted the Reject,
        required (RF-08-003, RF-08-004).  The ``object`` is an entry, not an
        activity, so the class cannot derive it.  On a hash mismatch and on
        the genesis Reject for a case the sender does not hold it is the
        ``Add(CaseLedgerEntry)`` that carried the entry (SYNC-03-001,
        ADR-0204); after a case copy ahead of the chain it is the
        ``Announce(VulnerabilityCase)`` (SYNC-16-007).  The
        ``Create(ProcessingFault)`` for a refused entry names its ``Add``
        the same way (SYNC-16-003).

    Spec: SYNC-03-001, SYNC-03-002, SYNC-16-007, SYNC-18-001, RF-08-004.
    """

    object_: as_CaseLedgerEntry = Field(
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )
    in_reply_to: NonEmptyString = Field(default=...)


class _ReadLedgerActivity(as_Read):
    """Participant states its ledger position: ``Read(<case>/ledger)``.

    Sent by a participant to the case's CASE_MANAGER to state how far it
    has applied the case's ledger (SYNC-17-001, ADR-0204).  The CASE_MANAGER
    replays every entry after the stated position (SYNC-17-004), so a
    position behind its tail, or the empty ledger's at index -1, asks for a
    replay.

    object_: the case's ledger, the ``OrderedCollection``
        ``case_ledger_id(context)`` named by its id and type; identity only
        (ADR-0204).
    context: the case whose ledger it is.
    ledger_position: the sender's tail, the ``logIndex`` and ``entryHash``
        of the last entry it holds, or index -1 and the case's genesis hash
        when it holds none, so the CASE_MANAGER can tell a lag from a
        position its ledger does not hold (SYNC-17-005).

    Spec: SYNC-17-001, SYNC-16-027.
    """

    object_: as_OrderedCollection = Field(  # type: ignore[assignment]
        default=...,
        validation_alias="object",
        serialization_alias="object",
    )
    context: NonEmptyString = Field(  # type: ignore[assignment]
        default=...,
    )
    #: The ledger is identity only and has no record of its own, so storage
    #: keeps it inline: collapsed to its id, it could not be read back
    #: (DL-08-001, ADR-0204).
    inline_required_refs: ClassVar[frozenset[str]] = frozenset({"object_"})
    ledger_position: LedgerPosition = Field(  # type: ignore[assignment]
        default=...,
        validation_alias="ledgerPosition",
        serialization_alias="ledgerPosition",
        json_schema_extra=LEDGER_POSITION_PROPERTY,
    )

    @field_serializer("object_", mode="wrap")
    def _ledger_as_identity(
        self,
        ledger: as_OrderedCollection,
        handler: SerializerFunctionWrapHandler,
    ) -> object:
        """The ledger without its ``items``: it is identity only (ADR-0204).

        An empty ``items`` would read as a claim that the ledger holds no
        entry, which is the ``ledgerPosition``'s to state.
        """
        dumped = handler(ledger)
        if isinstance(dumped, dict):
            dumped.pop("items", None)
        return dumped

    @model_validator(mode="after")
    def _reads_its_cases_ledger(self) -> Self:
        """Refuse a ``Read`` whose object is not its case's ledger (ADR-0204)."""
        ledger = case_ledger_id(self.context)
        if self.object_.id_ != ledger:
            raise ValueError(
                f"Read {self.id_!r}: object must be the case's ledger"
                f" {ledger!r}, not {self.object_.id_!r} (SYNC-17-001)"
            )
        if self.object_.items:
            raise ValueError(
                f"Read {self.id_!r}: the ledger is identity only and carries"
                " no items; the ledgerPosition states the position"
                " (SYNC-17-001, ADR-0204)"
            )
        return self
