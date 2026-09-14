---
title: CM-23-011 decline must also suppress the CLP-10-006 receipt commit
type: learning
timestamp: 2026-09-14T00:00:00Z
source: ISSUE-3137
signal: spec-gap
---

CM-23-011 states that declining an owner `Leave(VulnerabilityCase)` while an
embargo is live MUST NOT execute the CM-23-002 closure sequence — "no
participant advances to `RM.CLOSED`; no `case_fully_closed` entry is emitted."
It enumerates the RM/ledger effects to skip but says nothing about the
CLP-10-006 *receipt* commit that the received-activity tree performs before any
role-specific effects.

On the close-case receive path that receipt commit is not neutral: it commits a
`close_case` `CaseLedgerEntry` and fans it out, and each replica's
`ApplyCloseCaseFromLedgerNode` then advances the departing participant to
`RM.CLOSED` (CLP-10-001, CM-23-003). So honoring CM-23-011's stated constraint
("no participant advances to `RM.CLOSED`") on the *replicas* is impossible
unless the decline also suppresses the receipt commit itself — a step the spec
never names. A straightforward reading that only skips the local RM effects
(the literal CM-23-002 steps) still closes the case everywhere via fan-out.

The implementation resolves this by gating the entire receive-and-commit path
behind the decline decision, so a declined owner-close records nothing to the
ledger. Worth making explicit in `specs/case-management.yaml`: CM-23-011 (or a
CLP-10 cross-reference) should state that a declined close records no `close_case`
receipt entry at all, not merely that it skips the RM.CLOSED advances — because
the receipt entry is the closure mechanism, not a separate bookkeeping record.
