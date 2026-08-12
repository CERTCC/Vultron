---
status: accepted
date: 2026-08-11
deciders: Allen D. Householder
consulted: []
informed: []
---

# Buffer Pre-Genesis `Announce(CaseLedgerEntry)` and Drain on Case Seed

## Context and Problem Statement

A participant replica receives the canonical recorded log from the CaseActor as
a stream of `Announce(CaseLedgerEntry)` activities, and it receives the case
itself as a `Create`/`Announce(VulnerabilityCase)`. Both travel over a transport
with **no ordering guarantee** (HTTP `BackgroundTasks` fan-out), so a replica can
receive a ledger entry *before* the case that anchors it. In that pre-genesis
window `_reconstruct_tail_hash` cannot derive the per-case genesis hash
(CLP-08-005): there is no local tail and no case object to seed one from.

ADR-0037 buffers *forward-gap* entries — those for a case whose genesis anchor is
already known — but its forward-gap test (`log_index > tail_index + 1`) never
fires when there is no chain at all, so a pre-genesis entry falls straight through
to the reject-on-missing-case path (`ReconstructOrRejectOnMissingCase`,
SYNC-15-001) and is **dropped**, leaving convergence to the reject → replay
round-trip.

That round-trip is exactly the mechanism ADR-0037 showed does not converge under
adversarial reordering, and it has two observed costs: transient CLP-08-005 churn
logged during fvcv-handoff (issue #2169), and — fatally for the fcvcv V1 demo —
the `add_report_to_case` entry being dropped so no `VultronOfferRecord` is ever
created and the report offer 404s (issue #2180). Issue #2186 identifies the
missing pre-genesis buffer as the root cause of #2180. How should a replica handle
a valid ledger entry that arrives before its case?

## Decision Drivers

- Convergence must not depend on whether the case or its ledger entries arrive
  first (SYNC-15, SYNC-10-004); the transport provides no ordering.
- The fix must interoperate with unknown implementations — we cannot assume the
  sender retries or that any recovery message is delivered in order either.
- Must preserve the effects-before-persist invariant (SYNC-12-001) and the
  DataLayer-presence-means-committed invariant (SYNC-13-001 / SYNC-14-005).
- Reuse the existing `LedgerGapBuffer` machinery rather than introduce a second,
  parallel holding area.
- Keep the genesis `Reject` as the loss backstop (SYNC-15-001) so an entry that
  is genuinely never delivered still triggers replay.

## Considered Options

- **A. Rely on the reject → replay backstop only** — keep dropping pre-genesis
  entries; trust SYNC-15-001 + SYNC-15-003 rate-limited replay to redeliver them
  once the case is seeded.
- **B. Buffer pre-genesis entries and drain on case seed** — hold every entry for
  a not-yet-seeded case in the existing `LedgerGapBuffer` (keyed by
  `prev_log_hash`), then drain the chain the moment the case seed anchors the
  deterministic genesis hash.
- **C. Wait for the genesis ledger entry** — buffer, but drain only when the
  `log_index == 0` entry is separately re-delivered, not when the case is seeded.
- **D. Add a client-side ordering guard in the demo** — make `fcvcv_demo.py`
  order the case seed before the report so the race cannot occur in the demo.

## Decision Outcome

Chosen option: **B, buffer pre-genesis entries and drain on case seed.**

The genesis hash is **deterministic from the case object alone** —
`compute_genesis_hash(case_id, created_at, case_actor_id)` runs at
`VulnerabilityCase` construction whenever `attributed_to` is present (CLP-08) — so
seeding the case is sufficient to anchor the chain; the replica need not wait for
the genesis ledger entry to be re-delivered. That makes option C strictly weaker
(it re-introduces a dependence on redelivery order) and lets B reuse the ADR-0037
drain unchanged: a buffered genesis entry's `prev_log_hash` equals the per-case
genesis hash, so once the case is seeded `_reconstruct_tail_hash` returns
`(genesis_hash, -1)`, `take_next(genesis_hash)` finds it, and the rest cascade in
hash-chain order.

A new `BufferPreGenesisEntryNode` is wired as the first child of the
`ReconstructOrRejectOnMissingCase` fallback (wrapped in `FailureIsSuccess` so the
`Reject` still fires), mirroring the buffer-and-reject structure of
`CheckHashOrRejectOnMismatchNode`. Unlike `BufferOutOfOrderEntryNode` it applies
**no** forward-gap check — there is no tail in the pre-genesis window, so every
entry for the missing case is held. The drain logic itself is extracted into a
module-level `drain_gap_buffer(...)` reused by both the announce receive path and
a new drain-on-seed hook in `AnnounceVulnerabilityCaseReceivedUseCase`.

Option A alone is insufficient for the same reason ADR-0037 rejected repairing
replay: the replay re-announces entries individually over the same unordered
transport and each pre-genesis entry Rejects again, amplifying churn (#2169). We
keep the genesis `Reject` at buffer time purely as the backstop for entries that
are genuinely *lost*. Option D was declined: the protocol, not the demo harness,
must converge under reordering, so the demo is left to prove the protocol fix
end-to-end (per the "protocol fix only" decision on #2180).

### Consequences

- Good: a replica that receives ledger entries before its case converges as soon
  as the case is seeded, regardless of delivery order (SYNC-15-004, SYNC-15-005);
  #2180's dropped `add_report_to_case` entry is retained and applied.
- Good: reuses `LedgerGapBuffer` and the ADR-0037 drain — one holding area, one
  cascade, one effects-before-persist path.
- Good: no new dependence on sender retry or on the genesis ledger entry being
  re-delivered; the deterministic genesis hash anchors from the case object.
- Good: the genesis `Reject` remains as the loss backstop (SYNC-15-001), so a
  genuinely lost entry still triggers replay.
- Neutral: buffered state is in-memory and lost on restart; the SYNC-10 catch-up
  gate re-syncs any gap after restart, so no durability is required.
- Bad: the pre-genesis hold has no forward-gap bound to distinguish "far-future"
  from "just early", so it leans entirely on the `LedgerGapBuffer` size cap +
  farthest-ahead eviction (recoverable via the Reject backstop).

## Validation

- Pre-genesis regression tests through `AnnounceLedgerEntryReceivedUseCase` and
  `drain_gap_buffer` (`test/core/use_cases/received/test_sync.py`,
  `TestPreGenesisAnnounceBuffering`): a pre-genesis entry is buffered not dropped
  (with the Reject still queued), a single buffered entry drains when the case is
  seeded, and a multi-entry chain cascade-drains on seed.
- A use-case-level drain-on-seed test
  (`test/core/use_cases/received/actor/test_announce.py`,
  `TestAnnounceDrainsPreGenesisBuffer`): seeding the case via
  `AnnounceVulnerabilityCaseReceivedUseCase` drains a pre-buffered pre-genesis
  entry into the local ledger.
- The fcvcv demo exercises the end-to-end path: the `add_report_to_case` entry is
  retained across the case-seed race, so the `VultronOfferRecord` is created and
  the report offer no longer 404s (#2180).

## Pros and Cons of the Options

### A. Rely on the reject → replay backstop only

- Good, because it reuses the existing recovery mechanism with no new state.
- Bad, because replay re-announces entries individually over the same unordered
  transport, so the drop race reappears — the same failure ADR-0037 documented.
- Bad, because it amplifies CLP-08-005 churn (#2169) and leaves #2180's dropped
  entry unrecovered within the demo's timeout.

### B. Buffer pre-genesis entries and drain on case seed

- Good, because convergence becomes independent of case-vs-entry arrival order.
- Good, because it reuses `LedgerGapBuffer` and the ADR-0037 drain unchanged.
- Good, because the deterministic genesis hash lets the case seed alone anchor
  the chain — no wait for the genesis ledger entry.
- Neutral, because it introduces bounded, ephemeral per-actor state (shared with
  the forward-gap buffer).
- Bad, because the pre-genesis hold cannot tell "early" from "far-future" and
  relies on the size cap for its bound.

### C. Wait for the genesis ledger entry

- Good, because it drains through the identical `log_index == 0` code path.
- Bad, because it re-introduces a dependence on redelivery order — the genesis
  entry can itself reorder or be lost — which is the whole problem.

### D. Client-side ordering guard in the demo

- Good, because it is a small, local change that hides the symptom for #2180.
- Bad, because it does not fix the protocol: any real deployment under reordering
  still drops entries. The demo must validate the protocol, not paper over it.

## More Information

Root-cause / symptom split and the deterministic-genesis insight are recorded in
`plan/incoming/learnings/` (`20260811-self-healing-recovery-logged-at-error.md`,
`20260810-clp-08-005-protocol-hardening-gap`) and issues #2186 (root cause) and #2180
(symptom). Builds on ADR-0037 (forward-gap buffering) and the SYNC-15
Genesis-Unavailable requirements.

Generated spec requirements: `sync-ledger-replication.yaml` SYNC-15-004 and
SYNC-15-005.
