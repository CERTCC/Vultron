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

"""Architecture ratchet: a node's failure line says what it is (SL-03-003).

A node whose FAILURE records a reason the handler may report as a refusal
logs that reason at DEBUG, through
:func:`~vultron.core.behaviors.node_logger.fail_with_reason`; a fault keeps
its SL-03-001 level, through
:func:`~vultron.core.behaviors.node_logger.fail_with_fault` (or
:func:`~vultron.core.behaviors.node_logger.fail_with_error`, which picks one
from the error).  A hand-written ``.warning(..., <x>.feedback_message)`` under
``vultron/core/behaviors/`` states neither: it is a refusal reason at the
wrong level, or a fault no reader can tell from one.

``KNOWN_NODE_FEEDBACK_WARNINGS`` lists the sites that predate the rule, one
per enclosing function, keyed ``<path>::<qualname>``.  Follow-up Task #6507
sorts each into a refusal or a fault and empties it.  A new site fails; an
entry whose site is gone fails until it is removed, so the list only shrinks.
The reading can miss a site that logs its reason through another name (a
local ``reason`` variable); it cannot invent one.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_BEHAVIORS = _corpus.REPO_ROOT / "vultron" / "core" / "behaviors"

# owner: #6507
KNOWN_NODE_FEEDBACK_WARNINGS: frozenset[str] = frozenset(
    {
        "vultron/core/behaviors/case/nodes/announce.py::SeedAnnouncedCaseNode.update",
        "vultron/core/behaviors/case/nodes/carried_snapshot.py::_CarriedEmbargoNode.update",
        "vultron/core/behaviors/case/nodes/case_lookup.py::CaseIdInputPortMixin._resolve_case_id",
        "vultron/core/behaviors/case/nodes/clock_decision_stage.py::ClockDecision.update",
        "vultron/core/behaviors/case/nodes/delegation.py::IsRoleOfferTargetNode.update",
        "vultron/core/behaviors/case/nodes/delegation.py::_AnswerCaseParticipantRoleOfferBase._validate_context",
        "vultron/core/behaviors/case/nodes/invite_inert_participant.py::_SeatInertInviteeBase._existing_record_outcome",
        "vultron/core/behaviors/case/nodes/leave/advance.py::AdvanceCaseActorToRMClosedNode.update",
        "vultron/core/behaviors/case/nodes/leave/advance.py::AdvanceParticipantToRMClosedNode.update",
        "vultron/core/behaviors/case/nodes/lifecycle.py::CommitCaseLedgerEntryNode._refuse_unrecordable",
        "vultron/core/behaviors/case/nodes/ownership_transfer_apply.py::_TransferCaseOwnershipNode.update",
        "vultron/core/behaviors/case/nodes/participant/common.py::report_unshaped_status",
        "vultron/core/behaviors/case/nodes/participant/common.py::validate_participant_status_write",
        "vultron/core/behaviors/case/nodes/participant/rm_closure.py::RMClosureWriter.close",
        "vultron/core/behaviors/case/nodes/participant/trigger_validation.py::ValidateTriggerTransitionsNode.update",
        "vultron/core/behaviors/case/nodes/participant/trigger_validation.py::check_participant_status_move",
        "vultron/core/behaviors/case/nodes/proposal.py::ProposeReportCaseToActorNode.update",
        "vultron/core/behaviors/case/nodes/proposal_admission_actions.py::RecordProposalAdmissionNode.update",
        "vultron/core/behaviors/case/nodes/proposal_case_resolution.py::CreateCaseFromProposalNode.update",
        "vultron/core/behaviors/case/nodes/proposal_emits.py::EmitAcceptCaseProposalNode.update",
        "vultron/core/behaviors/case/nodes/proposal_emits.py::EmitCreateVulnerabilityCaseNode.update",
        "vultron/core/behaviors/case/nodes/replica_bootstrap.py::CheckInlineParticipantsNode.update",
        "vultron/core/behaviors/case/nodes/replica_bootstrap.py::CheckReportReferenceNode.update",
        "vultron/core/behaviors/case/nodes/stub_invite_lifetime.py::ReinviteNotToClosedParticipantNode.update",
        "vultron/core/behaviors/case/nodes/update.py::BroadcastCaseUpdateNode.update",
        "vultron/core/behaviors/case/nodes/vfd_role_guards.py::CheckDeployerRoleNode.update",
        "vultron/core/behaviors/case/nodes/vfd_role_guards.py::CheckNotSoleObserverVfdNode.update",
        "vultron/core/behaviors/case/nodes/vfd_role_guards.py::CheckSomeVendorAtVFNode.update",
        "vultron/core/behaviors/case/nodes/vfd_role_guards.py::CheckVendorRoleNode.update",
        "vultron/core/behaviors/case_status_snapshot.py::EmitCaseStatusUpdateNode.update",
        "vultron/core/behaviors/embargo/end_time_tree.py::EmbargoEndTimePassedNode.update",
        "vultron/core/behaviors/embargo/nodes/abandon.py::ReadOpenEmbargoProposalsNode.update",
        "vultron/core/behaviors/embargo/nodes/activation_effect.py::ApplyEmbargoActivationFromLedgerNode.update",
        "vultron/core/behaviors/embargo/nodes/answer_record.py::EmbargoDecisionAppliesNode.update",
        "vultron/core/behaviors/embargo/nodes/conditions.py::HasActiveEmbargoNode.update",
        "vultron/core/behaviors/embargo/nodes/conditions.py::IsAnswerableEmbargoNode.update",
        "vultron/core/behaviors/embargo/nodes/conditions.py::LookupParticipantNode.update",
        "vultron/core/behaviors/embargo/nodes/em_state.py::ReadEmStateNode.update",
        "vultron/core/behaviors/embargo/nodes/emit.py::_SendEmbargoActivityBase.update",
        "vultron/core/behaviors/embargo/nodes/ending_notice_replica.py::ApplyAnnouncedEmbargoRevisionNode.update",
        "vultron/core/behaviors/embargo/nodes/expiry.py::EvaluateInviteExpiryNode.update",
        "vultron/core/behaviors/embargo/nodes/expiry_commit.py::_CommitConsentRowDecisionNode._fail",
        "vultron/core/behaviors/embargo/nodes/invite_answer.py::CanAnswerEmbargoInviteNode.update",
        "vultron/core/behaviors/embargo/nodes/invite_fault.py::EmitReceivedEmbargoFaultNode.update",
        "vultron/core/behaviors/embargo/nodes/lifecycle.py::_EmbargoLifecycleNode._decide",
        "vultron/core/behaviors/embargo/nodes/owner_decision.py::IsOpenEmbargoProposalNode.update",
        "vultron/core/behaviors/embargo/nodes/owner_decision.py::OwnerMayActivateEmbargoNode.update",
        "vultron/core/behaviors/embargo/nodes/proposal.py::RecordParticipantAcceptanceNode.update",
        "vultron/core/behaviors/embargo/nodes/proposal.py::RecordParticipantRejectionNode.update",
        "vultron/core/behaviors/embargo/nodes/pxa_refusal.py::ReceiverIsInviteeNode.update",
        "vultron/core/behaviors/embargo/nodes/pxa_refusal.py::RefusalFactoryAvailableNode.update",
        "vultron/core/behaviors/embargo/nodes/reinvite.py::ReinviteRefusedAccepterNode._invite_owed",
        "vultron/core/behaviors/embargo/nodes/reject_proposed.py::DecideRejectedEmbargoProposalNode.update",
        "vultron/core/behaviors/embargo/nodes/reject_proposed.py::OwnerRejectionAppliesNode.update",
        "vultron/core/behaviors/embargo/nodes/relay_effect.py::ApplyEmbargoInviteFromLedgerNode.update",
        "vultron/core/behaviors/embargo/nodes/relay_effect.py::_EmbargoRelayEffectNode._resolve",
        "vultron/core/behaviors/embargo/nodes/relay_effect.py::_EmbargoRelayEffectNode._store_embargo",
        "vultron/core/behaviors/embargo/nodes/relay_guards.py::EmStateAdmitsProposalNode.update",
        "vultron/core/behaviors/embargo/nodes/teardown.py::ApplyEmbargoTeardownNode.update",
        "vultron/core/behaviors/embargo/nodes/teardown.py::ClearActiveEmbargoNode.update",
        "vultron/core/behaviors/embargo/nodes/teardown.py::SendAnnounceEmbargoEventNode._on_factory_unavailable",
        "vultron/core/behaviors/embargo/nodes/teardown.py::SendAnnounceEmbargoEventNode._on_outbox_write_failure",
        "vultron/core/behaviors/embargo/nodes/teardown.py::SendAnnounceEmbargoEventNode._resolve_embargo_and_manager",
        "vultron/core/behaviors/embargo/nodes/teardown.py::TerminationIsTimelyNode.update",
        "vultron/core/behaviors/embargo/nodes/terminate.py::SendTerminateEmbargoActivityNode._on_factory_unavailable",
        "vultron/core/behaviors/embargo/nodes/terminate.py::SendTerminateEmbargoActivityNode._on_outbox_write_failure",
        "vultron/core/behaviors/embargo/nodes/termination_cause_guard.py::TerminationCauseIsAdmissibleNode.update",
        "vultron/core/behaviors/embargo/nodes/withdrawal.py::RecordParticipantWithdrawalNode.update",
        "vultron/core/behaviors/embargo/nodes/withdrawal.py::_EmbargoRefusalGuardNode.update",
        "vultron/core/behaviors/note/nodes/creation.py::AttachNoteFromResultNode.update",
        "vultron/core/behaviors/report/nodes/close_conditions.py::CheckReportClosable.update",
        "vultron/core/behaviors/report/nodes/develop_fix.py::_EmitParticipantStatusActivityBase.update",
        "vultron/core/behaviors/status/nodes/append/actions.py::AppendStatusAndSaveParticipantNode.update",
        "vultron/core/behaviors/status/nodes/append/actions.py::LoadParticipantNode.update",
        "vultron/core/behaviors/status/nodes/append/actions.py::ResolveAndPersistStatusObjectNode.update",
        "vultron/core/behaviors/status/nodes/append/conditions.py::CheckStatusNotAlreadyAppendedNode.update",
        "vultron/core/behaviors/status/nodes/case_status.py::CheckCaseStatusIdempotencyNode.update",
        "vultron/core/behaviors/status/nodes/case_status_acceptance.py::CheckCaseStatusAcceptableNode.update",
        "vultron/core/behaviors/status/nodes/cs_invariant_guards.py::CheckCsEphemeralStateNode.update",
        "vultron/core/behaviors/status/nodes/cs_invariant_guards.py::CheckCsHistoryPrefixNode.update",
        "vultron/core/behaviors/status/nodes/lifecycle.py::EmitCloseCaseNode.update",
        "vultron/core/behaviors/status/nodes/rm_declaration.py::AdjudicateRMDeclarationNode.update",
        "vultron/core/behaviors/status/nodes/rm_validation.py::ValidateRMTransitionNode.update",
        "vultron/core/behaviors/status/nodes/status_subject.py::CheckOnBehalfStatusShapeNode.update",
        "vultron/core/behaviors/sync/nodes/case_content_effect.py::_ApplyCaseContentFromLedgerNode.update",
        "vultron/core/behaviors/sync/nodes/case_status_effect.py::ApplyCaseStatusFromLedgerNode._reconstruct",
        "vultron/core/behaviors/sync/nodes/embargo_copy_effect.py::ApplyEmbargoChangeFromLedgerNode._refuse",
        "vultron/core/behaviors/sync/nodes/ledger_position.py::LedgerPositionAnswer.update",
        "vultron/core/behaviors/sync/nodes/ownership_effects.py::ApplyOwnershipTransferFromLedgerNode.update",
        "vultron/core/behaviors/sync/nodes/participant_status_effect.py::ApplyParticipantStatusFromLedgerNode.update",
    }
)


def _logs_feedback_at_warning(call: ast.Call) -> bool:
    """``<logger>.warning(..., <x>.feedback_message, ...)``."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "warning"
        and any(
            isinstance(arg, ast.Attribute) and arg.attr == "feedback_message"
            for arg in call.args
        )
    )


def _sites_in(tree: ast.AST, rel: str) -> set[str]:
    """``<rel>::<qualname>`` of every function holding such a call."""
    found: set[str] = set()

    def walk(node: ast.AST, scope: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(
                child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            ):
                walk(child, (*scope, child.name))
                continue
            if isinstance(child, ast.Call) and _logs_feedback_at_warning(
                child
            ):
                found.add(f"{rel}::{'.'.join(scope)}")
            walk(child, scope)

    walk(tree, ())
    return found


def _live_sites() -> set[str]:
    found: set[str] = set()
    for path, tree in _corpus.files_mentioning(
        "feedback_message", under=_BEHAVIORS
    ):
        rel = Path(path).relative_to(_corpus.REPO_ROOT).as_posix()
        found |= _sites_in(tree, rel)
    return found


@pytest.mark.spec("SL-03-003", "SL-03-001")
def test_no_new_node_logs_its_failure_reason_at_warning() -> None:
    new = sorted(_live_sites() - KNOWN_NODE_FEEDBACK_WARNINGS)
    assert new == [], (
        "A node logs its feedback_message at WARNING by hand (SL-03-003):"
        " fail through fail_with_reason for a refusal reason, or"
        " fail_with_fault for a fault (vultron/core/behaviors/"
        "node_logger.py):\n" + "\n".join(f"  {site}" for site in new)
    )


@pytest.mark.spec("SL-03-003")
def test_the_known_sites_only_shrink() -> None:
    gone = sorted(KNOWN_NODE_FEEDBACK_WARNINGS - _live_sites())
    assert gone == [], (
        "These sites no longer log their feedback at WARNING; remove them"
        " from KNOWN_NODE_FEEDBACK_WARNINGS (#6507):\n"
        + "\n".join(f"  {site}" for site in gone)
    )


def test_the_reading_finds_a_hand_written_site() -> None:
    """The detector is not vacuous: it sees the shape it ratchets."""
    tree = _corpus.parse_inline(
        "class N:\n"
        "    def update(self):\n"
        "        self.feedback_message = 'x'\n"
        "        self.logger.warning('%s: %s', self.name,"
        " self.feedback_message)\n"
        "    def ok(self):\n"
        "        self.logger.debug('%s', self.feedback_message)\n"
    )
    assert _sites_in(tree, "m.py") == {"m.py::N.update"}
