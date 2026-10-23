---
title: "Code review for #2495 surfaced 10 pre-existing filter-node defects"
type: learning
timestamp: "2026-08-26T20:10:00Z"
source: ISSUE-2495
signal: concern
---

Code review of PR #2703 (docs-only change) surfaced 10 pre-existing defects in
the CS dimension filter nodes and related code. None were introduced by PR #2703.
All have been filed or linked:

- #2704 — Filter guards return SUCCESS for unresolvable status; GuardedCommit fires
  before AppendCaseStatusToCaseNode fails (SYNC-12-001 violation — Effects-Before-Persist)
- #2706 — FilterCsPxaDimensionNode mutates shared accumulator in-place; PXA refusals
  silently lost if blackboard returns copy
- #2707 — backend.update() called without py_trees setup()/initialise() in
  _record_named_peer (triggers/actor.py)
- #2708 — PXA validation changed to is_monotonic_pxa_forward; 7 multi-step transitions
  now accepted where old validator rejected them
- #2709 — emState serialized with str() but pxaState with .name; breaks if EM value ≠ name
- #2710 — FilterCsEmDimensionNode returns SUCCESS on missing case; implicit coupling on
  downstream commit gate
- #2711 — FilterCsEmDimensionNode._clear() zeros shared BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE;
  latent collision if more filter nodes added
- #2688 (pre-existing) — save(filtered_status) before save(case); inconsistent state on crash
- Comment on #2668 — VultronValidationError behavior change for non-inbox callers
- Comment on #2701 — dead test guard in REJECTION_VALIDATORS

The most critical is #2704 (SYNC-12-001 violation — ledger commit before effect
application can complete).

**Promoted**: 2026-08-27 — GitHub Concern issues #2739 #2740 filed. Pre-existing issues #2704-#2711 already tracked. Docs PR: <pending>.
