#!/usr/bin/env python
"""This module provides base activity classes"""

#  Copyright (c) 2025 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

import json
from collections.abc import Sequence
from typing import Any, Self

from pydantic import (
    Field,
    PrivateAttr,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from vultron.core.models.actor import CoreActor
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.sender_sequence import SenderSequence
from vultron.core.models.verified_proof import VerifiedProof
from vultron.wire.as2.enums import as_ObjectType as O_type
from vultron.wire.as2.vocab.base.base import VULTRON_PROPERTY_EXTRA
from vultron.wire.as2.vocab.base.links import ActivityStreamRef
from vultron.wire.as2.vocab.base.objects.actors import as_ActorRef
from vultron.wire.as2.vocab.base.objects.base import as_Object, as_ObjectRef


class as_Activity(as_Object):
    """https://www.w3.org/TR/activitystreams-vocabulary/#dfn-activity
    An Activity is a subtype of Object that describes some form of action that may happen, is
    currently happening, or has already happened. The Activity type itself serves as an abstract
    base type for all types of activities. It is important to note that an Activity is not a
    representation of a currently executing process, but rather a statement about that process.
    For example, a person walking down the street is not an Activity unless they are posting a
    picture of themselves walking down the street. The Activity in that case would be the posting
    of the picture, not the person walking down the street.
    """

    type_: str = Field(
        default=O_type.ACTIVITY,
        validation_alias="type",
        serialization_alias="type",
    )

    # All four slots admit a core object, not just ``actor``.
    #
    # Widening only ``actor`` (and ``as_ObjectRef``, for ``object_``) left
    # ``target``/``origin``/``instrument`` declaring a wire-only union while the
    # adapters put promoted core classes in them.  A value outside its declared
    # union escapes in both directions: outbound, Pydantic emits
    # ``PydanticSerializationUnexpectedValue`` and ships a payload shaped by the
    # wrong schema; inbound, a payload from an unmodified peer is refused. That is
    # what made every recipient answer ``422`` to ``Create(VulnerabilityCase)`` and
    # never seed the case replica (ADR-0041, PCR-01-003).
    #
    # The type errors this produced on the subclass overrides were suppressed with
    # ``# type: ignore[assignment]`` rather than fixed, which is why mypy and
    # pyright stayed green while the wire protocol did not work. Widening here is
    # what lets those suppressions be deleted: a subclass narrowing
    # ``target`` to ``VulnerabilityCase | as_Link | NonEmptyString | None`` is
    # now a genuine narrowing of this union rather than an incompatible override.
    #
    # The slots go through the shared reference aliases so the IRI branch is
    # ``NonEmptyString`` (CS-08-001, CS-08-002) rather than a hand-spelled
    # ``str`` that admits a blank reference.
    actor: as_ActorRef | CoreActor
    target: as_ObjectRef = None
    origin: as_ObjectRef = None
    instrument: as_ObjectRef = None
    result: ActivityStreamRef[as_Object] = None

    # SYNC-18-001 (ADR-0156): an activity about a case whose ledger its
    # sender holds states the sender's ledger tail as the Vultron property
    # ``ledgerPosition``, the term a case copy already uses (SYNC-16-005).
    # Declared on the base so every inbound activity keeps it through the
    # parse (MV-11-003), and ``LedgerPosition`` refuses a malformed one at the
    # edge.  Set only by ``vultron.wire.as2.factories`` (SYNC-18-008); which
    # received activities must carry it is the event model's call
    # (SYNC-18-015).
    ledger_position: LedgerPosition | None = Field(
        default=None,
        validation_alias="ledgerPosition",
        serialization_alias="ledgerPosition",
        json_schema_extra=VULTRON_PROPERTY_EXTRA,
    )

    # SYNC-21-001 (ADR-0178): a participant numbers each case activity it
    # sends the CASE_MANAGER that states a ``ledgerPosition``, except a
    # ``Read`` or ``Reject`` of a ledger entry, with the Vultron property
    # ``senderSequence``: 1 for its first on the case, one more after that.
    # Declared on the base for the reason ``ledger_position`` is, so every
    # inbound activity keeps it through the parse (MV-11-003).  Set only by
    # ``vultron.wire.as2.factories`` (SYNC-21-004).
    sender_sequence: SenderSequence | None = Field(
        default=None,
        validation_alias="senderSequence",
        serialization_alias="senderSequence",
        json_schema_extra=VULTRON_PROPERTY_EXTRA,
    )

    #: The JSON body as received, decoded and re-serialized to text by
    #: ``parse_activity`` before anything reads or expands it (VM-08-002).
    #: Keys, key order and values are the sender's; whitespace, number
    #: spelling and escapes are not kept, because the body arrives decoded.
    #: ``frozen=True`` covers this activity's own fields, but it does not reach
    #: the nested objects: since ARCH-25-003 (ADR-0099) most of those are mutable core
    #: classes.  So the received evidence is kept here as an immutable ``str``,
    #: independent of the object graph, rather than being inferred from the
    #: graph's class configuration (ISSUE-3584).  ``None`` on an activity this
    #: process authored or rebuilt from storage.  Pydantic's ``==`` compares
    #: private attributes, so a sealed activity is unequal to an otherwise
    #: identical copy without evidence.
    _received_evidence: str | None = PrivateAttr(default=None)

    @property
    def received_evidence_json(self) -> str | None:
        """The received JSON as the text it was sealed with, or ``None``."""
        return self._received_evidence

    @property
    def received_evidence(self) -> dict[str, Any] | None:
        """A fresh copy of the received JSON, or ``None`` if none was sealed.

        Every call decodes a new ``dict``, so what a caller does to the result
        cannot reach the sealed evidence or any other caller's copy.
        """
        if self._received_evidence is None:
            return None
        evidence: dict[str, Any] = json.loads(self._received_evidence)
        return evidence

    def seal_received_evidence(self, evidence_json: str) -> None:
        """Attach the received JSON to this activity, exactly once.

        Pydantic leaves private attributes writable on a frozen model, so the
        write-once rule is enforced here: resealing with the same text is a
        no-op (a routing copy inheriting its artifact's evidence), and any other
        text raises, because two different claims about what arrived cannot both
        be the evidence.

        Raises:
            ValueError: If different evidence is already sealed.
        """
        current = self._received_evidence
        if current is not None and current != evidence_json:
            raise ValueError(
                f"{type(self).__name__} {self.id_!r} already carries different "
                "received evidence; received evidence is sealed once (VM-08-002)."
            )
        self._received_evidence = evidence_json

    #: The proofs the inbox verified on the body this activity was parsed
    #: from, each with the key it verified against as fetched (SIG-03-004).
    #: Like the evidence, carried beside the object graph and never part of
    #: a dump; empty on an activity no inbox verified.
    _verified_proofs: tuple[VerifiedProof, ...] = PrivateAttr(default=())

    @property
    def verified_proofs(self) -> tuple[VerifiedProof, ...]:
        """The proofs the inbox verified on this activity's received body."""
        return self._verified_proofs

    def seal_verified_proofs(self, proofs: Sequence[VerifiedProof]) -> None:
        """Attach the proofs the inbox verified on this activity, once.

        Sealing the same proofs again, or none, is a no-op; other proofs
        raise, since two accounts of what verified cannot both be true.

        Raises:
            ValueError: If different proofs are already sealed.
        """
        sealed = tuple(proofs)
        if not sealed or sealed == self._verified_proofs:
            return
        if self._verified_proofs:
            raise ValueError(
                f"{type(self).__name__} {self.id_!r} already carries"
                " different verified proofs; they are sealed once"
                " (SIG-03-004)."
            )
        self._verified_proofs = sealed

    #: Set only by :meth:`inlined_as_received`: the AS2 form of this copy is
    #: its received evidence, verbatim (DL-06-004, ADR-0149).
    _inline_as_received: bool = PrivateAttr(default=False)

    def inlined_as_received(self) -> Self:
        """A copy of this received activity whose AS2 form is the body received.

        For a reply that embeds the activity it answers (an embargo
        ``Accept`` of an ``Invite``, a refusal notice, a case proposal's
        inline report ``Offer``).  The Actor Knowledge Model asks for the
        activity as its sender sent it, and the parsed graph is not that: the
        parse sets aside a key the vocabulary does not name (MV-11-003), and
        a dump renders defaults the sender did not send.  So the copy's
        ``by_alias`` dump is the sealed received evidence itself, every key
        and value as it arrived (VM-08-002), while the copy is still the
        validated activity for the reply's own construction.  A storage dump
        (``by_alias=False``) is unchanged.

        Raises:
            ValueError: When this activity carries no received evidence, so
                there is no body to embed.
        """
        if self._received_evidence is None:
            raise ValueError(
                f"{type(self).__name__} {self.id_!r} carries no received"
                " evidence to embed as received (VM-08-002)"
            )
        copy = self.model_copy()
        copy._inline_as_received = True
        return copy

    @model_serializer(mode="wrap")
    def _serialize_as_received(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> Any:
        """The received body on the AS2 path of an inlined-as-received copy.

        Any other dump places ``@context`` as ``as_Base`` does (VM-10-001); this
        serializer replaces that one, so it delegates to it.
        """
        if self._inline_as_received and info.by_alias:
            return self.received_evidence
        return self._as2_document(handler, info)

    def description(self):
        raise NotImplementedError


def main():
    x = as_Activity(
        actor="https://example.org/actor", published=None, updated=None
    )
    print(x.to_json(indent=2))


if __name__ == "__main__":
    main()
