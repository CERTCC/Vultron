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
literally. ADR-0131 and two non-normative spec notes reconcile them, but the
statements themselves do not:

- CM-23-017 says every late activity other than a Leave "MUST be dropped with
  no reply under both settings". CP-05-006 and CP-05-008 require a
  `Reject(CaseProposal)`. ADR-0131 resolves this: a proposal names a report, not
  a case. PR #4665 added that carve-out to the CM-23-017 `note`, not its
  statement.
- CP-05-008 says a new proposal "MUST be subject to the admission decision
  (CP-05-002)". The reference tree declines a closed-case proposal before the
  `EvaluateCaseProposal` call-out runs, because closure forces a `Reject`
  either way. PR #4665 added to the CP-05-008 `note` that closure is part of
  the admission decision; the statement does not say so.

**Evidence.** PR #4665 (#4468) implements the decline ahead of the call-out
point. Its pre-PR spec review flagged both readings.

**How to apply.** When `learn` processes this, decide whether the two notes are
enough, or whether the CM-23-017 statement needs the proposal carve-out and the
CP-05-008 statement needs the closure-first order. A statement change alters
what a MUST obliges, so it needs a human decision.

**Already closed**: 2026-10-30 — #5378 makes the CP-05-008 statement fix
(maintainer-decided); the CM-23-017 carve-out was added to its scope (comment on #5378).
Docs PR: <https://github.com/CERTCC/Vultron/pull/5581>.
