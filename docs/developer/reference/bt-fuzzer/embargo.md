---
stakeholder_type: [project-contributor]
---

# Embargo management fuzzer nodes

These stub nodes belong to `EmbargoManagementBt` and its sub-trees (`TerminateEmbargoBt`, `_ConsiderTerminatingActiveEmbargo`, `_ProposeEmbargoBt`, `_ChooseEmProposedResponse`) in `vultron/bt/embargo_management/behaviors.py`.
They model the negotiation, evaluation, and lifecycle management of coordinated disclosure embargoes.

{% include-markdown "./_index_pointer.md" %}

## `ExitEmbargoWhenDeployed`

- **Node name**: `ExitEmbargoWhenDeployed`
- **btz type**: `ProbablyFail` (p=0.33)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenDeployed` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a deployed fix is sufficient reason to exit an active embargo
- **Input dependency**: Human or policy judgment.
  A deployment event plus the site policy on embargo continuation after deployment
- **Notes**: Modeled as unlikely because deployment alone is usually not sufficient.
  Examples are a partial rollout or an emergency deployment
- **Automation potential**: **Medium** — patch-management or case-state application programming interfaces (APIs) can automate the deployment status check.
  The *decision* to exit still needs a policy-rule evaluation or a human confirmation.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.ExitEmbargoWhenDeployed`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`exit_embargo_when_deployed_factory` param) — condition guard in the ReasonSelector.
  The tree checks it before it delegates to `terminate_embargo_bt`.
  The same bundle slot also feeds the `create_manage_embargo_tree` stub Sequence
- **Termination cause**: On SUCCESS, the `ChooseTerminationCauseNode` that follows it sets the cause of the termination to `FIX_DEPLOYED`.
  The `Remove(EmbargoEvent)` and the `TERMINATED` register entry carry this cause (EMB-14-001, EMB-14-004, EMB-13-004)

## `ExitEmbargoWhenFixReady`

- **Node name**: `ExitEmbargoWhenFixReady`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenFixReady` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a ready (but not yet deployed) fix is sufficient reason to exit the embargo
- **Input dependency**: Human or policy judgment.
  Fix-readiness status plus organizational policy
- **Notes**: Less common than an exit that deployment triggers.
  The vendor might first want to coordinate a simultaneous deployment across the affected population
- **Automation potential**: **Medium** — an automatic query can read the fix-readiness flag.
  The exit decision depends on configurable organizational policy, which can need a human override.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.ExitEmbargoWhenFixReady`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`exit_embargo_when_fix_ready_factory` param) — condition guard in the ReasonSelector.
  The tree checks it before it delegates to `terminate_embargo_bt`.
  The same bundle slot also feeds the `create_manage_embargo_tree` stub Sequence
- **Termination cause**: On SUCCESS, the `ChooseTerminationCauseNode` that follows it sets the cause of the termination to `FIX_READY`.
  The cause names the vendors of the case whose fix is ready.
  The `Remove(EmbargoEvent)` and the `TERMINATED` register entry carry this cause (EMB-14-001, EMB-14-004, EMB-13-004).
  When no vendor has a ready fix, that node fails, and the ReasonSelector tries the next reason.

## `ExitEmbargoForOtherReason`

- **Node name**: `ExitEmbargoForOtherReason`
- **btz type**: `OneInTwoHundred` (p=0.005)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_OtherReasonToExitEmbargo` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition — catch-all for exiting an embargo for reasons other than fix readiness, deployment, timer expiry, public awareness, known exploits, or observed attacks
- **Input dependency**: Human judgment.
  A rare edge-case policy decision
- **Notes**: Intentionally very rare in simulation.
  It represents extraordinary circumstances
- **Automation potential**: **Low** — rare edge case that represents extraordinary circumstances.
  It fundamentally needs human judgment that no general policy rule can anticipate.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.ExitEmbargoForOtherReason`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`exit_embargo_for_other_reason_factory` param) — rare fallback condition guard in the ReasonSelector for extraordinary circumstances.
  The same bundle slot also feeds the `create_manage_embargo_tree` stub Sequence
- **Termination cause**: On SUCCESS, the `ChooseTerminationCauseNode` that follows it sets the cause of the termination to `OTHER`.
  The `Remove(EmbargoEvent)` and the `TERMINATED` register entry carry this cause (EMB-14-001, EMB-14-004, EMB-13-004)

## `EmbargoTimerExpired`

- **Node name**: `EmbargoTimerExpired`
- **btz type**: `OneInOneHundred` (p=0.01)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_SufficientCauseToTerminateActiveEmbargo` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition — check whether the agreed deadline of the embargo has passed
- **Input dependency**: System clock compared to the embargo expiry timestamp recorded in the case.
  Full automation is possible
- **Notes**: Rare in simulation, because most ticks occur well before expiry.
  In production, this node is a simple timestamp comparison
- **Automation potential**: **High** — simple system-clock comparison against the recorded embargo expiry timestamp.
  Full automation is possible, with no human involvement.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.EmbargoTimerExpired`
- **Call-out point shape**: Retriever — on-demand synchronous check.
  It reads the embargo expiry timestamp from the case DataLayer and compares it to the current system clock.
  It returns SUCCESS/FAILURE with no output keys.
  The behavior tree (BT) tick drives this node.
  The node does not run independently or fire a trigger endpoint.
  A timestamp comparison is the simplest kind of structured fact (ADR-0024, BT-18-006: binary on-demand queries are Retrievers, not Sentinels).
- **Factory-fn placement**: Not placed in a production factory.
  `create_terminate_active_embargo_tree` models actor-chosen exit reasons only.
  `vultron.core.behaviors.embargo.expiry_tree` handles invite-deadline expiry.

## `OnEmbargoExit`

- **Node name**: `OnEmbargoExit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderTerminatingActiveEmbargo`
- **Semantic function**: Action — do any site-specific tasks that are necessary when the actor leaves an active embargo (notifications, logging, downstream triggers)
- **Input dependency**: Site-specific integration hook.
  It can call notification APIs or start case management system updates, among other tasks.
- **Notes**: Always succeeds in simulation.
  A production implementation must make sure that execution is idempotent
- **Automation potential**: **High** — integration hook (notifications, state updates, downstream triggers).
  API calls to notification and case-management systems can fully automate it.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.OnEmbargoExit`
- **Call-out point shape**: Actuator — fires integration hooks on embargo exit.
  It makes notification API calls, case-management state-write calls, and downstream trigger endpoint calls.
  The seam is the side effects in external systems, not a content artifact on the blackboard.
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`on_embargo_exit_factory` param) — Actuator effect node in the `TerminateActiveEmbargoBT` Sequence.
  It comes after the AuthorizeEmbargoExit Selector and before `terminate_embargo_bt`

## `EmbargoExitPolicyGuard`

- **Node name**: `EmbargoExitPolicyGuard`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vultron/demo/fuzzer/embargo.py`
- **Parent tree**: `AuthorizeEmbargoExit` (within `create_terminate_active_embargo_tree`)
- **Semantic function**: Condition — after the tree selects a reason, check whether site policy permits the actor to continue with voluntary embargo termination.
  Example checks are that no revision negotiation is active and that no approvals are pending
- **Input dependency**: Automated policy evaluation.
  Integration with case-management or approval-workflow systems
- **Notes**: Always succeeds in simulation, because the happy path assumes that policy permits the termination.
  In production, the node can call an approval queue or a rule engine
- **Automation potential**: **High** — case-management API calls can fully automate the rule-based checks (pending revision, approval status).
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.EmbargoExitPolicyGuard`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`embargo_exit_policy_guard_factory` param) — first arm of the AuthorizeEmbargoExit Selector.
  It comes after the ReasonSelector succeeds and before OnEmbargoExit

## `EmbargoExitOverride`

- **Node name**: `EmbargoExitOverride`
- **btz type**: `AlwaysFail` (p=0.00)
- **Source file**: `vultron/demo/fuzzer/embargo.py`
- **Parent tree**: `AuthorizeEmbargoExit` (within `create_terminate_active_embargo_tree`)
- **Semantic function**: Condition — the actor explicitly accepts responsibility to override a policy veto and continue with voluntary embargo termination.
  The node makes a distinct audit-trail entry for the override
- **Input dependency**: Explicit actor acknowledgment.
  The node can call an escalation endpoint or a confirmation dialog
- **Notes**: Always fails in simulation, because the override is not active by default.
  In production, an integrator connects this node to an escalation acknowledgment mechanism.
  The override is logged separately from the normal policy path
- **Automation potential**: **Low** — for accountability, the override needs an explicit actor acknowledgment.
  It should not be approved automatically.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.EmbargoExitOverride`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.terminate_active_embargo_tree.create_terminate_active_embargo_tree` (`embargo_exit_override_factory` param) — second (fallback) arm of the AuthorizeEmbargoExit Selector.
  The tree reaches it only when EmbargoExitPolicyGuard returns FAILURE

## `StopProposingEmbargo`

- **Node name**: `StopProposingEmbargo`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderAbandoningProposedEmbargo` (within `_ProposeEmbargoBt`)
- **Semantic function**: Condition — human or policy decision to abandon the negotiation of an embargo.
  Example causes are too many counter-proposals or time pressure
- **Input dependency**: Human judgment or policy-driven escalation trigger
- **Notes**: Modeled as uncommon, because parties are usually willing to continue the negotiation
- **Automation potential**: **Low** — fundamentally a negotiation-fatigue judgment.
  It depends on the relationship context and on a subjective assessment of the negotiation prospects.
  It needs a human decision.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.StopProposingEmbargo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Simulator-only.
  It gates the tick-based "keep proposing until effort is exhausted" loop of the simulator (`_EnsureSufficientEffortToAchieveEmbargo`).
  This loop has no event trigger in the prototype.
  The `stop_proposing_embargo_factory` slot feeds only the `create_manage_embargo_tree` stub Sequence.

## `SelectEmbargoOfferTerms`

- **Node name**: `SelectEmbargoOfferTerms`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ProposeNewEmbargo` and `_ProposeEmbargoRevision` (within `_ProposeEmbargoBt`)
- **Semantic function**: Action — choose the specific terms (duration, conditions) for an embargo proposal or counter-proposal
- **Input dependency**: Human decision or policy-driven term selection.
  Organizational policy templates could automate the selection
- **Notes**: Always succeeds in simulation.
  In production, the node can use negotiation-support tools or a policy lookup
- **Automation potential**: **Medium** — organizational policy templates can automatically supply standard terms (duration, conditions).
  Atypical situations can need human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.SelectEmbargoOfferTerms`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Outbound propose flow: the term-selection seam that supplies proposal terms before the propose trigger use case (`SvcProposeEmbargoUseCase` → `propose_embargo_trigger_bt`).
  The EMB-15-003 counter arm also uses this seam (counter = re-propose).
  Today the `select_embargo_offer_terms_factory` slot feeds only the `create_manage_embargo_tree` stub Sequence.

## `WantToProposeEmbargo`

- **Node name**: `WantToProposeEmbargo`
- **btz type**: `RandomSucceedFail` / `UniformSucceedFail` (p=0.50)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderProposingEmbargo` (within `_EmNone`)
- **Semantic function**: Condition — does the participant want to start an embargo negotiation now?
- **Input dependency**: Human or automated policy decision.
  It depends on case context, role, and organizational policy
- **Notes**: The default recommendation is to propose an embargo.
  The fuzzer exercises both paths equally
- **Automation potential**: **Medium** — the default policy (always propose) can be automated.
  Rules could encode the exceptions, such as an already-public vulnerability or no identified vendor.
  But edge cases can need a human override.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.WantToProposeEmbargo`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Outbound propose flow: the operator or policy decision to invoke `SvcProposeEmbargoUseCase` at all.
  This decision is a gate on the trigger, not a node in a decision tree.
  Today the `want_to_propose_embargo_factory` slot feeds only the `create_manage_embargo_tree` stub Sequence.

## `WillingToCounterEmbargoProposal`

- **Node name**: `WillingToCounterEmbargoProposal`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidCounterProposal` (within `_EmProposed`)
- **Semantic function**: Condition — is the participant willing to answer an incoming embargo proposal with a counter-proposal, instead of accepting or rejecting it outright?
- **Input dependency**: Human judgment or policy.
  Countering is generally discouraged in favor of accepting and then proposing a revision
- **Notes**: Intentionally low probability.
  The recommended behavior is to accept the current proposal and negotiate revisions separately
- **Automation potential**: **Low** — nuanced negotiation judgment about whether countering is strategically better than accepting and revising.
  It is best left to human discretion.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.WillingToCounterEmbargoProposal`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.response_decision_tree.create_embargo_response_decision_tree` (`willing_to_counter_factory` param) — gates the counter arm of the inbound embargo-response decision seam (EMB-15-003), Flow A only.
  Its DETERMINISTIC default is FAILURE, because accept-then-revise is preferred.
  On SUCCESS, the arm delegates to `propose_embargo_trigger_bt`.

## `ReasonToProposeEmbargoWhenDeployed`

- **Node name**: `ReasonToProposeEmbargoWhenDeployed`
- **btz type**: `AlmostCertainlyFail` (p=0.07)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidNewEmbargoesInCsDeployedUnlessReason`
- **Semantic function**: Condition — is there an unusual reason to start a new embargo negotiation, even though the fix is already deployed?
- **Input dependency**: Human judgment.
  An exceptional circumstance that needs an explicit decision
- **Notes**: Very rare by design.
  Embargo proposals after deployment are exceptional
- **Automation potential**: **Low** — highly exceptional circumstance.
  No general rule can anticipate valid reasons, so human judgment is necessary.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.ReasonToProposeEmbargoWhenDeployed`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: Outbound propose flow: an exceptional-case precondition on invoking `SvcProposeEmbargoUseCase` after fix deployment (CS `···D··`).
  Today the `reason_to_propose_when_deployed_factory` slot feeds only the `create_manage_embargo_tree` stub Sequence.

## `EvaluateEmbargoProposal`

- **Node name**: `EvaluateEmbargoProposal`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo` (within `_ChooseEmProposedResponse`)
- **Semantic function**: Condition/action — assess an incoming embargo proposal and decide whether to accept it
- **Input dependency**: Human analyst review, or an automated policy compatibility check that compares the proposed terms against organizational policy
- **Notes**: Modeled as usually successful, because acceptance is the common outcome.
  In production, the node can use structured negotiation support
- **Automation potential**: **Medium** — a basic compatibility check (is the proposed duration within policy bounds?) can be automated.
  The final accept/reject decision for out-of-range proposals usually needs human review.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.EvaluateEmbargoProposal`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: `vultron.core.behaviors.embargo.response_decision_tree.create_embargo_response_decision_tree` (`evaluate_embargo_proposal_factory` param) — the default-accept Evaluator of the inbound embargo-response decision seam (EMB-15-001).
  It sits behind the CASE_OWNER-bypass authorization Selector (EMB-15-002).
  On SUCCESS, it delegates to the flow-appropriate accept BT (`accept_embargo_trigger_bt` for a Flow A proposal, `accept_invite_to_embargo_tree` for a Flow B invitation).

## `OnEmbargoAccept`

- **Node name**: `OnEmbargoAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo`
- **Semantic function**: Action — do the site-specific tasks that the acceptance of an embargo proposal triggers.
  Examples are to notify Participants, record the agreement, and start the embargo timer
- **Input dependency**: Integration hook.
  It can call notification APIs and calendar/timer services, and it can start case management system updates
- **Notes**: Always succeeds in simulation.
  It must be idempotent in production
- **Automation potential**: **High** — API integrations can automate all the notification dispatch, timer initialization, and state-update actions.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.OnEmbargoAccept`
- **Call-out point shape**: Actuator — fires integration hooks on embargo acceptance.
  It makes notification API calls, embargo timer-service initialization calls, and case-management state writes.
  The seam is the side effects in external systems, not a content artifact on the blackboard.
- **Factory-fn placement**: Not wired yet: the `on_embargo_accept_factory` slot exists in `EmbargoCallOutBundle`, and `create_manage_embargo_tree` reserves it for the accept arm.

## `OnEmbargoReject`

- **Node name**: `OnEmbargoReject`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_RejectProposedEmbargo` (within `_ChooseEmProposedResponse`)
- **Semantic function**: Action — do the site-specific tasks that the rejection of an embargo proposal triggers.
  Examples are to notify Participants and to log the rejection rationale
- **Input dependency**: Integration hook.
  Notification APIs and case management updates
- **Notes**: Always succeeds in simulation.
  It must be idempotent in production
- **Automation potential**: **High** — APIs can fully automate the notification dispatch and logging actions.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.OnEmbargoReject`
- **Call-out point shape**: Actuator — fires integration hooks on embargo rejection.
  It makes notification API calls and case-management state writes for the rejection rationale.
  The seam is the side effects in external systems, not a content artifact on the blackboard.
- **Factory-fn placement**: Not wired yet: the `on_embargo_reject_factory` slot exists in `EmbargoCallOutBundle`, and `create_manage_embargo_tree` reserves it for the reject arm (EMB-15-004, EMB-15-008).

## `CaseOwnerApprovesEmbargoResponse`

- **Node name**: `CaseOwnerApprovesEmbargoResponse`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `vultron/demo/fuzzer/embargo.py`
- **Parent tree**: `AuthorizeSelector` (within `create_embargo_response_decision_tree`).
  It is the second child of the `AuthorizeSelector` Selector, and the tree reaches it only when the deciding actor is NOT a `CVDRole.CASE_OWNER`
- **Semantic function**: Condition — a non-CASE_OWNER actor asks the case owner for authorization before it accepts or counters.
  An example is the CASE_MANAGER when it processes an inbound overture on behalf of the owner.
  Defaults to approval in simulation, because the simulation assumes owner approval.
- **Input dependency**: Human approval / adjudication.
  Final authority rests with the case owner (a human or a configured policy agent)
- **Notes**: Gate only.
  The node places no content artifact on the blackboard.
  In production, an Evaluator-type Coordination Agent would fulfill this seam and return the decision of the owner.
  This agent can be a user interface (UI) prompt, a large language model (LLM) adjudicator, or a policy rule.
- **Automation potential**: **Low** — final authority rests with the case owner.
  By default, automatic approval is not possible.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.CaseOwnerApprovesEmbargoResponse`
- **Call-out point shape**: Evaluator — records an adjudication decision (approve/deny).
  It has no blackboard output_keys, because it is only a pass/fail gate (BT-18-006).
- **Factory-fn placement**: `vultron.core.behaviors.embargo.response_decision_tree.create_embargo_response_decision_tree` (`case_owner_approves_embargo_response_factory` param) — second child of the `AuthorizeSelector`.
  The tree reaches it when `SenderIsCaseOwnerNode` returns FAILURE (EMB-15-002).

## `CurrentEmbargoAcceptable`

- **Node name**: `CurrentEmbargoAcceptable`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ChooseEmActiveResponse` (within `_EmActive`)
- **Semantic function**: Condition — is the participant satisfied with the terms of the current active embargo, or does the participant want to propose a revision?
- **Input dependency**: Human judgment, or an automated policy check that compares the current embargo terms against organizational preferences
- **Notes**: Modeled as usually acceptable.
  Revision proposals are relatively uncommon
- **Automation potential**: **Medium** — an automated comparison of the current terms against policy preferences is possible.
  Edge cases and dynamic negotiation contexts can still need human judgment.
- **New-arch cross-ref**: `vultron.demo.fuzzer.embargo.CurrentEmbargoAcceptable`
- **Call-out point shape**: Evaluator
- **Factory-fn placement**: A continuous-monitoring evaluator with no inbound-message trigger.
  So it belongs to active-embargo monitoring under epic #1147, not to the EMB-15 response seam.
  Today the `current_embargo_acceptable_factory` slot feeds only the `create_manage_embargo_tree` stub Sequence.
