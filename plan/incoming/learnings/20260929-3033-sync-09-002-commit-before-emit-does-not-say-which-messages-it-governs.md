---
title: "SYNC-09-002 says every external message follows its ledger commit, while CM-14-011 puts the bootstrap Create before the commit — the corpus never says which messages 'associated' covers"
type: learning
timestamp: "2026-09-29T17:30:00Z"
source: ISSUE-3033
signal: spec-ambiguity
---

SYNC-09-002 reads: "External Vultron messages (activities sent to Participant
Actors or other protocol participants) MUST only be emitted after the associated
`CaseLedgerEntry` is committed." CM-14-011 puts step 4, "queue a `Create(Case)`
activity ... and flush the outbox", *before* step 6, "commit a case ledger entry,
triggering `Announce(CaseLedgerEntry)` fan-out", and CM-14-001 forbids reordering
the steps. Both are MUSTs; both are `kind: protocol`; neither cites the other.

The CaseProposal accept tree resolved the tension the SYNC-09-002 way — commit
first, emit after — and that ordering was the direct cause of the #3033 / #2898
flakes: the ledger fan-out queued ahead of `Create(VulnerabilityCase)` put every
recipient into the SYNC-15 pre-genesis reject/replay path on the normal route.
The fix (PR #3883) follows CM-14-011 and records the reconciliation only in
CP-09-009's rationale: the bootstrap `Create` is the CBT-01 trust handoff, not a
message *about* a ledger event, so "associated `CaseLedgerEntry`" in SYNC-09-002
is read as the entry an `Announce(CaseLedgerEntry)` carries, which still follows
its commit.

That reading lives in one rationale field. SYNC-09-002's own statement still says
"external messages", unqualified, and a future implementer of any other
case-seeding or bootstrap message (`Announce(VulnerabilityCase)` to a late joiner
is the sibling this PR also fixed) has no signal in the SYNC group that the seed
is exempt. Either SYNC-09-002 should name the messages it governs (the canonical
replication `Announce`, and messages whose content is a ledger assertion), or
CM-14 / CBT-01 should carry a cross-reference saying the bootstrap seed precedes
the first commit by design. Which group carries the qualification is the open
question.
