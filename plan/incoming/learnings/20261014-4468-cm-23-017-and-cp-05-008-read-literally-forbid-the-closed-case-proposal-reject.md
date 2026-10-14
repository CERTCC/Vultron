---
title: "CM-23-017 and CP-05-008, read literally, forbid the closed-case proposal Reject that CP-05-006 and CP-05-008 require"
type: learning
timestamp: "2026-10-14T22:30:00Z"
source: ISSUE-4468
signal: spec-ambiguity
---

**Trigger.** You change how the CASE_MANAGER answers a `Create(CaseProposal)`
that resolves to a fully closed case, or you change what CM-23-017 lets the
CASE_MANAGER send after `case_fully_closed`.

**Claim.** Two spec statements contradict the closed-case decline when read
literally, and only an ADR scoping sentence reconciles them:

- CM-23-017 says every late activity other than a Leave "MUST be dropped with
  no reply under both settings". CP-05-006 and CP-05-008 require a
  `Reject(CaseProposal)`. ADR-0131 resolves this: a proposal names a report, not
  a case. That carve-out is not in the CM-23-017 statement.
- CP-05-008 says a new proposal "MUST be subject to the admission decision
  (CP-05-002)". The reference tree declines a closed-case proposal before the
  `EvaluateCaseProposal` call-out runs, because closure forces a `Reject`
  either way. The statement does not say whether closure is part of the
  admission decision or comes before it.

**Evidence.** PR #4665 (#4468) implements the decline ahead of the call-out
point. Its pre-PR spec review flagged both readings.

**How to apply.** When `learn` processes this, decide whether CM-23-017 needs
the proposal carve-out written into its statement, and whether CP-05-008 should
say that closure is checked before the admission call-out point.
