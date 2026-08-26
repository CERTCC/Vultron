---
title: "CBT-05-007 bootstrap vs SM-04-001 precondition guard — latent contradiction"
type: learning
timestamp: "2026-08-26"
source: ISSUE-2481
signal: spec-contradiction
---

CBT-05-007 specifies: "Bootstrap Create upgrades an existing RM.START participant to
RM.ACCEPTED."

SM-04-001 specifies: "Runtime state changes MUST be guarded by an explicit precondition
check before the state value is written."

These requirements conflict when interpreted strictly: `is_valid_rm_transition(RM.START,
RM.ACCEPTED)` returns `False` (non-adjacent), so a naive SM-04-001 guard would block the
CBT-05-007 bootstrap path.

**Resolution in #2481**: the guard explicitly exempts `RM.START` and `RM.RECEIVED` as
bootstrap-forward states. The specs are compatible if SM-04-001 is understood to mean
"check against context-appropriate preconditions" rather than "check against
`is_valid_rm_transition` only." The bootstrap case has its own precondition — the
reporter is known to have accepted by virtue of submitting the report.

The spec texts do not document this nuance. If the spec is ever revised, the bootstrap
exemption rationale should be made explicit in SM-04-001 or as a companion entry.
