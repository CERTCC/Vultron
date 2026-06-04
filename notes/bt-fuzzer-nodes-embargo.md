---
title: "BT Fuzzer Nodes: Embargo Management"
status: active
description: >
  Catalog of fuzzer (stub) BT nodes for the Embargo Management workflow in
  the Vultron BT simulation.
related_specs:
  - specs/behavior-tree-integration.yaml
related_notes:
  - notes/bt-integration.md
  - notes/bt-fuzzer-nodes.md
relevant_packages:
  - vultron/bt/embargo_management
---

# BT Fuzzer Nodes: Embargo Management

These are the stub nodes for `EmbargoManagementBt` and its sub-trees
(`TerminateEmbargoBt`, `_ProposeEmbargoBt`, etc.) in
`vultron/bt/embargo_management/behaviors.py`. See
`notes/bt-fuzzer-nodes.md` for background on what fuzzer nodes are and
the full catalog index.

**Fuzzer base types quick reference:**

| btz type | Success probability |
|---|---|
| `AlwaysSucceed` | 1.00 |
| `AlmostCertainlySucceed` | 0.93 |
| `AlmostAlwaysSucceed` | 0.90 |
| `UsuallySucceed` | 0.75 |
| `OftenSucceed` / `LikelySucceed` | 0.70 |
| `ProbablySucceed` | 0.67 |
| `UniformSucceedFail` / `RandomSucceedFail` | 0.50 |
| `SuccessOrRunning` | 0.50 (never fails; returns SUCCESS or RUNNING) |
| `ProbablyFail` | 0.33 |
| `OftenFail` | 0.30 |
| `UsuallyFail` | 0.25 |
| `AlmostAlwaysFail` / `RarelySucceed` | 0.10 |
| `AlmostCertainlyFail` | 0.07 |
| `OneInTwenty` | 0.05 |
| `OneInOneHundred` | 0.01 |
| `OneInTwoHundred` | 0.005 |
| `AlwaysFail` | 0.00 |

---

## Embargo Management

These nodes belong to `EmbargoManagementBt` and its sub-trees
(`TerminateEmbargoBt`, `_ConsiderTerminatingActiveEmbargo`,
`_ProposeEmbargoBt`, `_ChooseEmProposedResponse`, etc.) in
`vultron/bt/embargo_management/behaviors.py`. They model the negotiation,
evaluation, and lifecycle management of coordinated disclosure embargoes.

### `ExitEmbargoWhenDeployed`

- **Node name**: `ExitEmbargoWhenDeployed`
- **btz type**: `ProbablyFail` (p=0.33)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenDeployed` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a deployed fix is
  sufficient reason to exit an active embargo
- **Input dependency**: Human or policy judgment; deployment event plus
  site policy on post-deployment embargo continuation
- **Notes**: Modeled as unlikely because deployment alone is usually
  insufficient (e.g., partial rollout, emergency deployment)
- **Automation potential**: **Medium** — deployment status check is automatable via patch-management or case-state APIs; the *decision* to exit still requires policy-rule evaluation or human confirmation.

### `ExitEmbargoWhenFixReady`

- **Node name**: `ExitEmbargoWhenFixReady`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_MaybeExitWhenFixReady` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition/action — decide whether a ready (but not
  yet deployed) fix is sufficient reason to exit the embargo
- **Input dependency**: Human or policy judgment; fix-readiness status plus
  organizational policy
- **Notes**: Less common than deployment-triggered exit; vendor may want to
  coordinate simultaneous deployment across affected population first
- **Automation potential**: **Medium** — fix-readiness flag is queryable automatically; the exit decision depends on configurable organizational policy that may require human override.

### `ExitEmbargoForOtherReason`

- **Node name**: `ExitEmbargoForOtherReason`
- **btz type**: `OneInTwoHundred` (p=0.005)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_OtherReasonToExitEmbargo` (within `TerminateEmbargoBt`)
- **Semantic function**: Condition — catch-all for exiting an embargo for
  reasons other than fix readiness, deployment, timer expiry, public
  awareness, known exploits, or observed attacks
- **Input dependency**: Human judgment; rare edge-case policy decision
- **Notes**: Intentionally very rare in simulation; represents extraordinary
  circumstances
- **Automation potential**: **Low** — rare edge case representing extraordinary circumstances; fundamentally requires human judgment that cannot be anticipated by a general policy rule.

### `EmbargoTimerExpired`

- **Node name**: `EmbargoTimerExpired`
- **btz type**: `OneInOneHundred` (p=0.01)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_SufficientCauseToTerminateActiveEmbargo` (within
  `TerminateEmbargoBt`)
- **Semantic function**: Condition — check whether the embargo's agreed-upon
  deadline has passed
- **Input dependency**: System clock compared to the embargo expiry
  timestamp recorded in the case; fully automatable
- **Notes**: Rare in simulation (most ticks occur well before expiry); in
  production this is a simple timestamp comparison
- **Automation potential**: **High** — simple system-clock comparison against the recorded embargo expiry timestamp; fully automatable with no human involvement.

### `OnEmbargoExit`

- **Node name**: `OnEmbargoExit`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderTerminatingActiveEmbargo`
- **Semantic function**: Action — execute any site-specific tasks required
  when leaving an active embargo (notifications, logging, downstream
  triggers)
- **Input dependency**: Site-specific integration hook; may invoke
  notification APIs, case management system updates, etc.
- **Notes**: Always succeeds in simulation; production implementation
  must ensure idempotent execution
- **Automation potential**: **High** — integration hook (notifications, state updates, downstream triggers); can be fully automated via API calls to notification and case-management systems.

### `StopProposingEmbargo`

- **Node name**: `StopProposingEmbargo`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderAbandoningProposedEmbargo` (within
  `_ProposeEmbargoBt`)
- **Semantic function**: Condition — human or policy decision to give up on
  negotiating an embargo (e.g., too many counter-proposals, time pressure)
- **Input dependency**: Human judgment or policy-driven escalation trigger
- **Notes**: Modeled as uncommon; parties are usually willing to keep
  negotiating
- **Automation potential**: **Low** — fundamentally a negotiation-fatigue judgment; depends on relationship context and subjective assessment of negotiation prospects; requires human decision.

### `SelectEmbargoOfferTerms`

- **Node name**: `SelectEmbargoOfferTerms`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ProposeNewEmbargo` and `_ProposeEmbargoRevision`
  (within `_ProposeEmbargoBt`)
- **Semantic function**: Action — choose the specific terms (duration,
  conditions) to include in an embargo proposal or counter-proposal
- **Input dependency**: Human decision or policy-driven term selection;
  could be automated from organizational policy templates
- **Notes**: Always succeeds in simulation; in production may involve
  negotiation-support tooling or policy lookup
- **Automation potential**: **Medium** — standard terms (duration, conditions) can be drawn from organizational policy templates automatically; atypical situations may need human review.

### `WantToProposeEmbargo`

- **Node name**: `WantToProposeEmbargo`
- **btz type**: `RandomSucceedFail` / `UniformSucceedFail` (p=0.50)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ConsiderProposingEmbargo` (within `_EmNone`)
- **Semantic function**: Condition — does the participant currently wish to
  initiate an embargo negotiation?
- **Input dependency**: Human or automated policy decision; depends on case
  context, role, and organizational policy
- **Notes**: Default recommendation is to propose an embargo; fuzzer
  exercises both paths equally
- **Automation potential**: **Medium** — default policy (always propose) can be automated; exceptions (e.g., already-public vulnerability, no vendor identified) could be rule-encoded, but edge cases may need human override.

### `WillingToCounterEmbargoProposal`

- **Node name**: `WillingToCounterEmbargoProposal`
- **btz type**: `UsuallyFail` (p=0.25)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidCounterProposal` (within `_EmProposed`)
- **Semantic function**: Condition — is the participant willing to respond
  to an incoming embargo proposal with a counter-proposal rather than
  accepting or rejecting it outright?
- **Input dependency**: Human judgment or policy; generally discouraged in
  favor of accepting and then proposing a revision
- **Notes**: Intentionally low probability; the recommended behavior is to
  accept the current proposal and negotiate revisions separately
- **Automation potential**: **Low** — nuanced negotiation judgment about whether countering is strategically preferable to accepting and revising; best left to human discretion.

### `ReasonToProposeEmbargoWhenDeployed`

- **Node name**: `ReasonToProposeEmbargoWhenDeployed`
- **btz type**: `AlmostCertainlyFail` (p=0.07)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_AvoidNewEmbargoesInCsDeployedUnlessReason`
- **Semantic function**: Condition — is there an unusual reason to start a
  new embargo negotiation even though the fix has already been deployed?
- **Input dependency**: Human judgment; exceptional circumstance requiring
  explicit decision
- **Notes**: Very rare by design; post-deployment embargo proposals are
  exceptional
- **Automation potential**: **Low** — highly exceptional circumstance; no general rule can anticipate valid reasons, so human judgment is required.

### `EvaluateEmbargoProposal`

- **Node name**: `EvaluateEmbargoProposal`
- **btz type**: `UsuallySucceed` (p=0.75)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo` (within
  `_ChooseEmProposedResponse`)
- **Semantic function**: Condition/action — assess an incoming embargo
  proposal and decide whether to accept it
- **Input dependency**: Human analyst review, or an automated policy
  compatibility check comparing proposed terms against organizational policy
- **Notes**: Modeled as usually succeeding (acceptance is the common
  outcome); in production may involve structured negotiation support
- **Automation potential**: **Medium** — basic compatibility check (is proposed duration within policy bounds?) is automatable; final accept/reject for out-of-range proposals typically needs human review.

### `OnEmbargoAccept`

- **Node name**: `OnEmbargoAccept`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_EvaluateAndAcceptProposedEmbargo`
- **Semantic function**: Action — execute site-specific tasks triggered when
  an embargo proposal is accepted (e.g., notify stakeholders, record
  agreement, start embargo timer)
- **Input dependency**: Integration hook; may invoke notification APIs,
  calendar/timer services, case management system updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — notification dispatch, timer initialization, and state-update actions are all integration-automatable via APIs.

### `OnEmbargoReject`

- **Node name**: `OnEmbargoReject`
- **btz type**: `AlwaysSucceed` (p=1.00)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_RejectProposedEmbargo` (within `_ChooseEmProposedResponse`)
- **Semantic function**: Action — execute site-specific tasks triggered when
  an embargo proposal is rejected (e.g., notify stakeholders, log rejection
  rationale)
- **Input dependency**: Integration hook; notification APIs and case
  management updates
- **Notes**: Always succeeds in simulation; must be idempotent in production
- **Automation potential**: **High** — notification dispatch and logging actions are fully automatable via APIs.

### `CurrentEmbargoAcceptable`

- **Node name**: `CurrentEmbargoAcceptable`
- **btz type**: `AlmostAlwaysSucceed` (p=0.90)
- **Source file**: `embargo_management/fuzzer.py`
- **Parent tree**: `_ChooseEmActiveResponse` (within `_EmActive`)
- **Semantic function**: Condition — is the participant satisfied with the
  current active embargo terms, or do they wish to propose a revision?
- **Input dependency**: Human judgment or automated policy check comparing
  current embargo terms against organizational preferences
- **Notes**: Modeled as usually acceptable; revision proposals are
  relatively uncommon
- **Automation potential**: **Medium** — automated comparison of current terms against policy preferences is feasible; edge cases and dynamic negotiation contexts may still require human judgment.

---
