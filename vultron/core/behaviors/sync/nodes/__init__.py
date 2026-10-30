#!/usr/bin/env python
#
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
SYNC log-replication behavior tree nodes subpackage.

Re-exports all public node classes from domain-specific submodules so that
existing import paths (``from vultron.core.behaviors.sync.nodes import ...``)
continue to work without modification.

Submodules:
- ``conditions``: Idempotency guard and sender verification condition nodes
- ``receive``: Log entry delivery and validation action nodes
- ``replay_held``: Replay the held Announce of a ledger successor (SYNC-14-009)
- ``chain``: Chain reconstruction and log entry creation action nodes
- ``canonical_entry``: Canonical ``payloadSnapshot`` validation (CLP-07)
- ``replay``: Reject- and Read-driven replay action nodes for replication
- ``replay_case``: the case a replay or position statement is about
- ``ledger_position``: the CASE_MANAGER's answer to the ``ledgerPosition``
  every case activity stamps: lag, split, inert sender (SYNC-18)
- ``position_statement``: the ``Read(CaseLedgerEntry)`` position check and
  the participant's position statements (SYNC-17)
- ``invite_resend``: the resend of each Invite a participant that states its
  position still owes an answer to (SYNC-20)
- ``genesis_announce``: the genesis-Reject case pre-seed (SYNC-15-015)
- ``reseed``: the rate-bounded re-seed of a diverged peer with a fresh case
  copy, and the log of a divergence a re-seed already covered: ERROR once the
  peer acknowledged that re-seed's position, WARNING before (SYNC-16)
- ``hash_mismatch``: the CASE_MANAGER's ERROR report of a replica's
  hash-mismatch fault, with a re-check of its own copy (SYNC-03-010)
- ``verified_send``: the one ``send_announce_log_entry`` call, behind the
  CASE_MANAGER's send-side hash check (SYNC-03-009)
- ``embargo_pause``: the CM-10-005/006 embargo pause and backfill helpers
- ``embargo_backfill``: ``BackfillAdmittedParticipantsNode`` (CM-10-006)
- ``fanout``: Fan-out action nodes; RM.CLOSED participants are skipped
  except for the entries recording their own closure (CM-23-004)
- ``effects``: Ledger-apply side-effect nodes (note, invite-accept)
- ``ledger_entry_fault``: the replica's ``Create(ProcessingFault)`` about a
  refused ledger entry, sent to the CASE_MANAGER and never ledgered (SYNC-16-002)
- ``participant_status_effect``: Ledger-apply of ``ParticipantStatus``, copying
  the status the entry carries (CM-23-016)
- ``offer_report_effect``, ``ownership_effects``,
  ``participant_removal_effect``: per-effect ledger-apply nodes
- ``case_status_effect``: Ledger-apply of ``add_case_status_to_case``, copying
  the status the entry carries (CM-23-016)

A ``close_case`` entry has no effect slot: it records the received Leave, and
the RM transitions the Leave caused arrive as the status entries after it
(CM-23-001, CM-23-016).  The activity-typed RM moves (report verdicts,
engage/defer, the full-case Invite replies) have none either, for the same
reason: the status the CASE_MANAGER wrote follows as its own entry
(CLP-07-013).

Every case node that commits imports
:mod:`~vultron.core.behaviors.sync.commit_tree`, which loads this package, so
a module here that imported ``case.nodes`` would close an import cycle
(CS-05-003).  Nodes in this package depend on no domain node package.
"""

from vultron.core.behaviors.sync.nodes.case_status_effect import (
    ApplyCaseStatusFromLedgerNode,
    IsAddCaseStatusEventNode,
)
from vultron.core.behaviors.sync.nodes.chain import (
    CreateLogEntryNode,
    PersistLogEntryNode,
    ReconstructChainTailNode,
    UpdateReplicationStateNode,
)
from vultron.core.behaviors.sync.nodes.conditions import (
    CheckEntryAgreesWithCasePositionNode,
    CheckLedgerEntryAlreadyStoredNode,
    CheckLedgerFreshnessNode,
    EntryReflectedByCaseCopyNode,
    _require_log_entry,
)
from vultron.core.behaviors.sync.nodes.embargo_backfill import (
    BackfillAdmittedParticipantsNode,
)
from vultron.core.behaviors.sync.nodes.event_conditions import (
    IsAcceptEmbargoInviteEventNode,
    IsAddNoteEventNode,
    IsCreateCaseParticipantEventNode,
    IsCreateEmbargoEventNode,
    IsEmbargoAbandonmentEventNode,
    IsEmbargoInviteRelayEventNode,
    IsEmbargoProposalEventNode,
    IsInviteAcceptEventNode,
    IsInviteRejectEventNode,
    IsOwnershipTransferEventNode,
    IsParticipantStatusEventNode,
    IsRejectEmbargoInviteEventNode,
    IsRemoveEmbargoEventNode,
    IsRemoveNoteEventNode,
    IsSubmitReportEventNode,
    IsUndoEmbargoInviteEventNode,
    IsWithdrawFromEmbargoEventNode,
)
from vultron.core.behaviors.sync.nodes.fanout import (
    CollectLogEntryRecipientsNode,
    FanOutLogEntryNode,
    SendLogEntryToEachNode,
)
from vultron.core.behaviors.sync.nodes.genesis_announce import (
    AnnounceCaseOnGenesisRejectNode,
)
from vultron.core.behaviors.sync.nodes.hash_mismatch import (
    ReportHashMismatchNode,
)
from vultron.core.behaviors.sync.nodes.invite_resend import (
    ResendOwedInvitesNode,
)
from vultron.core.behaviors.sync.nodes.ledger_authority import (
    DeclineForeignLedgerCommitNode,
)
from vultron.core.behaviors.sync.nodes.ledger_entry_fault import (
    EmitLedgerEntryFaultNode,
)
from vultron.core.behaviors.sync.nodes.note_effect import (
    ApplyNoteFromLedgerNode,
    ApplyRemoveNoteFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.offer_report_effect import (
    ApplyOfferReportFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.ownership_effects import (
    ApplyOwnershipTransferFromLedgerNode,
)
from vultron.core.behaviors.sync.nodes.participant_record_effect import (
    ApplyCaseParticipantUpdateFromLedgerNode,
    ApplyCreateCaseParticipantFromLedgerNode,
    IsUpdateCaseParticipantEventNode,
)
from vultron.core.behaviors.sync.nodes.participant_removal_effect import (
    ApplyReinstateCaseParticipantFromLedgerNode,
    ApplyRemoveCaseParticipantFromLedgerNode,
    IsReinstateCaseParticipantEventNode,
    IsRemoveCaseParticipantEventNode,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
    EmitImpossibleStateFaultNode,
)
from vultron.core.behaviors.sync.nodes.port_guard import (
    RequireSyncPortNode,
    RequireWireRenderPortNode,
)
from vultron.core.behaviors.sync.nodes.position_statement import (
    CheckStatedPositionInLedgerNode,
    StateLedgerPositionsNode,
)
from vultron.core.behaviors.sync.nodes.receive import (
    BufferOutOfOrderEntryNode,
    BufferPreGenesisEntryNode,
    CheckEntryHashIntactNode,
    CheckHashMatchesNode,
    CheckHashOrRejectOnMismatchNode,
    LogDeliveryConfirmationNode,
    PersistReceivedLogEntryNode,
    SendRejectLogEntryNode,
)
from vultron.core.behaviors.sync.nodes.replay import (
    CollectAndSortCaseLedgerEntriesNode,
    FindCaseActorNode,
    FindDivergenceIndexNode,
    ReplayMissingEntriesNode,
    SendMissingEntriesNode,
)
from vultron.core.behaviors.sync.nodes.replay_held import (
    ReplayHeldSuccessorNode,
)
from vultron.core.behaviors.sync.nodes.reseed import (
    ReportRepeatDivergenceNode,
    ReseedPeerNode,
)
from vultron.core.behaviors.sync.nodes.role_grant_effect import (
    ApplyCaseParticipantRoleGrantFromLedgerNode,
    IsAcceptCaseParticipantRoleEventNode,
)
from vultron.core.behaviors.sync.nodes.stub_reply_effect import (
    ApplyInviteAcceptFromLedgerNode,
    ApplyInviteRejectFromLedgerNode,
)

__all__ = [
    # conditions
    "CheckEntryAgreesWithCasePositionNode",
    "CheckLedgerEntryAlreadyStoredNode",
    "CheckLedgerFreshnessNode",
    "EntryReflectedByCaseCopyNode",
    "IsRemoveEmbargoEventNode",
    "IsParticipantStatusEventNode",
    "IsAddNoteEventNode",
    "IsRemoveNoteEventNode",
    "IsCreateCaseParticipantEventNode",
    "IsCreateEmbargoEventNode",
    "IsUpdateCaseParticipantEventNode",
    "IsInviteAcceptEventNode",
    "IsInviteRejectEventNode",
    "IsSubmitReportEventNode",
    "IsOwnershipTransferEventNode",
    "IsEmbargoProposalEventNode",
    "IsEmbargoInviteRelayEventNode",
    "IsAcceptEmbargoInviteEventNode",
    "IsRejectEmbargoInviteEventNode",
    "IsUndoEmbargoInviteEventNode",
    "IsWithdrawFromEmbargoEventNode",
    "IsEmbargoAbandonmentEventNode",
    # effects
    "ApplyNoteFromLedgerNode",
    "ApplyCaseParticipantRoleGrantFromLedgerNode",
    "ApplyRemoveNoteFromLedgerNode",
    "ApplyCreateCaseParticipantFromLedgerNode",
    "ApplyCaseParticipantUpdateFromLedgerNode",
    "ApplyInviteAcceptFromLedgerNode",
    "ApplyInviteRejectFromLedgerNode",
    # ledger_entry_fault (RSH-09-006, SYNC-03-007, SYNC-16-001)
    "EmitLedgerEntryFaultNode",
    # participant_status_effect
    "ApplyParticipantStatusFromLedgerNode",
    "EmitImpossibleStateFaultNode",
    # per-effect ledger-apply modules
    "ApplyOfferReportFromLedgerNode",
    "ApplyOwnershipTransferFromLedgerNode",
    "IsAcceptCaseParticipantRoleEventNode",
    # participant_removal_effect (CM-31-007, CM-31-011)
    "ApplyReinstateCaseParticipantFromLedgerNode",
    "ApplyRemoveCaseParticipantFromLedgerNode",
    "IsReinstateCaseParticipantEventNode",
    "IsRemoveCaseParticipantEventNode",
    "ApplyCaseStatusFromLedgerNode",
    "IsAddCaseStatusEventNode",
    # receive
    "LogDeliveryConfirmationNode",
    "PersistReceivedLogEntryNode",
    "CheckEntryHashIntactNode",
    "CheckHashMatchesNode",
    "BufferOutOfOrderEntryNode",
    "BufferPreGenesisEntryNode",
    # replay_held
    "ReplayHeldSuccessorNode",
    "SendRejectLogEntryNode",
    "CheckHashOrRejectOnMismatchNode",
    # chain
    "ReconstructChainTailNode",
    # ledger authority
    "DeclineForeignLedgerCommitNode",
    # port guard
    "RequireSyncPortNode",
    "RequireWireRenderPortNode",
    "UpdateReplicationStateNode",
    "CreateLogEntryNode",
    "PersistLogEntryNode",
    # position_statement (SYNC-17)
    "CheckStatedPositionInLedgerNode",
    "StateLedgerPositionsNode",
    # invite_resend (SYNC-20)
    "ResendOwedInvitesNode",
    # replay
    "AnnounceCaseOnGenesisRejectNode",
    # hash_mismatch (SYNC-03-010)
    "ReportHashMismatchNode",
    # reseed (SYNC-16)
    "ReportRepeatDivergenceNode",
    "ReseedPeerNode",
    "FindCaseActorNode",
    "CollectAndSortCaseLedgerEntriesNode",
    "FindDivergenceIndexNode",
    "SendMissingEntriesNode",
    "ReplayMissingEntriesNode",
    "CollectLogEntryRecipientsNode",
    "SendLogEntryToEachNode",
    "FanOutLogEntryNode",
    # embargo_backfill
    "BackfillAdmittedParticipantsNode",
    # re-exported helper function (backward compat)
    "_require_log_entry",
]
