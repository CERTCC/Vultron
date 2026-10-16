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

"""What a composed sender guard checks one received activity against.

:class:`SenderCheckContext` names the sender and the records the kinds'
condition nodes read: the request a ``NAMED_ACTOR`` sender answers
(:data:`AddresseeRequest`), the object an ``AUTHOR`` sender wrote
(:data:`AuthoredObject`), and the Invite an ``INVITEE`` sender answers.
The composer, :func:`vultron.core.behaviors.sender_guard.compose_sender_guard`,
reads it to choose each kind's node (HP-01-008, HP-01-009); it re-exports
every name here.

Split out of ``sender_guard.py`` when the composer passed the CS-18-001 size
window: these are plain records with no behaviour.
"""

from dataclasses import dataclass

__all__ = [
    "AddresseeRequest",
    "AuthoredCaseProposal",
    "AuthoredNote",
    "AuthoredObject",
    "CaseBootstrapRequest",
    "CaseProposalRequest",
    "LedgerActivityContext",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "SenderCheckContext",
    "SenderContext",
    "embargo_sender_context",
]


@dataclass(frozen=True)
class CaseProposalRequest:
    """The request is a CaseProposal, recorded on the report case link.

    Attributes:
        report_id: The report the proposal was for (CP-06-005).
    """

    report_id: str


@dataclass(frozen=True)
class ReportOfferRequest:
    """The request is an ``Offer(VulnerabilityReport)``, recorded on this
    store's offer record.

    Attributes:
        offer_id: The Offer the reply names; ``None`` when it names none,
            which refuses (RMB-08-004).
    """

    offer_id: str | None


@dataclass(frozen=True)
class OwnershipOfferRequest:
    """The request is an ownership-transfer Offer, recorded in the case
    ledger by the CASE_MANAGER of :attr:`SenderCheckContext.case_id`.

    A ``NAMED_ACTOR`` sender must be its transferee (CM-21-011); a
    ``CASE_OWNER`` sender must be the Case Owner that made it (CM-21-015).

    Attributes:
        offer_id: The Offer the reply names; ``None`` when it names none,
            which refuses.
        reply_id: The reply's own id, so the offerer check recognises a
            redelivery of the withdrawal that closed the Offer (HP-01-003).
    """

    offer_id: str | None
    reply_id: str


@dataclass(frozen=True)
class CaseBootstrapRequest:
    """The request is the one that asked for a case, recorded on this
    store's report case links.

    A bootstrap ``Create(VulnerabilityCase)`` answers it: the vendor's
    ``CaseProposal`` or the reporter's report ``Offer``, each recorded with
    the actor expected to create the case (CBT-01-005, CBT-01-011).

    Attributes:
        case_id: The case the bootstrap creates.
    """

    case_id: str


#: The record that holds the request a ``NAMED_ACTOR`` sender answers.
AddresseeRequest = (
    CaseProposalRequest
    | ReportOfferRequest
    | OwnershipOfferRequest
    | CaseBootstrapRequest
)


@dataclass(frozen=True)
class AuthoredNote:
    """An ``AUTHOR`` sender must have written this note, and still be an
    active participant of the case (CM-30-001).

    Attributes:
        note_id: The note being removed.
    """

    note_id: str


@dataclass(frozen=True)
class AuthoredCaseProposal:
    """An ``AUTHOR`` sender must be this proposal's proposer, as the
    CASE_MANAGER recorded it for the proposal id (CP-05-010).

    Attributes:
        proposal_id: The proposal the ``Create(CaseProposal)`` carries.
    """

    proposal_id: str


#: The object an ``AUTHOR`` sender must have written.
AuthoredObject = AuthoredNote | AuthoredCaseProposal


@dataclass(frozen=True)
class SenderCheckContext:
    """What the kinds' condition nodes need to check one received activity.

    Attributes:
        sender_id: The activity's sender.
        case_id: The case the activity names; ``None`` for an activity sent
            before any case exists, which is checked against the rule's
            ``outside_case`` side.
        invite_id: The recorded Invite an ``INVITEE`` sender answers.
        invite_is_case_join: The Invite is a case-join Invite, so the record
            must also be one this CASE_MANAGER issued for ``case_id``
            (CM-11-017).
        case_manager_anchored: A ``CASE_MANAGER`` sender is matched against the
            trust anchor the receiver recorded with the stub Invite when the
            replica names no CASE_MANAGER (PCR-03-004).
        case_manager_required: A ``CASE_MANAGER`` sender is refused, rather
            than passed through, when this store holds no case or the case
            names no CASE_MANAGER.
        request: The record holding the request a ``NAMED_ACTOR`` sender
            answers; it picks the addressee check (HP-01-009).  An
            :class:`OwnershipOfferRequest` also makes a ``CASE_OWNER`` sender
            the Case Owner that made the Offer.
        authored_object: The object an ``AUTHOR`` sender must have written;
            it picks the author check (HP-01-009).
        offered_ownership_id: A new ownership-transfer Offer's own id: a
            ``CASE_OWNER`` sender must hold the role, unless it redelivers
            an Offer the CASE_MANAGER recorded from it (CM-21-019,
            HP-01-003).
    """

    sender_id: str
    case_id: str | None = None
    invite_id: str | None = None
    invite_is_case_join: bool = False
    case_manager_anchored: bool = False
    case_manager_required: bool = False
    request: AddresseeRequest | None = None
    authored_object: AuthoredObject | None = None
    offered_ownership_id: str | None = None


@dataclass(frozen=True)
class LedgerActivityContext:
    """The received activity carries a ``CaseLedgerEntry``, which names the case.

    A ledger activity's tree has no case at build time, so the guard's nodes
    read the sender and the case from the activity on the blackboard when the
    tree runs: ``CASE_MANAGER`` from the announced entry (SYNC-13-006), and
    ``LEDGER_PEER`` from the rejected entry (SYNC-03-005).  The guard is
    composed for the activity's case, never for the rule's ``outside_case``
    side, and the rule must state the same kinds at the CASE_MANAGER and at a
    participant: telling the receiver's side apart needs the case at build
    time.
    """


#: Either kind of context :func:`compose_sender_guard` composes a guard for.
SenderContext = SenderCheckContext | LedgerActivityContext


def embargo_sender_context(
    sender_id: str, case_id: str | None
) -> SenderCheckContext:
    """The context an embargo activity's sender is checked in.

    Embargo state is the case's, so the sender's standing is established
    against the case this store holds: a case it does not hold, or one that
    names no CASE_MANAGER, refuses the sender rather than passing it through
    (Regime 1, ADR-0087).  ``Invite``, ``Remove`` and ``Announce`` of an
    ``EmbargoEvent`` share it (EP-09-003, PCR-03-001, PCR-08).
    """
    return SenderCheckContext(
        sender_id=sender_id, case_id=case_id, case_manager_required=True
    )
