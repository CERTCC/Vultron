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
    "AuthoredParticipantRecord",
    "CaseBootstrapRequest",
    "CaseProposalRequest",
    "ClosedSenderCheck",
    "LedgerActivityContext",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "RoleOfferRequest",
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
class RoleOfferRequest:
    """The request is a role ``Offer(CaseParticipantRole)``, recorded in the
    case ledger by the CASE_MANAGER of :attr:`SenderCheckContext.case_id`.

    A ``NAMED_ACTOR`` sender must be its target (CM-33-005).

    Attributes:
        offer_id: The Offer the answer names, the recorded Offer or the
            CASE_MANAGER's forward of it; ``None`` when it names none, which
            refuses.
    """

    offer_id: str | None


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
    | RoleOfferRequest
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


@dataclass(frozen=True)
class AuthoredParticipantRecord:
    """An ``AUTHOR`` sender must be the participant this record names.

    The record's ``attributed_to`` is the participant it belongs to, so a
    received ``Add(ParticipantStatus)`` onto it is the sender's statement
    about itself (RSH-08-007).

    Attributes:
        participant_id: The participant record the status is added to.
    """

    participant_id: str


#: The object an ``AUTHOR`` sender must have written.
AuthoredObject = (
    AuthoredNote | AuthoredCaseProposal | AuthoredParticipantRecord
)


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
            CASE_MANAGER this receiver has trusted for the case: the one its
            bootstrap recorded on a completed ``ReportCaseLink``
            (CBT-02-003), else the replica's, else the trust anchor recorded
            with the stub Invite (PCR-03-004).
        case_manager_required: A ``CASE_MANAGER`` sender is refused, rather
            than passed through, when this store holds no case or the case
            names no CASE_MANAGER.
        request: The record holding the request a ``NAMED_ACTOR`` sender
            answers; it picks the addressee check (HP-01-009).  An
            :class:`OwnershipOfferRequest` also makes a ``CASE_OWNER`` sender
            the Case Owner that made the Offer.
        authored_object: The object an ``AUTHOR`` sender must have written;
            it picks the author check (HP-01-009).
        ownership_proposal_id: An ownership-transfer proposal's own id: a
            ``CASE_OWNER`` sender must hold the role, unless it redelivers
            a proposal the CASE_MANAGER already made its Offer from on the
            sender's behalf (CM-21-019, HP-01-003, ADR-0148).
        closing_case_owner: The activity is the Case Owner's
            ``Leave(VulnerabilityCase)``, which closes the case while it is
            not fully closed (CM-23-002, CM-23-018): a ``CASE_OWNER`` sender is
            checked for the role alone, even once its own closure is
            recorded.  The tree's closed-sender door guard
            (:class:`ClosedSenderCheck` with ``case_owner_completes``)
            decides the repeat.
    """

    sender_id: str
    case_id: str | None = None
    invite_id: str | None = None
    invite_is_case_join: bool = False
    case_manager_anchored: bool = False
    case_manager_required: bool = False
    request: AddresseeRequest | None = None
    authored_object: AuthoredObject | None = None
    ownership_proposal_id: str | None = None
    closing_case_owner: bool = False


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


@dataclass(frozen=True)
class ClosedSenderCheck:
    """A door guard: the case must not record the sender's closure (CM-23-018).

    The receive-tree factory builds it on the tree's case, after the
    post-close boundary and before the sender guard, for a tree whose act may
    close its sender.

    Attributes:
        sender_id: The activity's sender.
        case_owner_completes: The act closes the case as well, so a Case
            Owner whose own closure is recorded on a case that is not fully
            closed is not repeating it: its Leave runs to close the case
            (CM-23-002), and the check passes for it.
    """

    sender_id: str
    case_owner_completes: bool = False


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
