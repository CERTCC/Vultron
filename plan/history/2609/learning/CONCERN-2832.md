---
source: CONCERN-2832
timestamp: '2026-09-01T18:07:51.271128+00:00'
title: 'G04: Causal ordering and ledger authority — fix mis-citations, add CM-29 and
  CSB-19 spec groups'
type: learning
---

## Outcome

Closed CONCERN-2832 (G04: Causal ordering and ledger authority). The design was
already substantially resolved by ADR-0079 (accepted 2026-08-26) and the
CLP-14/CLP-15 spec entries in `specs/case-ledger-processing.yaml`. Planning work
reduced to: fixing three stale ADR-0041 mis-citations, adding two new spec groups
to codify the remaining gaps, and creating two impl Tasks.

## What Was Done

**PR #2978**: <https://github.com/CERTCC/Vultron/pull/2978>

1. **Fixed ADR-0041 mis-citations** (three sites): `specs/case-management.yaml`
   CM-18-007 rationale, `notes/event-driven-control-flow.md`, and
   `docs/adr/0058-causal-gating-in-demo-scenarios.md` all cited ADR-0041 as the
   authority for `log_index` causal order. Corrected to ADR-0079 / CLP-14-001.

2. **Added CM-29** "Case Status Recency Resolution" (`specs/case-management.yaml`):
   `current_status` MUST determine recency by timestamps only; `id_` MUST NOT be
   used as a sort tiebreaker. Closes the spec gap behind bug #2737
   (UUID-scheme IDs sort higher than HTTPS-scheme IDs, causing auto-seeded initial
   statuses to beat received statuses when both lack timestamps).

3. **Added CSB-19** "CS Ordering Invariants Under Out-of-Order Ledger Delivery"
   (`specs/cs-behavior.yaml`): CS guards (ephemeral-state, history-prefix,
   CP-before-ET) MUST be evaluated at buffer-drain time in causal order, not at
   original out-of-order receipt. Codifies existing correct behaviour per ADR-0037.
   Closes the spec gap behind #2527.

## Implementation Issues Created

- **#2979** (size:S, parent #2684, blocked-by #2832): Fix `current_status` UUID
  tiebreaker — replace `cs.id_` with `datetime.min.replace(tzinfo=timezone.utc)`
  in `vultron/core/models/case.py` and
  `vultron/wire/as2/vocab/objects/vulnerability_case.py`.

- **#2980** (size:M, parent #607, blocked-by #2832): Write
  `docs/topics/case_ledger_sync.md` — user-facing explanation of ledger
  synchronisation, log_index causal order, and the ADR-0037 buffer/drain
  mechanics.

## Learnings

- **ADR-0079 was already the settled answer.** When a Concern arrives with a
  multi-issue batch and an ADR already exists for the core question, the planning
  session's real work is gap-filling (mis-citations, missing spec entries) not
  re-deciding. Orient-agent + deepen-context surfaced this in minutes; don't
  assume a Concern requires a new ADR.

- **ID-scheme sort order is an invisible footgun.** `urn:uuid:…` (prefix `'u'`)
  sorts lexically above `https://…` (prefix `'h'`). Any `max(key=…id_)` fallback
  on mixed-scheme IDs will silently prefer the UUID-scheme value. Watch for this
  pattern wherever a "latest" or "most-recent" winner is chosen from a mixed
  collection.

- **Buffer-time vs drain-time invariant evaluation** is a recurring spec gap in
  async BT architectures. The code was already correct (guards fire at drain),
  but without a spec entry the behaviour was invisible to reviewers and future
  implementors. When ADR-0037-style buffering is in play, always check whether
  invariant specs explicitly state *when* the guard fires.

- **#1166 (distributed consensus ledger) does not conflict with ADR-0079.**
  AC-4 of #2832 required checking that the near-term decision (ADR-0079:
  single-writer CaseActor, log_index = causal order) does not foreclose
  consensus-based ledgering (#1166). It does not: ADR-0079 defines the
  *current* authority model for cases with a single designated CaseActor.
  #1166 would introduce a consensus layer *beneath* that abstraction —
  consensus is an upgrade path for the authority mechanism, not a contradiction
  of it. The log_index-is-causal-order property would remain valid in a
  consensus-backed system; the CaseActor role would simply gain a replicated
  backing store. #1166 remains open as a long-horizon architectural item;
  no immediate action required.
