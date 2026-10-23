---
source: CONCERN-923
timestamp: '2026-06-12T15:52:23.115413+00:00'
title: 'Two-actor demo case log: hash-chain fork, oscillation loop, and 17 protocol
  correctness findings'
type: learning
---

## Summary

A review of case log replicas from a two-actor demo run (2026-06-12, case
`urn:uuid:0f69d289-734f-47af-afd2-37091895371a`) surfaced 17 findings across
all three actors (case-actor, vendor, finder), including two critical-severity
bugs: a permanent hash-chain fork starting at logIndex=3 (50% cross-replica
mismatch rate) and an infinite RM ACCEPTED↔CLOSED oscillation loop on the
finder participant with no convergence.

The findings together pointed to a deeper structural gap: the canonical case
log was being used as a generic event sink, with synthetic checkpoint events
(`demo_verification`) committed alongside missing protocol-significant
activities (`validate_report`, `accept_report`, `propose_embargo`,
`accept_embargo`, `notify_*`, `close_case`, `add_note`). The conceptual model
"the case log is a CaseActor-authored ledger of protocol-significant
assertions, NOT a per-actor process log" was implicit but not enforced.

## Findings (abbreviated)

- 🔴 Finding 1: Hash-chain fork at logIndex=3 — duplicate `Add(ParticipantStatus)`
  emitted by both vendor and case-actor for the same RM/CS transition; replicas
  receive inconsistent bytes.
- 🔴 Finding 2: Case-actor oscillation between ACCEPTED and CLOSED for finder,
  13 consecutive entries, log ends mid-oscillation.
- 🟠 Findings 3–6: pre-join history absent for late joiners; empty
  `payloadSnapshot` for synthetic `demo_verification`; payload content
  divergence; no terminal all-CLOSED state.
- 🟡 Findings 7–11: missing protocol event log entries (validate_report,
  accept_report, propose_embargo, accept_embargo, notify_*, close_case,
  add_note, announce_case_log_entry).
- 🟡 Findings 12–13: `emConsentState` and `cvdRole` absent from
  `ParticipantStatus` snapshots.
- 🟡 Findings 14–15: report-URI context discontinuity; nested embargo objects
  stored as bare ID strings.
- 🟡 Findings 16–17: duplicate Add for same transition; tail missing from
  finder/vendor (demo terminated mid-oscillation).

## Resolution

**Resolved**: 2026-06-12 — Planned via `plan-issue` skill under epic #788
(Converge CaseEvent flow onto canonical CaseLogEntry).

**Docs PR**: <https://github.com/CERTCC/Vultron/pull/924>

Docs PR adds:

- **ADR-0019** — "Case Log Is a Canonical Protocol Ledger, Not a Process Log"
  (carves into stone the separation between canonical case log and per-actor
  process log; rejects the conflated-log alternative).
- **`specs/case-log-processing.yaml`** — new **CLP-07** group (CLP-07-001
  through CLP-07-007): one entry per accepted assertion, verbatim
  `payloadSnapshot`, asserter-identity preservation, exclusion of
  diagnostics, commit-boundary guard, inline nested objects, case-URI
  context.
- **`notes/case-log-authority.md`** — extended with canonical entry criteria,
  allowed vs. disallowed entry-type examples, the `Announce` envelope vs.
  `payloadSnapshot.actor` distinction (with worked example), and
  commit-boundary enforcement guidance.
- **`AGENTS.md`** — pitfall: "Case Log Is a Ledger, Not a Process Log".

**Implementation tracked in:**

- #925 — CI case-log invariant assertion harness (xfail ratchet) — lands first
- #926 — CaseActor commit-path uniqueness (Findings 1, 16)
- #927 — Sender-side trigger audit sweep (PCR-08 enforcement)
- #928 — RM terminal-state guard (Finding 2)
- #929 — Remove synthetic checkpoint events (Finding 4)
- #930 — Commit-boundary runtime guard (CLP-07-005)
- #931 — ParticipantStatus schema completeness: emConsentState + cvdRole
  (Findings 12, 13)
- #932 — Snapshot context normalization at report→case promotion (Finding 14)
- #933 — Inline nested protocol objects in canonical snapshots (Finding 15)

**Refinements to existing issues:**

- #789 — added explicit ACs for Findings 7–11 (missing protocol event entries)
- #791 — added join-time backfill AC (Finding 3)

All new issues are children of epic #788, blocked by #923 (this concern) and
by #925 (the harness scaffolding lands first). Each implementation PR is
required to flip its named xfail invariant in the harness to passing, giving
the dependency chain progressive deep-test coverage rather than one big
final test imposition.

## Key conceptual outcomes

- **Two distinct logs** (now ADR-level): canonical case log = protocol ledger,
  CaseActor-authored, replicated, hash-chained; per-actor process log =
  Python logging, ephemeral, never replicated. They MUST NOT be conflated.
- **CaseLogEntry payloadSnapshot is the verbatim asserted AS2 activity** —
  `payloadSnapshot.actor` is the original asserter; `Announce.actor` is the
  CaseActor (envelope). These MUST NOT be swapped.
- **One canonical entry per logical state change**, broadcast byte-identically
  to every participant.
- **Commit-boundary enforcement**: runtime guard at the CaseActor's commit
  path rejects non-canonical entries before they enter the hash chain.
- **Progressive test ratcheting**: invariant assertions land up front as
  xfail; each fix PR flips one xfail to passing.
