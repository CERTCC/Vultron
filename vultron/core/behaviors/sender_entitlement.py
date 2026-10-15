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

"""One sender-entitlement module: predicates, condition nodes, and declarations.

This is the single home for every sender predicate and its condition node
(ADR-0115, HP-01-006, HP-01-007).
No sender check may be defined elsewhere; the architecture ratchet in
``test/architecture/test_sender_entitlement_ratchet.py`` enforces this.

Entitlement kinds
-----------------
- ``CASE_MANAGER`` — sender must be the case's ``CVDRole.CASE_MANAGER``
  (PCR-03-001, SYNC-13-006)
- ``CASE_OWNER`` — sender must hold ``CVDRole.CASE_OWNER``
- ``ACTIVE_PARTICIPANT`` — sender must be an active participant per CM-10-004
  (joined and a signatory to the embargo in force) whose closure the case does
  not record: a participant at RM ``CLOSED`` may act on nothing further
  (CM-23-018).  Every guard for it asks one predicate,
  :func:`~vultron.core.participants.recipients.may_act_on_case`
- ``PARTICIPANT`` — sender must have a participant record on the case, active
  or not, whose closure the case does not record (CM-23-018)
- ``LEDGER_PEER`` — sender must be an active participant per CM-10-004, at RM
  ``CLOSED`` or not: the one standing for a ``Reject(CaseLedgerEntry)``
  resync request, whose replay to a closed peer stops at its own closure
  entries (SYNC-03-005, CM-23-004, CM-23-018)
- ``NAMED_ACTOR`` — sender must be the addressee of the request it answers, as
  this store recorded it: the one addressee kind (HP-01-009, ADR-0129)
- ``INVITEE`` — sender must be the sole ``to`` recipient of the recorded Invite
  it answers (EP-09-010, CM-11-017)
- ``AUTHOR`` — sender must be the author of the object it sends or changes, as
  this store recorded it: a note's author, who must also be an active
  participant (CM-30-001), or a case proposal's proposer (CP-05-010)
  (HP-01-009)
- ``ANY_ACTOR`` — any actor may send it, whatever its standing in any case: a new
  report, which precedes any case (HP-01-010, HP-01-011).
  It is a declared rule, not an exemption, and has no condition node: there is
  no standing to check, so no tree composes a sender guard for it.

Each kind declares its "Sent by" wording and its glossary term
(``SenderEntitlementKind.sent_by``, ``SenderEntitlementKind.term``;
MSM-08-010).

Sender rules
------------
A received use case declares a ``SenderRule`` (HP-01-008, ADR-0129): per
addressee side (the CASE_MANAGER, a participant, an actor outside any case),
an any-of set of kinds.  ``SenderRule.in_case(kind)`` states the same kinds at
the CASE_MANAGER and at a participant; ``SenderRule.to_case_manager(kind)``
states the kinds at the CASE_MANAGER and the CASE_MANAGER at a participant
(PCR-03-001); ``SenderRule.before_case(kind)`` states the side for an activity
sent before any case exists.  ``AddresseeSide`` names the three sides, and
``SenderRule.side(addressee)`` reads one; an occasion declares its addressee
as a side (MSM-08-009).  The receive-tree
factory composes the guard from the rule
(``vultron.core.behaviors.sender_guard.compose_sender_guard``).

A tree cannot pass a guard of its own.  The ratchet in
``test/architecture/test_sender_entitlement_ratchet.py`` fails on any of these
nodes named outside this module and the composer, unless an allow-list names
the site: a guard not yet migrated names the open issue that migrates it, and
a standing read that picks an effect after admission says why it admits no
one (HP-01-007, #4437).

Exemption
---------
``exempt(tracking_issue, reason)`` declares a received use case as not yet
checked, naming the tracking issue that owns the fix.
The ratchet accepts an exemption as a valid declaration; it only fails on a
missing attribute.

Nodes
-----
- ``SenderIsParticipantNode`` — guards that the case lists a participant
  record for the sender whose closure is not recorded (``PARTICIPANT``;
  CM-23-018); merged from ``VerifySenderIsParticipantNode``
- ``SenderIsActiveParticipantNode`` — guards that the sender is an active
  participant whose closure is not recorded (``ACTIVE_PARTICIPANT``;
  CM-10-004, CM-23-018)
- ``SenderIsActiveLedgerParticipantNode`` — guards that the sender is an active
  participant, closed or not, of the case named by a ledger activity on the
  blackboard (``LEDGER_PEER`` kind; SYNC-03-005)
- ``SenderIsCaseManagerNode`` — guards that the sender is the case's
  CASE_MANAGER; merged from ``VerifySenderIsCaseActorNode`` and, as the check
  that the CASE_MANAGER's own announcement came from itself, from
  ``SenderIsNamedActorNode`` (#4437)
- ``SenderIsRequestAddresseeNode`` — the shared base of the addressee checks:
  each subclass reads one kind of recorded request, and the base compares the
  sender with its addressees and words the refusal (``NAMED_ACTOR``; HP-01-009)
- ``SenderIsProposalAddresseeNode`` — guards that the sender is the actor the
  vendor addressed a CaseProposal to, as recorded on the report case link
  (``NAMED_ACTOR`` kind; CP-06-005)
- ``SenderIsOfferAddresseeNode`` — guards that the sender is an actor the
  ``Offer(VulnerabilityReport)`` was addressed to, as recorded on this store's
  offer record (``NAMED_ACTOR`` kind; RMB-08-004)
- ``SenderIsInviteeNode`` — guards that the sender is the sole ``to``
  recipient of the recorded Invite it answers (EP-09-010)
- ``SenderIsOwnershipTransfereeNode`` — guards that the sender of an answer
  to an ownership-transfer Offer is the transferee of the Offer the
  CASE_MANAGER recorded (``NAMED_ACTOR`` kind; CM-21-011, CM-21-013)
- ``SenderIsOwnershipOffererNode`` — guards that the sender of a withdrawal
  is the Case Owner that made the Offer the CASE_MANAGER recorded
  (``CASE_OWNER`` kind; CM-21-015).  Whether that Offer is still open is a
  precondition guard after the sender check
  (``vultron.core.behaviors.case.nodes.ownership_offer_guard``)
- ``SenderIsOfferingCaseOwnerNode`` — guards that the sender of a new
  ownership-transfer Offer holds CVDRole.CASE_OWNER, or is the recorded sender
  of the Offer it redelivers (``CASE_OWNER`` kind; CM-21-019)
- ``SenderIsCaseOwnerNode`` — guards that the sender holds CVDRole.CASE_OWNER;
  merged from ``CheckIsCaseOwnerNode``
- ``SenderIsNoteAuthorNode`` — guards that the sender is the note's author and
  an active participant whose closure is not recorded (``AUTHOR`` kind;
  CM-30-001, CM-23-018)
- ``SenderIsProposalAuthorNode`` — guards that the sender of a
  ``Create(CaseProposal)`` is the proposer this store recorded for the
  proposal id, when it recorded one (``AUTHOR`` kind; CP-05-010)
- ``SenderClosureNotRecordedNode`` — guards that the case does not record the
  sender's closure; the closed-sender pre-flight runs it to tell a repeated
  closing act (``SKIPPED``) from any other act (``REFUSED``) (CM-23-018)
- ``NoSenderAdmittedNode`` — refuses every sender on a side a ``SenderRule``
  leaves empty (HP-01-008)
- ``SenderHoldsNoneOfNode`` — the last arm of an any-of side, naming every
  standing the side accepts (HP-01-008)

Helper predicate
----------------
``is_case_owner(case, actor_id)`` — pure boolean predicate; merged from
``_is_case_owner`` in ``vultron.core.use_cases.triggers._helpers``.

Spec: HP-01-006, HP-01-007, CM-10-004, PCR-03-001.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Self

from py_trees.common import Status
from py_trees.ports import NoDataAvailable, PortInformation

from vultron.core.behaviors.helpers import (
    DataLayerConditionWithPorts,
    FindParticipantByActorIdNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_proposal_admission import (
    CaseProposalAdmissionRecord,
)
from vultron.core.models.case_proposal_decline import (
    CaseProposalDeclineRecord,
)
from vultron.core.models.offer_record import VultronOfferRecord
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.participants.authority import resolve_case_manager_id
from vultron.core.participants.ownership_offer import (
    RecordedOwnershipOffer,
    recorded_ownership_offer,
    recorded_ownership_offer_sender,
)
from vultron.core.participants.recipients import (
    closure_recorded,
    is_case_content_recipient,
    may_act_on_case,
)
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.predicates.addressing import (
    distinct_recipients,
    is_addressed_to,
    same_actor_id,
)
from vultron.core.predicates.roles import has_case_owner_role
from vultron.errors import VultronError, VultronNotFoundError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helper (inlined to avoid cross-module private import)
# ---------------------------------------------------------------------------


def _log_entry_from(activity: Any, node_name: str) -> CaseLedgerEntry:
    """Return the ``CaseLedgerEntry`` from *activity*, or raise.

    Checks ``activity.log_entry`` first, then ``activity.object_``.
    Raises :class:`~vultron.errors.VultronError` when neither carries a
    :class:`~vultron.core.models.case_ledger_entry.CaseLedgerEntry`.
    """
    entry = getattr(activity, "log_entry", None)
    if entry is None:
        entry = getattr(activity, "object_", None)
    if isinstance(entry, CaseLedgerEntry):
        return entry
    raise VultronError(
        f"{node_name}: activity did not carry a CaseLedgerEntry"
    )


# ---------------------------------------------------------------------------
# Declaration types
# ---------------------------------------------------------------------------


def _numbered_member[E: Enum](cls: type[E]) -> E:
    """A new member of the enum *cls*, valued by its declaration position.

    The declared tuple carries the member's wording, so its value is numbered
    as ``auto()`` would number it.
    """
    member = object.__new__(cls)
    member._value_ = len(cls.__members__) + 1
    return member


class SenderEntitlementKind(Enum):
    """One sender standing a :class:`SenderRule` may require.

    Each kind corresponds to one condition node in this module, except
    ``ANY_ACTOR``, which requires no standing and so has no guard.
    A use case never declares a kind on its own: it declares a
    :class:`SenderRule` composed of kinds (HP-01-008).

    Each kind also declares how a "Sent by" value words it and the glossary
    term that defines it (MSM-08-010, ADR-0129):

    - :attr:`sent_by` is the wording.  A position held within one exchange
      names the object it is held over with an ``{object}`` placeholder,
      filled from the object type of the activity the sender answers or
      changes: ``NAMED_ACTOR`` reads "the addressee of the case proposal"
      for ``Accept(CaseProposal)``, whatever the request (HP-01-009).
    - :attr:`term` is the term's bold name in ``docs/reference/glossary.md``.
    """

    sent_by: str
    term: str

    def __new__(cls, sent_by: str, term: str) -> Self:
        member = _numbered_member(cls)
        member.sent_by = sent_by
        member.term = term
        return member

    CASE_MANAGER = ("the case manager", "Case Manager")
    """Sender must be the case's ``CVDRole.CASE_MANAGER``."""

    CASE_OWNER = ("the case owner", "Case Owner")
    """Sender must hold ``CVDRole.CASE_OWNER``."""

    ACTIVE_PARTICIPANT = ("an active participant", "Active Participant")
    """Sender must be an active participant whose closure is not recorded.

    Active per CM-10-004: joined and, while an embargo is in force, a
    signatory to it; a removed participant is not active.  And not at RM
    ``CLOSED``: a participant that has left the case may act on nothing
    further (CM-23-018).  Every guard for this kind asks one predicate,
    :func:`~vultron.core.participants.recipients.may_act_on_case`.  Compare
    ``PARTICIPANT``, which any open participant record on the case satisfies.
    """

    PARTICIPANT = ("a participant", "Participant")
    """Sender must have a participant record on the case, not closed.

    The record may be inert or removed: an invitee that has not answered and a
    removed participant both hold one.  A record at RM ``CLOSED`` does not:
    that participant has left the case (CM-23-018).  Use
    ``ACTIVE_PARTICIPANT`` when the sender must be entitled to the case's
    content (CM-10-004).
    """

    LEDGER_PEER = (
        "an active participant, including one that has left the case",
        "Active Participant",
    )
    """Sender must be an active participant, at RM ``CLOSED`` or not.

    The standing of a ``Reject(CaseLedgerEntry)`` resync request
    (SYNC-03-005): a closed participant keeps it, and the replay it is
    answered with stops at the entries that record its own closure
    (CM-23-004, CM-23-018).  No other use case declares it.
    """

    NAMED_ACTOR = ("the addressee of the {object}", "Addressee")
    """Sender must be the addressee of the request it answers (HP-01-009).

    The one addressee kind, whatever the request: the receiver checks the
    sender against the addressee it recorded for the request (the case
    proposal's report case link, the report Offer's record, the ledgered
    ownership-transfer Offer), never against the copy the reply embeds.
    A transferee whose closure the case records is refused (CM-23-018).
    """

    INVITEE = ("the invitee", "Invitee")
    """Sender must be the sole ``to`` recipient of the recorded Invite.

    An invitee whose closure the case records (RM ``CLOSED``) is refused: it
    has left the case and may answer nothing further (CM-23-018).
    """

    AUTHOR = ("the {object}'s author", "Author")
    """Sender must be the author of the object it sends or changes (HP-01-009).

    The author is the object's ``attributed_to`` as this store recorded it.
    A note's author must still be an active participant of the case
    (CM-10-004, CM-30-001).  A case proposal's author is the proposer the
    CASE_MANAGER recorded for its proposal id when it admitted, declined or
    stored it; a proposal id it has not recorded is a new proposal, whose
    author the parse edge has already matched to the sender (CP-05-010,
    CP-01-010).
    """

    ANY_ACTOR = ("any actor", "Actor")
    """Any actor may send it; no standing is required (HP-01-010).

    Declared only by the use cases that receive a new report, which precedes
    any case (HP-01-011).  It has no condition node, so no tree composes a
    sender guard for it.
    """

    def worded(self, object_words: str) -> str:
        """The "Sent by" words for this kind, its ``{object}`` placeholder
        filled with *object_words* ("case proposal") when it has one."""
        return self.sent_by.format(object=object_words)


class AddresseeSide(Enum):
    """Whom an activity is sent to: one side of a :class:`SenderRule`.

    The sides are the standings a receiver can hold for one activity: the
    case's CASE_MANAGER, any other participant of the case, or, for an
    activity sent before a case exists, an actor outside any case
    (HP-01-008).  An occasion declares its addressee as one of them, which
    picks the side of its use case's rule that gives "Sent by" and renders
    as "Send to" (MSM-08-009, ADR-0129).

    Like a kind, each side declares its :attr:`send_to` wording and the
    glossary :attr:`term` that defines it.
    """

    send_to: str
    term: str

    def __new__(cls, send_to: str, term: str) -> Self:
        member = _numbered_member(cls)
        member.send_to = send_to
        member.term = term
        return member

    CASE_MANAGER = ("the case manager", "Case Manager")
    """Sent to the case's CASE_MANAGER (``SenderRule.at_case_manager``)."""

    PARTICIPANT = ("a participant", "Participant")
    """Sent to a participant other than the CASE_MANAGER
    (``SenderRule.at_participant``)."""

    OUTSIDE_CASE = ("an actor outside any case", "Actor")
    """Sent before any case exists, to an actor outside any case
    (``SenderRule.outside_case``)."""


@dataclass(frozen=True)
class SenderExemption:
    """Declaration that a received use case is not yet sender-checked.

    The ``tracking_issue`` names the sibling issue that will add the real
    check.
    The ratchet accepts this as a valid declaration.

    Attributes:
        tracking_issue: GitHub issue reference, e.g. ``"#4072"``.
        reason: Human-readable reason the check is deferred.
    """

    tracking_issue: str
    reason: str = ""


def any_of(*kinds: SenderEntitlementKind) -> frozenset[SenderEntitlementKind]:
    """The kinds one side of a :class:`SenderRule` admits, any one sufficing."""
    return frozenset(kinds)


def in_declaration_order(
    kinds: frozenset[SenderEntitlementKind],
) -> list[SenderEntitlementKind]:
    """*kinds* in the enum's declaration order, so composition and wording
    are deterministic."""
    return [kind for kind in SenderEntitlementKind if kind in kinds]


@dataclass(frozen=True)
class SenderRule:
    """The full sender rule a received use case declares (HP-01-008, ADR-0129).

    Each field is one addressee side: the standing a sender needs when the
    activity is addressed to the CASE_MANAGER, to a participant, or, for an
    activity sent before a case exists, to an actor outside any case.
    A side holds an any-of set of kinds: the sender is entitled when it holds
    any one of them.  An empty side admits no sender, so an activity addressed
    to that side is refused.

    The receive-tree factory composes the guard from the rule alone
    (:func:`vultron.core.behaviors.sender_guard.compose_sender_guard`).

    Attributes:
        at_case_manager: Kinds that entitle a sender at the CASE_MANAGER.
        at_participant: Kinds that entitle a sender at any other participant.
        outside_case: Kinds that entitle a sender of an activity that names no
            case, addressed to an actor outside any case.

    Raises:
        ValueError: The rule states no side, a side holds something other than
            a :class:`SenderEntitlementKind`, or ``ANY_ACTOR`` shares a side
            with another kind (it already admits every sender).
    """

    at_case_manager: frozenset[SenderEntitlementKind] = frozenset()
    at_participant: frozenset[SenderEntitlementKind] = frozenset()
    outside_case: frozenset[SenderEntitlementKind] = frozenset()

    def __post_init__(self) -> None:
        sides = (self.at_case_manager, self.at_participant, self.outside_case)
        if not any(sides):
            raise ValueError("A SenderRule must state at least one side")
        for side in sides:
            if not isinstance(side, frozenset) or not all(
                isinstance(kind, SenderEntitlementKind) for kind in side
            ):
                raise ValueError(
                    "Each side of a SenderRule is a frozenset of"
                    f" SenderEntitlementKind members, got {side!r}"
                )
            if SenderEntitlementKind.ANY_ACTOR in side and len(side) > 1:
                raise ValueError(
                    "ANY_ACTOR admits every sender, so it cannot share a side"
                    f" with other kinds: {sorted(k.name for k in side)}"
                )

    @classmethod
    def in_case(cls, *kinds: SenderEntitlementKind) -> "SenderRule":
        """The same kinds entitle a sender at the CASE_MANAGER and at a participant."""
        return cls(
            at_case_manager=any_of(*kinds), at_participant=any_of(*kinds)
        )

    @classmethod
    def to_case_manager(cls, *kinds: SenderEntitlementKind) -> "SenderRule":
        """The kinds entitle a sender at the CASE_MANAGER, and a participant
        takes the change from the CASE_MANAGER alone (PCR-03-001)."""
        return cls(
            at_case_manager=any_of(*kinds),
            at_participant=any_of(SenderEntitlementKind.CASE_MANAGER),
        )

    @classmethod
    def before_case(cls, *kinds: SenderEntitlementKind) -> "SenderRule":
        """The kinds entitle the sender of an activity sent before any case exists."""
        return cls(outside_case=any_of(*kinds))

    @property
    def kinds(self) -> frozenset[SenderEntitlementKind]:
        """Every kind the rule names, on any side."""
        return self.at_case_manager | self.at_participant | self.outside_case

    def side(
        self, addressee: AddresseeSide
    ) -> frozenset[SenderEntitlementKind]:
        """The kinds that entitle a sender of an activity sent to *addressee*.

        An empty set means the rule admits no sender on that side
        (MSM-08-009).
        """
        match addressee:
            case AddresseeSide.CASE_MANAGER:
                return self.at_case_manager
            case AddresseeSide.PARTICIPANT:
                return self.at_participant
            case AddresseeSide.OUTSIDE_CASE:
                return self.outside_case


#: Union type for the per-use-case ``sender_entitlement`` class variable: a
#: full sender rule, or an exemption naming the issue that owns the check.
SenderEntitlement = SenderRule | SenderExemption


def exempt(tracking_issue: str, reason: str = "") -> SenderExemption:
    """Declare a received use case as not yet sender-checked.

    Usage on a received use-case class::

        class MyReceivedUseCase:
            sender_entitlement: ClassVar[SenderEntitlement] = exempt(
                "#4072", "pending fix for accept/reject case proposal"
            )

    Args:
        tracking_issue: GitHub issue that owns the fix, e.g. ``"#4072"``.
        reason: Short rationale for the deferral.

    Returns:
        A :class:`SenderExemption` instance.
    """
    return SenderExemption(tracking_issue=tracking_issue, reason=reason)


# ---------------------------------------------------------------------------
# Pure-predicate helper
# ---------------------------------------------------------------------------


def is_case_owner(case: object | None, actor_id: str) -> bool:
    """Return ``True`` when *actor_id* matches the case's attributed owner.

    Consolidated from ``_is_case_owner`` in
    ``vultron.core.use_cases.triggers._helpers`` (ADR-0115, AC-2).

    Args:
        case: The ``VulnerabilityCase`` object (or ``None``).
        actor_id: The actor ID to test.

    Returns:
        ``True`` when the case's ``attributed_to`` matches *actor_id*;
        ``False`` when the case is ``None`` or the owner does not match.
    """
    if case is None:
        return False
    owner_id = _as_id(getattr(case, "attributed_to", None))
    return owner_id is not None and owner_id == actor_id


def _holds_case_owner_role(
    datalayer: CasePersistence, case: VulnerabilityCase, actor_id: str
) -> bool:
    """Return ``True`` when *actor_id*'s participant record holds CASE_OWNER."""
    participant_id = next(
        (
            pid
            for aid, pid in case.actor_participant_index.items()
            if same_actor_id(aid, actor_id)
        ),
        None,
    )
    if participant_id is None:
        return False
    participant = datalayer.read(participant_id)
    if not isinstance(participant, CaseParticipant):
        return False
    return has_case_owner_role(
        list(participant.roles) if participant.roles else []
    )


# ---------------------------------------------------------------------------
# Base class: marks nodes as sender-entitlement checks for the ratchet
# ---------------------------------------------------------------------------


class SenderEntitlementConditionNode(DataLayerConditionWithPorts):
    """Base class for all sender-entitlement condition nodes.

    Subclasses of this class are the *only* permitted sender predicate nodes
    in the codebase; the architecture ratchet fails on any subclass defined
    outside this module (HP-01-007).
    This class adds no new behaviour — it is a marker for the ratchet.

    Each concrete subclass names the one kind it is a guard of in
    :attr:`guards_kind` (HP-01-009).
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = None
    """The kind this node is a guard of; ``None`` for a node that checks no
    one kind (the empty side and the any-of refusal the factory composes)."""


# ---------------------------------------------------------------------------
# Condition node: PARTICIPANT
# ---------------------------------------------------------------------------


class SenderIsParticipantNode(FindParticipantByActorIdNode):
    """Guard: sender must have a participant record on the case.

    Not a :class:`SenderEntitlementConditionNode`: it reuses the participant
    lookup of :class:`FindParticipantByActorIdNode`, so it names its kind
    itself.

    Returns ``SUCCESS`` when the case lists a participant record for the
    sender, whether or not that participant is active (CM-10-004): an inert
    invitee and a removed participant pass.  A participant whose closure the
    case records (RM ``CLOSED``) fails: it has left and may act on nothing
    further (CM-23-018; the same test as
    :func:`~vultron.core.participants.recipients.closure_recorded`, asked of
    the record the lookup found).
    Returns ``FAILURE`` otherwise, halting the parent ``Sequence`` with a
    REFUSED outcome.

    With no ``case_id`` there is no case to check the sender against, so it
    fails (DEMOMA-07-003 step 1); the status use case resolves the case from
    the stored status before it builds its tree.

    Merged from ``VerifySenderIsParticipantNode`` (ADR-0115, AC-2); it was
    ``SenderIsActiveParticipantNode`` until the ``PARTICIPANT`` kind split
    from ``ACTIVE_PARTICIPANT`` (#4437).

    Spec: HP-01-006, HP-01-009, DEMOMA-07-003.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.PARTICIPANT
    )

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(
            case_id=case_id or "",
            target_actor_id=sender_actor_id,
            participant_key="sender_participant",
            name=name or self.__class__.__name__,
        )
        self.sender_actor_id = sender_actor_id
        self._case_id_hint = case_id or None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f

        case_id = self._case_id_hint
        if case_id is None:
            self.feedback_message = (
                f"No case in this store to check sender"
                f" '{self.sender_actor_id}' against"
            )
            self.logger.warning(
                "%s: %s (HP-01-006, DEMOMA-07-003 step 1)",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE

        self.case_id = case_id
        result = super().update()
        if result == Status.FAILURE:
            self.feedback_message = (
                f"Sender '{self.sender_actor_id}' is not a participant of"
                f" case '{case_id}' — REFUSED (HP-01-006)"
            )
            self.logger.warning(
                "%s: %s (DEMOMA-07-003 step 1)",
                self.name,
                self.feedback_message,
            )
            return Status.FAILURE

        # The record the lookup above found, not a second lookup through the
        # index, so the two can never disagree about which record is closed.
        record = self.found_participant
        if record is not None and record.rm_closed:
            self.feedback_message = (
                f"Sender '{self.sender_actor_id}' has left case '{case_id}'"
                " (RM CLOSED) and may act on nothing further — REFUSED"
                " (HP-01-006, CM-23-018)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        self.logger.debug(
            "%s: sender '%s' is a participant in case '%s'"
            " (HP-01-006, DEMOMA-07-003 step 1)",
            self.name,
            self.sender_actor_id,
            case_id,
        )
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Condition node: ACTIVE_PARTICIPANT
# ---------------------------------------------------------------------------


class SenderIsActiveParticipantNode(SenderEntitlementConditionNode):
    """Guard: sender must be an active participant whose closure is not recorded.

    The guard of the ``ACTIVE_PARTICIPANT`` kind (CM-23-018).  Active means
    joined, not removed, and a signatory to the embargo in force (CM-10-004);
    the sender must also not be at RM ``CLOSED``, because a participant that
    has left may act on nothing further.  Both are asked through the one
    shared predicate,
    :func:`~vultron.core.participants.recipients.may_act_on_case`.  An inert
    invitee, a removed participant, a closed participant and a sender the
    case does not list all fail.  A closed participant's resync request is
    the ``LEDGER_PEER`` kind's instead
    (:class:`SenderIsActiveLedgerParticipantNode`).  With no ``case_id``, or
    a case this store does not hold, there is no standing to check, so the
    sender is refused (Regime 1, ADR-0087).

    Spec: CM-23-018, CM-10-004, HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.ACTIVE_PARTICIPANT
    )

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id or None

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        if self.case_id is None:
            # An activity that names no case is a routine refusal, as
            # SenderIsParticipantNode reports it, not a Regime 1 anomaly.
            self.feedback_message = (
                f"No case in this store to check sender"
                f" '{self.sender_actor_id}' against — REFUSED (HP-01-006)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: no case, so no standing to check
        if may_act_on_case(case, self.datalayer, self.sender_actor_id):
            return Status.SUCCESS
        self.feedback_message = (
            f"Sender '{self.sender_actor_id}' is not an active participant"
            f" of case '{self.case_id}', or has left it — REFUSED"
            " (HP-01-006, CM-10-004, CM-23-018)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Condition node: LEDGER_PEER (ledger activity on the blackboard)
# ---------------------------------------------------------------------------


class SenderIsActiveLedgerParticipantNode(SenderEntitlementConditionNode):
    """Guard: sender must be an active participant of the ledger entry's case.

    The guard of the ``LEDGER_PEER`` kind, the standing of a
    ``Reject(CaseLedgerEntry)`` resync request (SYNC-03-005).
    Reads ``activity`` from the blackboard and takes the case from the
    ``CaseLedgerEntry`` it carries.
    Returns ``SUCCESS`` only when the sender is an active participant of that
    case (:func:`~vultron.core.participants.recipients.is_case_content_recipient`,
    CM-10-004).
    An unknown case, a missing sender, an unlisted sender and an inert
    participant all return ``FAILURE``: there is nothing to replay to a sender
    the case cannot vouch for, so there is no bootstrap pass-through here.

    A participant at RM ``CLOSED`` passes: it may still ask for the entries
    that record its own closure, and the replay stops there
    (:func:`~vultron.core.participants.recipients.closed_participant_ledger_cutoff`,
    CM-23-004, CM-23-018).  This is the one participant guard that does not
    refuse a closed sender.

    Spec: SYNC-03-005, CM-10-004, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.LEDGER_PEER
    )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        entry = getattr(self.activity, "rejected_entry", None)
        if not isinstance(entry, CaseLedgerEntry):
            try:
                entry = _log_entry_from(self.activity, self.name)
            except VultronError as exc:
                self.logger.warning("%s: %s", self.name, exc)
                return Status.FAILURE
        sender_id = getattr(self.activity, "actor_id", None)
        if not sender_id:
            self.logger.warning("%s: activity has no actor_id", self.name)
            return Status.FAILURE

        # Regime 1: no case means no participant, so the sender is refused.
        case, failure = self._require_case(entry.case_id)
        if failure is not None:
            return failure
        if not is_case_content_recipient(case, self.datalayer, sender_id):
            self.feedback_message = (
                f"Sender '{sender_id}' is not an active participant in case"
                f" '{entry.case_id}' — REFUSED (SYNC-03-005, CM-10-004)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Condition node: CASE_MANAGER
# ---------------------------------------------------------------------------


class SenderIsCaseManagerNode(SenderEntitlementConditionNode):
    """Guard: sender must be the case's CASE_MANAGER.

    Resolves the case's authoritative CaseActor via
    :func:`~vultron.core.participants.authority.resolve_case_manager_id`
    and returns ``SUCCESS`` only when the announce ``actor_id`` equals that
    resolved CaseActor id.

    Passes through (``SUCCESS``) during the bootstrap window — when the case
    replica is not seeded yet, or no CASE_MANAGER is known — so downstream
    reject-on-missing-case / pre-genesis buffering (SYNC-15-001,
    SYNC-15-004) handles the entry rather than this gate dropping it.

    With ``anchored=True`` there is no pass-through: with no CASE_MANAGER on
    the replica, the sender must be the CASE_MANAGER recorded as the case's
    trust anchor when the receiver got the stub Invite (PCR-03-004, #4185),
    and a sender with no anchor to match is refused.  The full-case Invite
    uses it: its sender is the one actor the stub Invite introduced.

    With ``required=True`` there is no pass-through either: a case this store
    does not hold, or one that names no CASE_MANAGER, leaves nothing to
    establish the sender's standing against, so the sender is refused
    (Regime 1, ADR-0087).  A reply to an ownership-transfer Offer uses it at a
    replica, which takes the ownership change from the CASE_MANAGER alone
    (PCR-03-001).

    The check that the CASE_MANAGER's own ``Announce(CaseLedgerEntry)``, echoed
    back to it, came from itself is this check too: the identity compared is
    the one :func:`resolve_case_manager_id` resolves for the case (#4437).

    Reads ``activity`` from the blackboard via INPUT_PORTS; the sender is its
    ``actor_id`` unless ``sender_actor_id`` names it.

    Merged from ``VerifySenderIsCaseActorNode`` (ADR-0115, AC-2).

    Spec: CLP-01-003, SYNC-13-006, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_MANAGER
    )

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "activity": PortInformation(data_type=object, required=True),
    }

    def __init__(
        self,
        case_id: str | None = None,
        name: str | None = None,
        *,
        anchored: bool = False,
        required: bool = False,
        sender_actor_id: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case whose CASE_MANAGER the sender must be.
                Leave ``None`` for a ledger-entry activity, where the case is
                read from the entry the activity carries.
            name: Optional node name.
            anchored: Refuse, rather than pass through, when the replica names
                no CASE_MANAGER and the receiver recorded no matching trust
                anchor (PCR-03-004).
            required: Refuse, rather than pass through, when this store holds
                no case or the case names no CASE_MANAGER.
            sender_actor_id: The sender to check.  ``None`` reads it from the
                blackboard activity's ``actor_id``; the composed guard passes
                the sender every other kind checks (HP-01-008).
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._anchored = anchored
        self._required = required
        self._sender_actor_id = sender_actor_id

    def _recorded_anchor(self, case_id: str) -> str | None:
        """The CASE_MANAGER recorded when the receiver got the stub Invite."""
        assert self.datalayer is not None
        pending = self.datalayer.read(
            VultronPendingCaseInbox.build_id(case_id)
        )
        if isinstance(pending, VultronPendingCaseInbox):
            return pending.case_actor_id
        return None

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"activity": "/activity"}

    def initialise(self) -> None:
        super().initialise()
        self.activity = self.get_input("activity")

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        if self._case_id is not None:
            case_id = self._case_id
        else:
            try:
                entry = _log_entry_from(self.activity, self.name)
            except VultronError as exc:
                self.logger.error(  # noqa: TRY400
                    "%s: %s", self.name, exc
                )
                return Status.FAILURE
            case_id = entry.case_id
        sender_id = self._sender_actor_id or getattr(
            self.activity, "actor_id", None
        )

        if not sender_id:
            self.logger.warning("%s: announce has no actor_id", self.name)
            return Status.FAILURE

        # Lenient read: a missing case is the bootstrap window (Regime 3,
        # ADR-0087) — pass through rather than starving buffer/reject paths.
        case = self.datalayer.read_case(case_id)
        case_actor_id = (
            resolve_case_manager_id(case, self.datalayer)
            if case is not None
            else None
        )

        if case_actor_id is None and self._anchored:
            case_actor_id = self._recorded_anchor(case_id)
            if case_actor_id is None:
                self.feedback_message = (
                    f"No CASE_MANAGER is known for case '{case_id}' to"
                    f" match sender '{sender_id}' — REFUSED (HP-01-006)"
                )
                self.logger.warning("%s: %s", self.name, self.feedback_message)
                return Status.FAILURE

        if case_actor_id is None and self._required:
            held = (
                f"this store holds no case '{case_id}'"
                if case is None
                else f"case '{case_id}' names no CASE_MANAGER"
            )
            self.feedback_message = (
                f"Sender '{sender_id}' has no standing: {held} — REFUSED"
                " (PCR-03-001, HP-01-006)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE

        if case_actor_id is None:
            self.logger.debug(
                "%s: no CaseActor known for case '%s'"
                " — passing through for bootstrap handling",
                self.name,
                case_id,
            )
            return Status.SUCCESS

        if same_actor_id(sender_id, case_actor_id):
            self.logger.debug(
                "%s: sender '%s' matches CaseActor for case '%s'",
                self.name,
                sender_id,
                case_id,
            )
            return Status.SUCCESS

        self.feedback_message = (
            f"Sender '{sender_id}' is not the CASE_MANAGER for case"
            f" '{case_id}' — REFUSED (HP-01-006)"
        )
        self.logger.warning(
            "%s: rejected announce from '%s' for case '%s' (expected '%s')",
            self.name,
            sender_id,
            case_id,
            case_actor_id,
        )
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Condition nodes: NAMED_ACTOR (the addressee of a recorded request)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordedRequest:
    """The request a reply answers, as this store recorded it.

    Attributes:
        description: The request as a refusal names it, e.g.
            ``"Offer 'https://…'"``.
        position: The entitled sender as a refusal names it, e.g.
            ``"an addressee"`` or ``"the transferee"``.
        addressees: The actors entitled to answer it.
    """

    description: str
    position: str
    addressees: tuple[str, ...]


@dataclass(frozen=True)
class NothingToProtect:
    """This store made no such request, so there is no standing to check.

    Attributes:
        reason: Why, for the debug log.
    """

    reason: str


class NoStandingError(VultronError):
    """The sender's standing cannot be established; the message says why."""


class SenderIsRequestAddresseeNode(SenderEntitlementConditionNode):
    """Guard: sender must be an addressee of the request it answers.

    The one guard shape of the ``NAMED_ACTOR`` kind (HP-01-009, ADR-0129).
    Each subclass reads one kind of record this store holds for the request
    (:meth:`_recorded_request`); this base compares the sender with the
    record's addressees and words the refusal, so every addressee check
    compares and refuses the same way.  The record is this store's own,
    never the copy of the request the reply embeds, which the sender wrote.

    - A record that names the sender: ``SUCCESS``.
    - A record that does not, or names no one: ``FAILURE``, naming the
      request and its addressees.
    - No record the sender could stand on (:class:`NoStandingError`):
      ``FAILURE`` with that reason.
    - :class:`NothingToProtect`: ``SUCCESS``; a subclass returns it only
      where an unrecorded request has nothing to protect.

    Spec: HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.NAMED_ACTOR
    )

    _spec: ClassVar[str]
    """The requirement a refusal cites; each subclass names its own."""

    def __init__(
        self,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.sender_actor_id = sender_actor_id

    def _recorded_request(self) -> RecordedRequest | NothingToProtect:
        """The request as this store recorded it.

        Raises:
            NoStandingError: This store holds no record the sender's
                standing could rest on.
        """
        raise NotImplementedError

    def _confirm_standing(self, request: RecordedRequest) -> None:
        """Check any standing the sender needs beyond being the addressee.

        Runs once the sender is known to be an addressee of *request*.

        Raises:
            NoStandingError: The sender lacks that standing.
        """

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED ({self._spec}, HP-01-006)"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _confirm_addressee(self, request: RecordedRequest) -> None:
        """The one comparison every addressee check makes.

        Raises:
            NoStandingError: The sender is not among *request*'s addressees.
        """
        sender = self.sender_actor_id
        if is_addressed_to(sender, request.addressees):
            return
        shown = ", ".join(f"'{a}'" for a in request.addressees) or "nobody"
        raise NoStandingError(
            f"Sender '{sender}' is not {request.position} of"
            f" {request.description} ({shown})"
        )

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        try:
            request = self._recorded_request()
            if isinstance(request, NothingToProtect):
                self.logger.debug(
                    "%s: %s — nothing to protect", self.name, request.reason
                )
                return Status.SUCCESS
            self._confirm_addressee(request)
            self._confirm_standing(request)
        except NoStandingError as exc:
            return self._refuse(str(exc))
        return Status.SUCCESS


class SenderIsProposalAddresseeNode(SenderIsRequestAddresseeNode):
    """Guard: sender must be the actor the CaseProposal was addressed to.

    The vendor records the addressee on its ``VultronReportCaseLink``
    (``case_creator_id``) when it proposes the case.

    - No link for the report (a relay, or a proposal this actor never made):
      ``SUCCESS``, because there is nothing to protect and the effect node
      reports the no-op as ``SKIPPED``.
    - A link with no recorded addressee: ``FAILURE`` (nobody is entitled).
    - Any other sender: ``FAILURE``, so the tree ends ``REFUSED`` with the
      link unchanged.

    Spec: CP-06-005, HP-01-006.
    """

    _spec = "CP-06-005"

    def __init__(
        self,
        report_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self.report_id = report_id

    def _recorded_request(self) -> RecordedRequest | NothingToProtect:
        assert self.datalayer is not None
        link = self.datalayer.read(
            VultronReportCaseLink.build_id(self.report_id)
        )
        if not isinstance(link, VultronReportCaseLink):
            return NothingToProtect(
                f"no report case link for '{self.report_id}'"
            )
        addressee = link.case_creator_id
        return RecordedRequest(
            description=f"the CaseProposal for report '{self.report_id}'",
            position="the addressee",
            addressees=(addressee,) if addressee is not None else (),
        )


class SenderIsOfferAddresseeNode(SenderIsRequestAddresseeNode):
    """Guard: sender must be an actor the ``Offer(VulnerabilityReport)`` was
    addressed to.

    ``RK`` (``Read(Offer(VulnerabilityReport))``) is sent by the actor that
    received the report submission, to the reporter (RMB-08-003).  The
    reporter holds the Offer it sent, so this guard reads this store's
    :class:`~vultron.core.models.offer_record.VultronOfferRecord` for the
    acknowledged Offer and admits only one of its ``offer_to`` recipients.

    A store that holds no record of the Offer has nothing to establish the
    sender's standing against, so the sender is refused.

    Spec: RMB-08-004, HP-01-006.
    """

    _spec = "RMB-08-004"

    def __init__(
        self,
        offer_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            offer_id: The Offer the acknowledgement names (``None`` when it
                names none, which refuses).
            sender_actor_id: The acknowledgement's sender.
            name: Optional node name.
        """
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self.offer_id = offer_id

    def _recorded_request(self) -> RecordedRequest:
        assert self.datalayer is not None
        if self.offer_id is None:
            raise NoStandingError(
                f"Acknowledgement from '{self.sender_actor_id}' names no Offer"
            )
        record = self.datalayer.read(
            VultronOfferRecord.build_id(self.offer_id)
        )
        if not isinstance(record, VultronOfferRecord):
            raise NoStandingError(
                f"No record of Offer '{self.offer_id}' in this store, so"
                f" sender '{self.sender_actor_id}' cannot be shown to be its"
                " addressee"
            )
        return RecordedRequest(
            description=f"Offer '{self.offer_id}'",
            position="an addressee",
            addressees=tuple(record.offer_to),
        )


# ---------------------------------------------------------------------------
# Condition node: INVITEE (the recorded Invite being answered)
# ---------------------------------------------------------------------------


class SenderIsInviteeNode(SenderEntitlementConditionNode):
    """Guard: sender must be the sole ``to`` recipient of the recorded Invite.

    The answer to an Invite is the invitee's to give, and the invitee is the
    Invite's sole ``to`` recipient (EP-09-010).
    The Invite is read from this store, never from the copy the reply embeds,
    which the sender wrote.
    An Invite this store never recorded, or one that names no recipient or
    several, names no invitee, so the sender is refused.

    When ``case_id`` is given the Invite is a case-join Invite, and the
    record must also be one this store's owner (the CASE_MANAGER) issued
    (CM-11-017: "an Invite it sent and recorded") and be for that case: a
    stub Invite names its case through its stub target, and an invitee of one
    case cannot answer for another.

    When ``closure_case_id`` is given, an invitee whose closure that case
    records (RM ``CLOSED``) is refused too: it has left the case and may
    answer nothing further (CM-23-018).  A repeat of a ``Reject`` that closed
    it is ``SKIPPED`` by the handler's pre-flight before this guard runs.

    Spec: EP-09-010, CM-11-017, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.INVITEE
    )

    def __init__(
        self,
        invite_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
        *,
        case_id: str | None = None,
        closure_case_id: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._invite_id = invite_id
        self._sender_actor_id = sender_actor_id
        self._case_id = case_id
        self._closure_case_id = closure_case_id

    @staticmethod
    def _named_case(invite: object) -> str | None:
        """The case a recorded Invite is for: its stub target's case, else its target."""
        target = getattr(invite, "target", None)
        stub_case = getattr(target, "case_id", None)
        return stub_case if isinstance(stub_case, str) else _as_id(target)

    def _admit_unless_closed(self) -> Status:
        """SUCCESS, unless the case records the invitee's closure (CM-23-018)."""
        if self._closure_case_id is None:
            return Status.SUCCESS
        assert self.datalayer is not None
        case = self.datalayer.read(self._closure_case_id)
        if not isinstance(case, VulnerabilityCase) or not closure_recorded(
            case, self.datalayer, self._sender_actor_id
        ):
            return Status.SUCCESS
        self.feedback_message = (
            f"Invitee '{self._sender_actor_id}' has left case"
            f" '{self._closure_case_id}' (RM CLOSED) and may answer nothing"
            " further — REFUSED (CM-23-018, HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def _refuse_case_join(self, why: str) -> Status:
        self.feedback_message = (
            f"Invite '{self._invite_id}' {why} — REFUSED (CM-11-017,"
            " HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        sender = self._sender_actor_id
        invite = (
            self.datalayer.read(self._invite_id) if self._invite_id else None
        )
        recipients = distinct_recipients(
            _as_id(r) for r in (getattr(invite, "to", None) or [])
        )
        if len(recipients) == 1 and same_actor_id(sender, recipients[0]):
            if self._case_id is None:
                return self._admit_unless_closed()
            issuer = _as_id(getattr(invite, "actor", None))
            if issuer is None or not same_actor_id(
                issuer, self.actor_id or ""
            ):
                return self._refuse_case_join(
                    f"was issued by '{issuer}', not by this CASE_MANAGER"
                )
            named_case = self._named_case(invite)
            if named_case != self._case_id:
                return self._refuse_case_join(
                    f"is for case '{named_case}', not '{self._case_id}'"
                )
            return self._admit_unless_closed()

        if invite is None:
            why = f"Invite '{self._invite_id}' was never recorded here"
        elif len(recipients) != 1:
            why = (
                f"Invite '{self._invite_id}' names {len(recipients)}"
                " recipients, so it has no invitee"
            )
        else:
            why = (
                f"Invite '{self._invite_id}' was addressed to"
                f" '{recipients[0]}'"
            )
        self.feedback_message = (
            f"Sender '{sender}' is not the invitee: {why}"
            " — REFUSED (EP-09-010, HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Condition nodes: the parties to a recorded ownership-transfer Offer
# ---------------------------------------------------------------------------


class SenderIsOwnershipOfferPartyNode(SenderIsRequestAddresseeNode):
    """Guard: sender is the party to a recorded ownership-transfer Offer that
    its reply needs.

    Shared by the transferee's answer (:class:`SenderIsOwnershipTransfereeNode`)
    and the offerer's withdrawal (:class:`SenderIsOwnershipOffererNode`).  The
    receive-tree factory composes it on the CASE_MANAGER's side of the
    declared rule; a replica takes the ownership change from the CASE_MANAGER
    alone, which the rule's participant side checks (PCR-03-001).

    It checks standing only: the sender is the party the subclass names to an
    ownership-transfer Offer the CASE_MANAGER recorded for the case.  The
    Offer is read from this store's ledger, never from the copy the reply
    embeds, which the sender wrote.  Whether the Offer is still open, and
    whether the reply is a redelivery of the one that closed it, is the
    precondition guard that runs right after the sender check
    (:class:`~vultron.core.behaviors.case.nodes.ownership_offer_guard.OwnershipOfferOpenNode`),
    so a sender with no standing is refused before any offer-state check.

    A case this store does not hold, or one that names no CASE_MANAGER,
    leaves nothing to establish the sender's standing against, so the sender
    is refused.

    Spec: CM-21-011, CM-21-013, CM-21-015, PCR-03-001, HP-01-006.
    """

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the reply names.
            offer_id: The Offer the reply names (``None`` when it names
                none, which refuses).
            sender_actor_id: The reply's sender.
            name: Optional node name.
        """
        super().__init__(sender_actor_id=sender_actor_id, name=name)
        self._case_id = case_id
        self._offer_id = offer_id
        self._case: VulnerabilityCase | None = None
        """The case :meth:`_recorded_offer` last read."""
        self._offer: RecordedOwnershipOffer | None = None
        """The Offer :meth:`_recorded_offer` last read."""

    def _recorded_offer(
        self,
    ) -> tuple[str, RecordedOwnershipOffer]:
        """The case's CASE_MANAGER and the Offer the reply names.

        Raises:
            NoStandingError: This store holds no such case, the case names no
                CASE_MANAGER, or the CASE_MANAGER recorded no such Offer.
        """
        assert self.datalayer is not None
        sender = self.sender_actor_id
        case = self.datalayer.read_case(self._case_id)
        if case is None:
            # The sender's case, not ours: nothing to establish its standing
            # against, which is a refusal and not a local anomaly.
            raise NoStandingError(
                f"Sender '{sender}' has no standing: this store holds no"
                f" case '{self._case_id}'"
            )
        manager_id = resolve_case_manager_id(case, self.datalayer)
        if manager_id is None:
            raise NoStandingError(
                f"Sender '{sender}' has no standing: case '{self._case_id}'"
                " names no CASE_MANAGER"
            )
        if self._offer_id is None:
            raise NoStandingError(
                f"Sender '{sender}' names no ownership-transfer Offer"
            )
        try:
            offer = recorded_ownership_offer(
                self.datalayer, self._case_id, self._offer_id, manager_id
            )
        except VultronNotFoundError as exc:
            raise NoStandingError(
                f"Sender '{sender}' names Offer '{self._offer_id}', which"
                f" this CASE_MANAGER never recorded for case"
                f" '{self._case_id}' ({exc})"
            ) from exc
        self._case = case
        self._offer = offer
        return manager_id, offer


class SenderIsOwnershipTransfereeNode(SenderIsOwnershipOfferPartyNode):
    """Guard: sender is the transferee of the ownership-transfer Offer it
    answers.

    The transferee is the addressee of the request, so the kind is
    ``NAMED_ACTOR`` (ADR-0129); see :class:`SenderIsOwnershipOfferPartyNode`.

    A transferee whose closure the case records is refused: it has left the
    case (CM-23-018).

    Spec: CM-21-011, CM-21-013, CM-23-018, HP-01-006.
    """

    _spec = "CM-21-011"

    def _recorded_request(self) -> RecordedRequest:
        _manager_id, offer = self._recorded_offer()
        return RecordedRequest(
            description=f"ownership-transfer Offer '{offer.offer_id}'",
            position="the transferee",
            addressees=(offer.transferee_id,),
        )

    def _confirm_standing(self, request: RecordedRequest) -> None:
        """Refuse a transferee whose closure the case records (CM-23-018).

        Raises:
            NoStandingError: The transferee has left the case (RM ``CLOSED``).
        """
        assert self.datalayer is not None and self._case is not None
        if closure_recorded(self._case, self.datalayer, self.sender_actor_id):
            raise NoStandingError(
                f"Transferee '{self.sender_actor_id}' has left case"
                f" '{self._case_id}' (RM CLOSED) and may answer nothing"
                " further (CM-23-018)"
            )


class SenderIsOwnershipOffererNode(SenderIsOwnershipOfferPartyNode):
    """Guard: sender is the Case Owner that made the ownership-transfer Offer
    it withdraws.

    The offerer is the participant the recorded Offer speaks for — its
    ``attributedTo`` only when the CASE_MANAGER sent it on that participant's
    behalf, else its ``actor`` (CM-24-002).  The kind is ``CASE_OWNER``,
    checked against the recorded Offer; see
    :class:`SenderIsOwnershipOfferPartyNode`.

    The offerer must also hold ``CVDRole.CASE_OWNER`` now (CM-21-015): that is
    standing too, so it is checked here, before the Offer's state.  An
    offerer whose Offer an Accept closed no longer holds it, and is refused
    for that.

    A redelivery of the withdrawal the CASE_MANAGER already ledgered as
    closing the Offer is a duplicate, not a new withdrawal: its standing was
    established when it was admitted, and ownership may since have moved on
    through a later Offer.  The role is not re-checked for it, so the
    open-Offer guard reports it ``SKIPPED`` (HP-01-003).

    Spec: CM-21-015, PCR-03-001, HP-01-003, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )
    _spec = "CM-21-015"

    def __init__(
        self,
        case_id: str,
        offer_id: str | None,
        sender_actor_id: str,
        reply_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the Undo names.
            offer_id: The Offer the Undo names (``None`` refuses).
            sender_actor_id: The Undo's sender.
            reply_id: The Undo's own id, so a redelivery of the withdrawal
                that closed the Offer is recognised.
            name: Optional node name.
        """
        super().__init__(
            case_id=case_id,
            offer_id=offer_id,
            sender_actor_id=sender_actor_id,
            name=name,
        )
        self._reply_id = reply_id

    def _recorded_request(self) -> RecordedRequest:
        manager_id, offer = self._recorded_offer()
        offerer_id = offer.offerer_id(manager_id)
        return RecordedRequest(
            description=f"ownership-transfer Offer '{offer.offer_id}'",
            position="the offerer",
            addressees=(offerer_id,) if offerer_id is not None else (),
        )

    def _confirm_standing(self, request: RecordedRequest) -> None:
        assert self.datalayer is not None and self._case is not None
        assert self._offer is not None
        if self._offer.answer_id == self._reply_id:
            return  # the admitted withdrawal, redelivered (HP-01-003)
        sender = self.sender_actor_id
        if not _holds_case_owner_role(self.datalayer, self._case, sender):
            raise NoStandingError(
                f"Sender '{sender}' made {request.description} but does not"
                f" hold CASE_OWNER on case '{self._case_id}'"
            )


class SenderIsOfferingCaseOwnerNode(SenderEntitlementConditionNode):
    """Guard: the sender of a new ownership-transfer Offer is the Case Owner.

    At the CASE_MANAGER only the actor holding ``CVDRole.CASE_OWNER`` on the
    case may offer it (CM-21-019); the kind is ``CASE_OWNER``.  It runs on
    the CASE_MANAGER's side of the rule, which holds the case (Regime 1).

    A redelivery of an Offer the CASE_MANAGER already ledgered from this
    sender is a duplicate, not a new Offer: its standing was established when
    it was admitted, and the sender may since have handed ownership on, so
    the role is not re-checked and the open-Offer guard reports it
    ``SKIPPED`` (HP-01-003).  The same Offer id from any other sender is
    judged as a new Offer.

    Spec: CM-21-019, HP-01-003, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        case_id: str,
        offer_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            case_id: The case the Offer names.
            offer_id: The Offer's own id, so a redelivery is recognised.
            sender_actor_id: The Offer's sender.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._case_id = case_id
        self._offer_id = offer_id
        self._sender_actor_id = sender_actor_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        sender = self._sender_actor_id
        case, failure = self._require_case(self._case_id)
        if failure is not None:
            return failure  # Regime 1: the CASE_MANAGER holds its case
        if _holds_case_owner_role(self.datalayer, case, sender):
            return Status.SUCCESS
        recorded_sender = recorded_ownership_offer_sender(
            self.datalayer, self._case_id, self._offer_id
        )
        if recorded_sender is not None and same_actor_id(
            recorded_sender, sender
        ):
            self.logger.debug(
                "%s: Offer '%s' was recorded from '%s' — redelivery"
                " (HP-01-003)",
                self.name,
                self._offer_id,
                sender,
            )
            return Status.SUCCESS
        return self._refuse(
            f"Sender '{sender}' is not the Case Owner of case"
            f" '{self._case_id}', so it may not offer its ownership"
        )

    def _refuse(self, reason: str) -> Status:
        self.feedback_message = f"{reason} — REFUSED (CM-21-019, HP-01-006)"
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Condition node: a side the declared rule leaves empty
# ---------------------------------------------------------------------------


class NoSenderAdmittedNode(SenderEntitlementConditionNode):
    """Guard for a side a :class:`SenderRule` leaves empty: it admits no one.

    The factory composes it when the receiver is on a side the use case's
    rule names no kind for, such as a participant receiving an activity only
    the CASE_MANAGER may be sent (HP-01-008).  It always fails, naming the
    side, so the tree ends ``REFUSED`` with nothing written.

    Spec: HP-01-006, HP-01-008.
    """

    def __init__(self, side: str, name: str | None = None) -> None:
        """Create the guard.

        Args:
            side: Plain-language name of the empty side, e.g.
                ``"a participant other than the CASE_MANAGER"``.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._side = side

    def update(self) -> Status:
        self.feedback_message = (
            f"No sender is entitled to send this activity to {self._side}"
            " — REFUSED (HP-01-006, HP-01-008)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SenderHoldsNoneOfNode(SenderEntitlementConditionNode):
    """The last arm of an any-of side: the sender held none of its kinds.

    The factory appends it to the selector of an any-of side (HP-01-008), so
    a refused sender's reason names every standing the side accepts rather
    than only the last kind tried (HP-01-006, BT-13-001).  It always fails.

    Spec: HP-01-006, HP-01-008.
    """

    def __init__(
        self,
        kinds: frozenset[SenderEntitlementKind],
        name: str | None = None,
    ) -> None:
        """Create the guard.

        Args:
            kinds: The kinds the side accepts, any one sufficing.
            name: Optional node name.
        """
        super().__init__(name=name or self.__class__.__name__)
        self._kinds = in_declaration_order(kinds)

    def update(self) -> Status:
        names = ", ".join(kind.name for kind in self._kinds)
        self.feedback_message = (
            f"Sender holds none of the standings this activity accepts"
            f" ({names}) — REFUSED (HP-01-006, HP-01-008)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


# ---------------------------------------------------------------------------
# Condition node: CASE_OWNER
# ---------------------------------------------------------------------------


class SenderIsCaseOwnerNode(SenderEntitlementConditionNode):
    """Guard: sender must hold ``CVDRole.CASE_OWNER``.

    Returns ``SUCCESS`` when the sender's participant record carries
    ``CVDRole.CASE_OWNER``.
    Returns ``FAILURE`` for any actor that is not a known CASE_OWNER,
    including unknown actors or those holding other roles.

    Used as the hard-bypass child of ``StatusAdoptionGate`` (RSH-01-002):
    a CASE_OWNER's status reports are authoritative ("gospel") and do not
    require approval by the ``CaseOwnerApprovesStatusUpdate`` call-out.

    Reads ``case_id`` from constructor or from the blackboard input port.

    Merged from ``CheckIsCaseOwnerNode`` (ADR-0115, AC-2).

    Spec: RSH-01-002, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.CASE_OWNER
    )

    def __init__(
        self,
        sender_actor_id: str,
        case_id: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self._sender_actor_id = sender_actor_id
        self._case_id = case_id

    INPUT_PORTS: dict[str, PortInformation] = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=False),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "/case_id"}

    def initialise(self) -> None:
        super().initialise()
        self._case_id_bb: str | None = None
        try:
            self._case_id_bb = self.get_input("case_id")
        except (NoDataAvailable, NotImplementedError):
            pass

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case_id = self._case_id or self._case_id_bb

        case, failure = self._require_case(case_id)
        if failure is not None:
            return failure  # Regime 1: CASE_OWNER role gate needs the case

        if _holds_case_owner_role(self.datalayer, case, self._sender_actor_id):
            self.logger.debug(
                "%s: sender '%s' IS CASE_OWNER for case '%s'",
                self.name,
                self._sender_actor_id,
                case_id,
            )
            return Status.SUCCESS

        self.logger.debug(
            "%s: sender '%s' is NOT CASE_OWNER for case '%s'",
            self.name,
            self._sender_actor_id,
            case_id,
        )
        return self._not_case_owner(case_id)

    def _not_case_owner(self, case_id: str | None) -> Status:
        """Record the missing entitlement by name and fail (HP-01-006)."""
        self.feedback_message = (
            f"Sender '{self._sender_actor_id}' is not the Case Owner of case"
            f" '{case_id}' — REFUSED (HP-01-006)"
        )
        return Status.FAILURE


class SenderIsNoteAuthorNode(SenderEntitlementConditionNode):
    """Guard: sender must be the note's author and an active case participant.

    Reads the note from the executing actor's store and compares its
    ``attributed_to`` with the sender.
    Returns ``FAILURE`` for an unknown note, a note with no recorded author, a
    different sender, and an author who is no longer an active participant of
    the case: one that is not an active participant (CM-10-004) or whose
    closure the case records (CM-23-018), asked through
    :func:`~vultron.core.participants.recipients.may_act_on_case`.

    Spec: CM-30-001, CM-10-004, CM-23-018, HP-01-006.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.AUTHOR
    )

    def __init__(
        self,
        note_id: str,
        sender_actor_id: str,
        case_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.note_id = note_id
        self.sender_actor_id = sender_actor_id
        self.case_id = case_id

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None

        case, failure = self._require_case(self.case_id)
        if failure is not None:
            return failure  # Regime 1: the participant check needs the case

        note = self.datalayer.read(self.note_id)
        author = _as_id(getattr(note, "attributed_to", None))
        if (
            author is not None
            and same_actor_id(self.sender_actor_id, author)
            and may_act_on_case(case, self.datalayer, self.sender_actor_id)
        ):
            return Status.SUCCESS

        self.feedback_message = (
            f"Sender '{self.sender_actor_id}' is not the author of note"
            f" '{self.note_id}' (author: '{author}') or not an active"
            f" participant of case '{self.case_id}' that has not left it"
            " — REFUSED (CM-30-001, CM-23-018, HP-01-006)"
        )
        self.logger.warning("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


class SenderIsProposalAuthorNode(SenderEntitlementConditionNode):
    """Guard: the sender of a ``Create(CaseProposal)`` is the proposal's author.

    The proposal id is chosen by the sender, and every proposal-keyed record
    is keyed on it alone.  The CASE_MANAGER records the proposer when it
    admits the proposal (``CaseProposalAdmissionRecord``) or declines it
    (``CaseProposalDeclineRecord``), and it stores the proposal itself, whose
    ``attributed_to`` is the proposer, when it sends the ``Accept`` or
    ``Reject``.  A store written before the admission record existed holds
    only that stored proposal, so it is read too.  A delivery of that
    proposal id is a redelivery only from that proposer (CP-05-006,
    CP-05-010).

    - Nothing recorded for the proposal id: ``SUCCESS``.  It is a new
      proposal, and the parse edge has already refused a proposal whose
      ``attributed_to`` is not its sender (CP-01-010).
    - Every recorded proposer is the sender: ``SUCCESS``, a redelivery.
    - Any recorded proposer is another actor: ``FAILURE``, so the tree ends
      ``REFUSED`` before any arm writes a record or sends an answer.

    A store error is not caught: it fails the tree, which refuses rather than
    admits (``notes/bt-pitfalls.md`` § "A Refusal Arm in a Selector Fails
    Toward 'Admit'").

    Spec: CP-05-006, CP-05-010, HP-01-006, HP-01-009.
    """

    guards_kind: ClassVar[SenderEntitlementKind | None] = (
        SenderEntitlementKind.AUTHOR
    )

    _RECORDS: ClassVar[
        tuple[
            type[CaseProposalAdmissionRecord]
            | type[CaseProposalDeclineRecord],
            ...,
        ]
    ] = (CaseProposalAdmissionRecord, CaseProposalDeclineRecord)

    def __init__(
        self,
        proposal_id: str,
        sender_actor_id: str,
        name: str | None = None,
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.proposal_id = proposal_id
        self.sender_actor_id = sender_actor_id

    def _recorded_proposers(self) -> list[str]:
        """Every proposer this store recorded for the proposal id."""
        assert self.datalayer is not None
        proposers: list[str] = []
        for record_type in self._RECORDS:
            record = self.datalayer.read(
                record_type.build_id(self.proposal_id)
            )
            if isinstance(record, record_type):
                proposers.append(record.proposer_uri)
        stored = self.datalayer.read(self.proposal_id)
        author = _as_id(getattr(stored, "attributed_to", None))
        if author:
            proposers.append(author)
        return proposers

    def update(self) -> Status:
        if (f := self._require_datalayer()) is not None:
            return f
        for proposer in self._recorded_proposers():
            if same_actor_id(proposer, self.sender_actor_id):
                continue
            self.feedback_message = (
                f"Sender '{self.sender_actor_id}' is not the author of"
                f" CaseProposal '{self.proposal_id}', which this store"
                f" recorded for '{proposer}' — REFUSED"
                " (CP-05-010, HP-01-006)"
            )
            self.logger.warning("%s: %s", self.name, self.feedback_message)
            return Status.FAILURE
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Condition node: the sender's closure is not recorded (CM-23-018)
# ---------------------------------------------------------------------------


class SenderClosureNotRecordedNode(DataLayerConditionWithPorts):
    """Guard: the case does not record the sender's closure (CM-23-018).

    A participant whose closure the case records (RM ``CLOSED``) may act on
    nothing further, except that a repeat of an act that would close it
    again changes nothing and is reported ``SKIPPED``, whatever its activity
    id (ID-05-003).  This node is the check the closed-sender pre-flight runs
    before a handler's received tree
    (:func:`vultron.core.use_cases.received._sender_preflight.closed_sender_preflight`),
    built by :func:`vultron.core.behaviors.sender_guard.closed_sender_guard`.

    SUCCESS when the sender is not at RM ``CLOSED`` here, or when this store
    holds no such case: the received tree decides what the act means.

    FAILURE with :attr:`sender_closed` set when the case records the
    sender's closure (:func:`~vultron.core.participants.recipients.closure_recorded`).
    The handler reports an act that would close the sender again as
    ``SKIPPED``, and any other act as ``REFUSED``.

    Keyed on the sender's recorded RM state, never on the activity id, which
    a repeat sent under a new id does not share.  Read-only.

    Spec: CM-23-018, ID-05-003, HP-01-007.
    """

    def __init__(
        self, case_id: str, sender_actor_id: str, name: str | None = None
    ) -> None:
        super().__init__(name=name or self.__class__.__name__)
        self.case_id = case_id
        self.sender_actor_id = sender_actor_id
        self.sender_closed = False
        """``True`` when the last run found the sender's closure recorded."""

    def update(self) -> Status:
        self.sender_closed = False
        if (f := self._require_datalayer()) is not None:
            return f
        assert self.datalayer is not None
        case = self.datalayer.read(self.case_id)
        if not isinstance(case, VulnerabilityCase) or not closure_recorded(
            case, self.datalayer, self.sender_actor_id
        ):
            return Status.SUCCESS
        self.sender_closed = True
        self.feedback_message = (
            f"'{self.sender_actor_id}' is already closed on case"
            f" '{self.case_id}' (CM-23-018)"
        )
        self.logger.info("%s: %s", self.name, self.feedback_message)
        return Status.FAILURE


__all__ = [
    # Declaration types
    "AddresseeSide",
    "SenderEntitlementKind",
    "SenderExemption",
    "SenderEntitlement",
    "SenderRule",
    "any_of",
    "in_declaration_order",
    "exempt",
    # Helper predicate
    "is_case_owner",
    # Base / marker class
    "SenderEntitlementConditionNode",
    # Condition nodes
    "SenderIsParticipantNode",
    "SenderIsActiveParticipantNode",
    "SenderIsActiveLedgerParticipantNode",
    "SenderIsCaseManagerNode",
    "RecordedRequest",
    "NothingToProtect",
    "NoStandingError",
    "SenderIsRequestAddresseeNode",
    "SenderIsProposalAddresseeNode",
    "SenderIsOwnershipOfferPartyNode",
    "SenderIsOwnershipTransfereeNode",
    "SenderIsOfferingCaseOwnerNode",
    "SenderIsOwnershipOffererNode",
    "SenderIsInviteeNode",
    "SenderIsOfferAddresseeNode",
    "SenderIsCaseOwnerNode",
    "SenderIsNoteAuthorNode",
    "SenderClosureNotRecordedNode",
    "NoSenderAdmittedNode",
    "SenderHoldsNoneOfNode",
]
