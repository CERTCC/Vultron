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

"""Sender-entitlement declaration types (HP-01-008, ADR-0129).

The kinds a :class:`SenderRule` names, the addressee sides it states them
at, and the exemptions a received use case may declare instead.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Self

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

    Each kind corresponds to one condition node in this package, except
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

    CASE_MANAGER = ("the CASE_MANAGER", "Case Manager")
    """Sender must be the case's ``CVDRole.CASE_MANAGER``."""

    CASE_OWNER = ("the Case Owner", "Case Owner")
    """Sender must hold ``CVDRole.CASE_OWNER``."""

    ACTIVE_PARTICIPANT = ("an active participant", "Active Participant")
    """Sender must be an active participant whose closure is not recorded.

    Active per CM-10-004: joined and, while an embargo is in force, a
    signatory to it; a removed participant is not active.  And not at RM
    ``CLOSED``: a participant that has left the case may act on nothing
    further (CM-23-018).  Every guard for this kind asks one predicate
    (CM-23-054),
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
    (CM-23-031, CM-23-048).  No other use case declares it (CM-23-020).
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
    CP-01-010).  A participant record's author is the participant it names,
    so a received ``Add(ParticipantStatus)`` onto it comes from that
    participant (RSH-08-007).
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
    (HP-01-024).  An occasion declares its addressee as one of them, which
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

    CASE_MANAGER = ("the CASE_MANAGER", "Case Manager")
    """Sent to the case's CASE_MANAGER (``SenderRule.at_case_manager``)."""

    PARTICIPANT = ("a participant", "Participant")
    """Sent to a participant other than the CASE_MANAGER
    (``SenderRule.at_participant``)."""

    OUTSIDE_CASE = ("an actor outside any case", "Actor")
    """Sent before any case exists, to an actor outside any case
    (``SenderRule.outside_case``)."""


@dataclass(frozen=True)
class SenderExemption:
    """Declaration that a received use case runs no sender check.

    Two forms (HP-01-007):

    - Not yet checked: ``tracking_issue`` names the open issue that will add
      the real check (:func:`exempt`).
    - No check applies: ``tracking_issue`` is ``None`` and ``reason`` says
      why no sender's standing gates anything the handler does
      (:func:`no_sender_check`).

    The ratchet accepts either as a valid declaration.

    Attributes:
        tracking_issue: GitHub issue reference, e.g. ``"#4072"``; ``None``
            when no sender check applies.
        reason: Human-readable reason the check is deferred, or why none
            applies.

    Raises:
        ValueError: An exemption that names no issue gives no reason.
    """

    tracking_issue: str | None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.tracking_issue is None and not self.reason.strip():
            raise ValueError(
                "An exemption that names no tracking issue must say why no"
                " sender check applies (HP-01-007)"
            )

    @property
    def permanent(self) -> bool:
        """No sender check applies, so no issue owns one."""
        return self.tracking_issue is None


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


def no_sender_check(reason: str) -> SenderExemption:
    """Declare a received use case to which no sender check applies.

    For a use case whose handler does nothing a sender's standing could
    gate: it writes nothing but the intake archive every received tree keeps
    (CLP-10-018), commits nothing and sends nothing.  It names no tracking
    issue, because no check is owed (HP-01-007).

    Usage on a received use-case class::

        class MyReceivedUseCase:
            sender_entitlement: ClassVar[SenderEntitlement] = no_sender_check(
                "the activity has no recognized meaning, so nothing is applied"
            )

    Args:
        reason: Why no sender check applies; required.

    Returns:
        A permanent :class:`SenderExemption`.

    Raises:
        ValueError: *reason* is empty.
    """
    return SenderExemption(tracking_issue=None, reason=reason)
