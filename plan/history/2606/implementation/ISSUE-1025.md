---
source: ISSUE-1025
timestamp: '2026-06-18T23:09:05.645653+00:00'
title: Post-convergence two-actor demo log review
type: implementation
---

## Issue #1025 — Post-convergence two-actor demo log review: verify correct CaseLedger entries for all actors

Performed the post-convergence manual review required by #1025 after all
prerequisites (#1021, #1022, #888, #792) merged to main.

**CI run analysed**: 27793292787 (PR #1063, merged 2026-06-18 — the most
recent successful demo-integration run, containing all prerequisite changes)

**Artifacts reviewed**: case-actor, vendor, finder JSONL logs for case
`urn:uuid:e0dfefbd-7da3-475b-a82b-df68e29a8fc9` (12 entries each)

**Invariant harness**: all 26 case-ledger invariants pass, zero xfail markers
remaining.

**All 17 #923 findings confirmed resolved**:

- Finding 1 (hash-chain fork) — RESOLVED: identical hashes across all 3 actors
- Finding 2 (oscillation loop) — RESOLVED: clean convergence to RM=CLOSED
- Finding 3 (finder missing genesis) — RESOLVED: complete log 0–11 for all actors
- Finding 4 (empty demo_verification payload) — RESOLVED: entries removed per ADR-0019
- Finding 5 (payload content divergence) — RESOLVED: identical content across actors
- Finding 6 (log ends mid-oscillation) — RESOLVED: both participants end RM=CLOSED
- Findings 7–11 (missing event types) — RESOLVED: validate_report, close_case,
  add_participant_status_to_participant present; EXPECTED_EVENT_TYPES updated by #1020
- Findings 12–17 (schema gaps, duplicates, tail missing) — RESOLVED

**Item 3 checks all pass**: hash chain, no RM oscillation, non-empty payloads,
expected event types, CASE_MANAGER gate (no spoofed entries), VFd/VFD/Pxa CS
transitions, embargo ACTIVE→EXITED lifecycle.

**No new discrepancies** requiring separate issues. `ack_report` absent from
this demo run by design (two-actor scenario does not call acknowledge flow).

**Docs change**: Updated `test/ci/README-case-log-ratchet.md` — all xfail rows
promoted to passing, invariant 15 row added, invariant 6 actor columns corrected.

**PR**: <https://github.com/CERTCC/Vultron/pull/1064>
