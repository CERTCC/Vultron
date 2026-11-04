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

"""Compose a sender guard from a declared :class:`SenderRule` (HP-01-025).

The receive-tree factory calls :func:`compose_sender_guard` with the use
case's declared rule and a :class:`SenderCheckContext` naming the records the
kinds' condition nodes read.  The predicates themselves stay in
:mod:`vultron.core.behaviors.sender_entitlement` (HP-01-007); this package only
chooses and arranges them.

Composition:

- An activity that names no case is checked against the rule's
  ``outside_case`` side.
- Otherwise, when the CASE_MANAGER and participant sides name the same kinds,
  the guard is those kinds' any-of selector, whoever receives the activity.
  An any-of selector ends with :class:`SenderHoldsNoneOfNode`, so a refused
  sender's reason names every kind the side accepts.
- Otherwise the guard dispatches on the receiver's side::

      SenderRuleGuard (Sequence)
      ├── AtCaseManager (Selector): Inverter(CheckIsCaseManager), <manager kinds>
      └── AtParticipant (Selector): CheckIsCaseManager, <participant kinds>

  Each arm passes on the other side, and on its own side fails on its own
  kinds' failure, so the refusal reason is the failing kind's (BT-13-001).

Each kind's node reads the records the context names.  ``NAMED_ACTOR`` is
one kind whatever the request (HP-01-009): the context's ``request`` names the
record holding it, and the factory picks the small check for that record, all
on one addressee base (``SenderIsRequestAddresseeNode``).  ``AUTHOR`` is one
kind whatever the object: the context's ``authored_object`` names it, and the
factory picks the note-author, proposal-author or participant-record check
for it.

An activity that carries a ``CaseLedgerEntry`` has no case at build time: the
entry names it.  Its tree passes a :class:`LedgerActivityContext`, and the
kinds' nodes read the sender and the case from the activity on the blackboard
at run time (SYNC-03-005, SYNC-13-006).  Only the kinds whose nodes can do
that may be declared for it: ``CASE_MANAGER`` and ``LEDGER_PEER``.

An empty side composes :class:`NoSenderAdmittedNode`, so an activity that
names no case is refused under a rule with no ``outside_case`` side; ``ANY_ACTOR`` composes
no node, so a rule that admits any actor composes no guard at all.

The context records live in :mod:`vultron.core.behaviors.sender_check_context`
and are re-exported here.  Beside the composer sit the closed-sender door
(:func:`closed_sender_door`, built from :func:`closed_sender_guard` and
:func:`case_owner_guard`, read back by :func:`closed_sender_turned_away`) and
:func:`sender_guard_refused`, which tells a handler its run ended at the
composed guard.

Submodules: ``compose`` (the composer and :func:`sender_guard_refused`),
``kind_nodes`` (the node each kind composes) and ``doors`` (the
closed-sender door and the checks it is built from).
"""

from vultron.core.behaviors.sender_check_context import (
    AddresseeRequest,
    AuthoredCaseProposal,
    AuthoredNote,
    AuthoredObject,
    AuthoredParticipantRecord,
    CaseBootstrapRequest,
    CaseProposalRequest,
    ClosedSenderCheck,
    LedgerActivityContext,
    OwnershipOfferRequest,
    ReportOfferRequest,
    RoleOfferRequest,
    SenderCheckContext,
    SenderContext,
    embargo_sender_context,
)
from vultron.core.behaviors.sender_guard.compose import (
    compose_sender_guard,
    is_composed_sender_guard,
    sender_guard_refused,
)
from vultron.core.behaviors.sender_guard.doors import (
    case_owner_guard,
    closed_sender_door,
    closed_sender_guard,
    closed_sender_turned_away,
)

__all__ = [
    "AddresseeRequest",
    "AuthoredCaseProposal",
    "AuthoredNote",
    "AuthoredObject",
    "AuthoredParticipantRecord",
    "CaseBootstrapRequest",
    "case_owner_guard",
    "CaseProposalRequest",
    "ClosedSenderCheck",
    "LedgerActivityContext",
    "OwnershipOfferRequest",
    "ReportOfferRequest",
    "RoleOfferRequest",
    "SenderCheckContext",
    "SenderContext",
    "closed_sender_door",
    "closed_sender_guard",
    "closed_sender_turned_away",
    "compose_sender_guard",
    "embargo_sender_context",
    "is_composed_sender_guard",
    "sender_guard_refused",
]
