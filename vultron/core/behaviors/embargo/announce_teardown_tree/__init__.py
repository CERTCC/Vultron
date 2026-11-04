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

"""
Embargo lifecycle behavior tree compositions.

Provides factory functions for the received-side embargo BTs:

``invite_to_embargo_on_case_tree`` — handles receipt of an ``Invite(EmbargoEvent)``
activity (protocol EP / EV message).  Two role-gated arms behind the shared
intake and guarded commit (ADR-0113, EP-09): the CASE_MANAGER adjudicates the
proposal (``ProposeEmbargoLifecycleNode``) and relays it to every participant
except the proposer (``RelayEmbargoInviteToEachNode``, ``nodes/relay.py``); the
addressee's store answers the Invite to the CASE_MANAGER and writes no state
(EP-09-003).  The tree's docstring draws it.

``remove_embargo_from_case_tree`` — handles receipt of a ``Remove(EmbargoEvent)``
activity (protocol ET message).  Two role-gated arms behind the shared intake
and guarded commit; each tears its own copy down only when the embargo is in
force, and only the CASE_MANAGER announces (BT-17-008):

    RemoveEmbargoFromCaseBT (Sequence)
    ├─ ClockDecisionsIfCaseManager        # end time, overdue invites (CM-28-015)
    ├─ ValidateCaseExistsNode             # case must exist as VulnerabilityCase
    ├─ TerminationCauseIsAdmissibleNode   # THREAT_SIGNAL: the CASE_MANAGER's only
    ├─ TerminationIsTimelyNode            # no END_TIME_REACHED before the end time
    └─ RemoveEmbargoFromCaseBTAct (ActTransaction)  # one act (ADR-0151)
       ├─ GuardedCommitCaseLedgerEntryBT     # record receipt before effects (CLP-10-006)
       ├─ TeardownOnReplica (Selector)       # participant replica: paused only
       │  ├─ SkipIfCaseManager
       │  └─ ReplicaTeardownIfEndingNoticeAwaited (Selector)  # CM-31-010 only
       │     ├─ SkipUnlessEndingNoticeAwaited (Inverter)      # active replica: skip
       │     │  └─ AwaitsEmbargoEndingNoticeNode              # paused-stream check
       │     └─ ReplicaApplyEndingNotice (Sequence)
       │        ├─ AdoptRemovedEmbargoRevisionNode  # overtaken Announce (SYNC-19-001)
       │        └─ ReplicaTeardownIfActive (Selector)
       │           ├─ EmbargoWasNotActive / EmbargoAlreadyExited  # nothing to do
       │           └─ ReplicaActiveTeardown: ClearActiveEmbargoNode  # sends nothing
       └─ TeardownAndAnnounceIfCaseManager (CaseManagerGate, from the factory)
          └─ TeardownIfActive (Selector)
             ├─ EmbargoWasNotActive / EmbargoAlreadyExited   # nothing to tear down
             └─ ActiveTeardown (Sequence)    # its FAILURE is the tree's FAILURE
                ├─ CaptureActiveEmbargoNode     # the embargo in force before the write
                ├─ ClearActiveEmbargoNode       # TERMINATE + CANCEL every proposal → EXITED
                ├─ SendAnnounceEmbargoEventNode # Announce(EmbargoEvent) to the others
                ├─ SendEmbargoEndingNoticesNode # ET to unreached signatories (CM-31-009)
                ├─ BackfillAdmittedParticipantsNode  # backfill paused peers (CM-10-006)
                └─ ReissueStubInvitesNode       # re-issue stale stub Invites (CM-11-016)

At a replica the teardown is the CASE_MANAGER's ``Remove(EmbargoEvent)``,
admitted by the sender guard only from the CASE_MANAGER (ADR-0115).  An active
replica takes the teardown from the ledger (EmbargoTeardown slot) and writes
nothing (RSH-08-003); the CM-31-009 ending notices are the CASE_MANAGER's, so
they sit in the CASE_MANAGER arm.  The one replica that still writes its own
copy is a signatory whose ledger stream is paused (removed, withheld, or at RM
``CLOSED``): that direct notice is its only channel, and it applies the
teardown through the one apply function (CM-31-010, ADR-0124) on the receive
side, as the CASE_MANAGER's arm does.  The
RSH-08-003 replica gate (#3814) gates that write on
``AwaitsEmbargoEndingNoticeNode``, so only the paused signatory tears down
directly.  A ``Remove`` naming a revision that replica has not activated
means that revision replaced its embargo: the revision's ``Announce`` notice
(CM-31-030) is late, or none was owed for a longer revision.  The replica
activates the revision first and then tears it down, ending as the in-order
delivery does (SYNC-19-001, CM-31-042).

Per specs/behavior-tree-integration.yaml BT-06-001.
"""

from vultron.core.behaviors.embargo.announce_teardown_tree.invite import (
    invite_to_embargo_on_case_tree,
)
from vultron.core.behaviors.embargo.announce_teardown_tree.teardown import (
    remove_embargo_from_case_tree,
)

__all__ = [
    "invite_to_embargo_on_case_tree",
    "remove_embargo_from_case_tree",
]
