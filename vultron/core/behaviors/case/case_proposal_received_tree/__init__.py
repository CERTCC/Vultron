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

"""BT tree for the CreateCaseProposal received-side use case.

Case-actor side: handles an inbound ``Create(CaseProposal)`` and emits
two outbound activities in sequence:

  1. ``Accept(CaseProposal)`` — acknowledgement to the report receiver
  2. ``Create(VulnerabilityCase)`` — case announcement to the report receiver

The accept flow performs CaseActor-native initialization per ADR-0041, emits
the outbound activities, commits the canonical ledger entries (CP-09-009) and
relays a contested creation's revision:

  1. Resolve (or create) the case, attributed to the proposer (CP-09-001)
  2. Add the proposer as CASE_OWNER at RM.RECEIVED, plus the roles it
     stated on the proposal (AC-1, CP-09-007, ADR-0133)
  3. Add reporter as participant at RM.ACCEPTED (AC-2)
  4. Initialize the default embargo, seeding the CASE_OWNER as a signatory
     (AC-3, CM-14-003); a contest registers the losing terms as a revision
     (EP-04-016)
  5. Seed reporter as an embargo signatory (CM-14-005)
  6. Emit ``Accept(CaseProposal)``
  7. Emit ``Create(VulnerabilityCase)`` with inline participants (AC-5)
  8. Commit canonical ledger entries (AC-4) — after the emits, so every
     participant holds the case before its first ``Announce(CaseLedgerEntry)``
     (CM-14-011, CP-09-009)
  9. Relay a contested creation's revision to the party whose terms won
     (EP-04-027) — after initialization is complete (CM-14-014)

Steps 1-9, with the admission record ahead of them, are one act: they run in
one ``ActTransaction`` (ADR-0146, CLP-07-015), so a failed step rolls back
the case, its records, the queued ``Accept`` and ``Create``, the relayed
``Invite`` and every creation entry already committed (CLP-07-013, #4442).
Nothing is kept for a later run: a redelivery of the proposal processes it
fresh.  Once the act commits, the durable outbox retries the delivery of
each queued activity (OX-13, CP-05-011).

Admission (CP-05-002) and idempotency (CP-05-006):

Ahead of the branches, the receive-tree factory composes the sender guard from
the use case's ``AUTHOR`` declaration: the proposal id is chosen by the sender,
so one this store recorded for another proposer is refused before any branch
reads or writes a proposal-keyed record (CP-05-010, HP-01-008, #4719).

The top-level tree is a Selector with four branches, tried in order:

* **Already declined** — ``CheckDeclineRecordExistsNode``: a
  ``CaseProposalDeclineRecord`` exists, so the decision stands and is not
  re-made.  The record commits with its ``Reject``, so a stored record means
  the ``Reject`` was queued.

* **Closed case** — ``DeclineClosedCaseProposalArm``: the proposal resolves to
  a fully closed case (the owner's own case for the report, or the case this
  proposal's stored ``Accept`` names), so record the decline and emit
  ``Reject(CaseProposal)``.  Nothing is written for the case (CP-05-014,
  CP-05-015, CP-05-018, CP-05-019, CM-23-013).  The factory's post-close guard
  cannot do this: the proposal names a report, not a case.

* **Decline** — ``DeclineProposalArm``: the ``EvaluateCaseProposal`` call-out
  point refused, so record the decline and emit ``Reject(CaseProposal)``.
  Its guards are proposal-keyed: ``report_id`` is supplied by the sender, so a
  report-keyed guard is one the sender can satisfy in order to skip the gate.

* **Accept** — ``CreateCaseFromProposalAct``: the accept flow above, which
  first writes the proposal-keyed ``CaseProposalAdmissionRecord`` (so a later
  delivery can tell that *this* proposal was accepted) and then
  resolves the case via a Selector between ``LoadExistingCaseNode`` (AC-1/AC-2:
  finds and reuses the existing ``VulnerabilityCase`` the proposal resolves
  to — the proposer's own case for the report, or the case the proposal's
  stored ``Accept`` names) and ``CreateCaseFromProposalNode`` (normal path:
  creates a new case).

Why a decline fails the tree
----------------------------
A Selector falls through on FAILURE, and ``_EmitSingleActivityBase.update()``
converts *any* exception into FAILURE.  A decline whose ``Reject`` could not be
built — no wire proposal, no injected ``TriggerActivityPort``, a store error —
would otherwise fall through to the accept flow and create the case, commit
ledger entries, and send ``Accept`` + ``Create``, reporting SUCCESS.  A refusal
gate whose failure direction is "admit" is worse than no gate, so each decline
records its decision and emits its ``Reject`` in one ``RefusalActTransaction``:
a failure rolls both back and fails the tree, instead of admitting.

Spec: ``specs/case-proposal.yaml`` CP-05-001 through CP-05-006, CP-05-008.
Per: ``docs/adr/0041-caseactor-authoritative-case-initialization.md``,
``docs/adr/0025-call-out-point-abstraction-layer.md``.

The package is split by concern (CS-18-005): ``factory`` composes the tree
and ``arms`` builds its decline and accept arms.
"""

from vultron.core.behaviors.case.case_proposal_received_tree.arms import (
    CLOSED_CASE_DECLINE_REASON,
)
from vultron.core.behaviors.case.case_proposal_received_tree.factory import (
    create_case_proposal_received_tree,
)

__all__ = [
    "CLOSED_CASE_DECLINE_REASON",
    "create_case_proposal_received_tree",
]
