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

"""Ledger recording of the RM closure transitions a Leave causes.

Separate module from :mod:`.advance` because applying a state change to the
local store and recording it as a canonical ``CaseLedgerEntry`` are different
concerns — and conflating them is what let ISSUE-2505 happen: the advance
existed, the record did not.

Per CM-23-001, CM-23-002 steps 1-2, CM-23-003, CM-23-005; ADR-0051.
"""

from vultron.core.behaviors.case.nodes.participant.status_entries import (
    CommitParticipantStatusEntriesNode,
)


class CommitRMClosureEntriesNode(CommitParticipantStatusEntriesNode):
    """Record each RM closure step a Leave caused, one ledger entry per step.

    The advance node just before this one (:class:`~.advance
    .AdvanceParticipantToRMClosedNode` for the leaving actor,
    :class:`~.advance.AdvanceCaseActorToRMClosedNode` for the CASE_MANAGER
    itself) writes the closure to the CASE_MANAGER's *own* store and reports
    the id of each status it wrote in the shared ``closure_steps`` list.  This
    node commits one ``add_participant_status_to_participant`` entry for each
    of those statuses, in order, and fans it out.  A closure from *Valid*
    writes ``V → D → C`` (RMB-14-005), so it records two entries.

    **Why every step is its own entry.**  A replica is the case as seeded plus
    the ledger entries since (CM-23-016).  It applies these status entries
    through the ordinary participant-status effect and never works out a
    closure path from its own stored state: the ``close_case`` entry that
    records the Leave changes no RM state anywhere (CM-23-001).  A replica
    that walked the RM table instead would write a step no entry backs when
    it held an older status for the actor (#4091).  The entries are not the
    Leave's duplicate: the Leave is the act, these are the transitions the
    CASE_MANAGER wrote as its consequence (CLP-07-002).

    **Why the CASE_MANAGER's own closure needs it too.**  ``close_case`` names
    the *departing* actor, and the Case Actor never sends itself a ``Leave``.
    Without its own entries the CASE_MANAGER is permanently ``RM.ACCEPTED``
    on every replica (ISSUE-2505), and its entry reaching ``RM.CLOSED`` is
    the owner-close write boundary (CM-23-013, ADR-0085).

    **Attribution.**  The CASE_MANAGER authors each entry: the snapshot's
    ``actor`` is the receiving CASE_MANAGER and its ``published`` is the
    CASE_MANAGER's clock.  The status inside it is the closing actor's
    (``attributedTo``).  This is not the trap-3 case of
    ``notes/case-ledger-authority.md``: no snapshot here poses as the leaving
    actor's own act, so no claimed time is carried or invented.

    **Fan-out.**  Through the standard commit tree, to every active
    participant not at ``RM.CLOSED``, plus the closing actor itself: the
    advance has already written its ``CLOSED`` when the first of these
    entries fans out, but each entry records the closing actor's own closure,
    so the shared selection still sends it (``ledger_entry_recipients``,
    CM-23-004).  The leaving actor's replica therefore receives every step,
    the one that reaches ``RM.CLOSED`` included, and nothing after them.

    Committed synchronously here rather than emitted as a self-addressed
    ``Add(ParticipantStatus)`` through the CLP-10-001 loopback, because
    CM-23-002 orders these entries: the leaver's precede the CASE_MANAGER's,
    whose ``RM.CLOSED`` entry is the owner-close write boundary after which
    no external act is recorded (CM-23-013).  Loopback delivery is an outbox
    background task, so it could not honour that ordering.

    Idempotent by construction: ``CreateLogEntryNode`` skips an entry that
    already exists for the same object (the status id), and the node no-ops
    when the advance wrote nothing (the actor was already ``RM.CLOSED``).

    **A step with no committed entry is not kept** (CLP-07-013, CM-23-001).
    The advance writes each step before this node commits it, the order
    CLP-07-013 gives a consequence, and both run in the Leave's
    ``ActTransaction``: a commit that fails fails the act, which keeps no
    step, no entry and not the ``close_case`` entry either (CLP-07-015).  A
    refused commit returns FAILURE, a missing trigger-activity port raises
    :class:`~vultron.errors.VultronWiringError`, and a nested commit that
    reports ``internal_error`` raises
    :class:`~vultron.errors.VultronBTInternalError`.  The Leave is then not
    applied, and a redelivered Leave walks the closure afresh.

    The commits skip ``CheckLedgerFreshnessNode``: a gapped local prefix
    fails that check by design
    (SYNC-10-001/002), and it must not block case closure (CM-23-002).

    Per CM-23-001, CM-23-002 steps 1-2, CM-23-003, CM-23-005, CLP-07-013;
    ADR-0051.
    """

    #: A gapped local prefix must not block case closure (CM-23-002,
    #: SYNC-10-001/002).
    check_freshness = False

    def __init__(
        self,
        closing_actor_id: str,
        case_id: str,
        closure_steps: list[str],
        name: str | None = None,
    ) -> None:
        """Create the node.

        Args:
            closing_actor_id: The actor whose closure is recorded: the leaving
                actor, or the CASE_MANAGER closing its own lifecycle.
            case_id: The case.
            closure_steps: The list the paired advance node fills with the id
                of each status it wrote, in order.
            name: Node name.
        """
        super().__init__(
            subject_actor_id=closing_actor_id,
            case_id=case_id,
            status_ids=closure_steps,
            name=name,
        )
