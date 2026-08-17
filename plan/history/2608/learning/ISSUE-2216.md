---
title: "Fix for ISSUE-2216 is narrow: update_participant_rm_state fallback, not upstream bootstrap"
type: learning
timestamp: "2026-08-12T00:00:00Z"
source: ISSUE-2216
signal: design-question
---

During the ISSUE-2216 fix, the invited-path 422 could have been addressed at two layers:

1. **Upstream (bootstrap)**: Fix `_store_embedded_participants` or the `Announce(VulnerabilityCase)` wire path so the invitee's DL actually receives the `CaseParticipant` object when the case snapshot arrives. This is the correct long-term fix (tracked as ISSUE-2223).

2. **Downstream (recovery)**: Fix `update_participant_rm_state` to bootstrap a fresh `CaseParticipant` when the actor is in `actor_participant_index` but the object is absent from the local DL. This is what was implemented.

The downstream fix was chosen because:

- It is scoped to the one function that was directly failing (ISSUE-2216 constraint: don't expand PR #2205's scope).
- It is safe: `actor_participant_index` is authoritative for membership; creating a participant at RM.RECEIVED when the index confirms participation is protocol-correct (CM-11-001).
- It unblocks the demo CI without touching the complex announce/bootstrap path that has broader blast radius.

**Trade-off**: The fallback advances only one step from RM.RECEIVED, so `RM.ACCEPTED` cannot be bootstrapped directly (RECEIVED → ACCEPTED is not a valid RM transition). The demo flow always calls validate-report before engage-case, so this is correct in practice. If that ordering invariant ever breaks, the error message will be a confusing "bootstrap RM transition to ACCEPTED blocked" warning rather than a clear indication that validate was skipped.

The systemic fix (ISSUE-2223) should eventually remove the need for the fallback entirely by ensuring the participant object lands in the invitee's DL during bootstrap.

**Promoted**: 2026-08-17 — captured in GitHub #2223 (closed — bootstrap gap fixed).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>0>0>0>0>0>0>0>0>0>.
