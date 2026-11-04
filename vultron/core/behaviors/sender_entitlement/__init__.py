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

"""One sender-entitlement package: predicates, condition nodes, and declarations.

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
  (CM-23-018).  Every guard for it asks one predicate (CM-23-054),
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
nodes named outside this package and the composer, unless an allow-list names
the site: a guard not yet migrated names the open issue that migrates it, and
a standing read that picks an effect after admission says why it admits no
one (HP-01-007, #4437).

Exemption
---------
``exempt(tracking_issue, reason)`` declares a received use case as not yet
checked, naming the open tracking issue that owns the fix.
``no_sender_check(reason)`` declares a use case to which no sender check
applies: it names no issue, because nothing is owed, and its reason says why
(an activity with no recognized meaning, or one whose handler writes, commits
and sends nothing a sender's standing could gate).
The ratchet accepts either as a valid declaration; it only fails on a
missing attribute.

Refusal reasons and log levels
------------------------------
A check that does not admit the sender calls
``SenderEntitlementConditionNode._refuse_by_placement(reason)``, which records
*reason* as ``feedback_message`` for ``BTBridge.get_failure_reason``
(BT-13-001) and logs it at WARNING only when ``failure_is_the_refusal(node)``
says this node's FAILURE is the guard's whole answer.  Inside an any-of side a
later arm may still admit the sender, so that line is DEBUG (SL-03-002) and drops
the ``REFUSED`` wording (SL-03-003): nothing was refused (#5460).

``SenderIsCaseManagerNode`` is so far the only check that takes this rule.  The
others log WARNING from their own ``update()``, and three of them
(``SenderIsRequestAddresseeNode``, ``SenderIsOfferingCaseOwnerNode``,
``SenderIsParticipantRecordSubjectNode``) have a private ``_refuse`` that
appends the ``REFUSED`` group instead of receiving it; #5786 brings the family
onto one rule.

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
- ``SenderIsExpectedCaseCreatorNode`` — guards that the sender of a bootstrap
  ``Create(VulnerabilityCase)`` is the actor a report case link this store
  wrote expects the case from, or the creator of a bootstrap it already
  accepted (``NAMED_ACTOR`` kind; CBT-01-005, CBT-01-011)
- ``SenderIsOfferAddresseeNode`` — guards that the sender is an actor the
  ``Offer(VulnerabilityReport)`` was addressed to, as recorded on this store's
  offer record (``NAMED_ACTOR`` kind; RMB-08-004)
- ``SenderIsInviteeNode`` — guards that the sender is the sole ``to``
  recipient of the recorded Invite it answers (EP-09-010)
- ``SenderIsOwnershipTransfereeNode`` — guards that the sender of an answer
  to an ownership-transfer Offer is the transferee of the Offer the
  CASE_MANAGER recorded (``NAMED_ACTOR`` kind; CM-21-011, CM-21-013)
- ``SenderIsRoleOfferTargetNode`` — guards that the sender of an answer to
  a role Offer is the target of the Offer the CASE_MANAGER recorded
  (``NAMED_ACTOR`` kind; CM-33-005)
- ``SenderIsOwnershipOffererNode`` — guards that the sender of a withdrawal
  is the Case Owner that made the Offer the CASE_MANAGER recorded
  (``CASE_OWNER`` kind; CM-21-015).  Whether that Offer is still open is a
  precondition guard after the sender check
  (``vultron.core.behaviors.case.nodes.ownership_reply_guard``)
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
  sender's closure; the receive-tree factory's closed-sender door runs it, so
  the handler tells a repeated closing act (``SKIPPED``) from any other act
  (``REFUSED``) (CM-23-018)
- ``NoSenderAdmittedNode`` — refuses every sender on a side a ``SenderRule``
  leaves empty (HP-01-024)
- ``SenderHoldsNoneOfNode`` — the last arm of an any-of side, naming every
  standing the side accepts (HP-01-023)

Helper predicate
----------------
``is_case_owner(case, actor_id)`` — pure boolean predicate; merged from
``_is_case_owner`` in ``vultron.core.use_cases.triggers._helpers``.

Submodules
----------
- ``declarations`` — the kinds, addressee sides, rule and exemptions
- ``base`` — the base class and its refusal-placement rule
- ``case_owner`` — ``is_case_owner`` and ``SenderIsCaseOwnerNode``
- ``membership`` — the participant-record checks and the closed-sender check
- ``case_manager`` — ``SenderIsCaseManagerNode``
- ``addressee`` — the ``NAMED_ACTOR`` base and its request-record checks
- ``invitee`` — the Invite's invitee and the role Offer's target
- ``ownership`` — the parties to an ownership-transfer Offer
- ``author`` — the ``AUTHOR`` checks
- ``side_refusals`` — the empty-side and any-of refusals

Spec: HP-01-006, HP-01-007, CM-10-004, PCR-03-001.
"""

from vultron.core.behaviors.sender_entitlement.addressee import (
    NoStandingError,
    NothingToProtect,
    RecordedRequest,
    SenderIsExpectedCaseCreatorNode,
    SenderIsOfferAddresseeNode,
    SenderIsProposalAddresseeNode,
    SenderIsRequestAddresseeNode,
)
from vultron.core.behaviors.sender_entitlement.author import (
    SenderIsNoteAuthorNode,
    SenderIsParticipantRecordSubjectNode,
    SenderIsProposalAuthorNode,
)
from vultron.core.behaviors.sender_entitlement.base import (
    SenderEntitlementConditionNode,
    failure_is_the_refusal,
)
from vultron.core.behaviors.sender_entitlement.case_manager import (
    SenderIsCaseManagerNode,
)
from vultron.core.behaviors.sender_entitlement.case_owner import (
    SenderIsCaseOwnerNode,
    is_case_owner,
)
from vultron.core.behaviors.sender_entitlement.declarations import (
    AddresseeSide,
    SenderEntitlement,
    SenderEntitlementKind,
    SenderExemption,
    SenderRule,
    any_of,
    exempt,
    in_declaration_order,
    no_sender_check,
)
from vultron.core.behaviors.sender_entitlement.invitee import (
    SenderIsInviteeNode,
    SenderIsRoleOfferTargetNode,
)
from vultron.core.behaviors.sender_entitlement.membership import (
    SenderClosureNotRecordedNode,
    SenderIsActiveLedgerParticipantNode,
    SenderIsActiveParticipantNode,
    SenderIsParticipantNode,
)
from vultron.core.behaviors.sender_entitlement.ownership import (
    SenderIsOfferingCaseOwnerNode,
    SenderIsOwnershipOffererNode,
    SenderIsOwnershipOfferPartyNode,
    SenderIsOwnershipTransfereeNode,
)
from vultron.core.behaviors.sender_entitlement.side_refusals import (
    NoSenderAdmittedNode,
    SenderHoldsNoneOfNode,
)

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
    "no_sender_check",
    # Helper predicates
    "is_case_owner",
    "failure_is_the_refusal",
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
    "SenderIsExpectedCaseCreatorNode",
    "SenderIsOwnershipOfferPartyNode",
    "SenderIsOwnershipTransfereeNode",
    "SenderIsRoleOfferTargetNode",
    "SenderIsOfferingCaseOwnerNode",
    "SenderIsOwnershipOffererNode",
    "SenderIsInviteeNode",
    "SenderIsOfferAddresseeNode",
    "SenderIsCaseOwnerNode",
    "SenderIsNoteAuthorNode",
    "SenderIsProposalAuthorNode",
    "SenderIsParticipantRecordSubjectNode",
    "SenderClosureNotRecordedNode",
    "NoSenderAdmittedNode",
    "SenderHoldsNoneOfNode",
]
