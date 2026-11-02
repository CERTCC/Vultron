---
source: CONCERN-5586
timestamp: '2026-11-02T15:56:37.540223+00:00'
title: Nothing requires a branch point's decider to run in a fixed-role cast slot
type: learning
---

**Original concern.** Every one of the decision sites across the registered demo
scenarios is decided by an actor in cast slot 0, 1 or 2, and only a fixed-role slot
declares `VULTRON_ACTOR__DEFAULT_CASE_ROLES` (DEMOCI-11-026, DEMOCI-11-032). No
requirement stated that property and no check enforced it. The concern asked for a
DEMOCI-11 requirement pinning a branch point's deciding actor to a slot that declares
the role the branch point names, plus a static check over the branch-point table and
every scenario's role declarations, failing at collection rather than in a container.

**Resolved**: 2026-11-02 — the premise was overturned and the fix is a role-model
change, not a seating rule. Implementation tracked in #5619 and #5620.

A participant's role never comes from its container. It comes from an act in the case:
submitting the report, claiming a role when proposing the case, or being assigned one
through the suggest-actor flow (CM-16-003, CM-17-003). The container-level
`default_case_roles` setting is read in exactly one place, the proposal a report
receiver sends, and is a hint rather than an authority. The concern's stated property
is also false for three of the eight branch points: the two Reporter decisions rest on
report authorship, the join decision on the Invite's offered role, and the case-owner
decision on owning the case, which no container declares.

The real defect is that `CVDRole` mixes three kinds of role — a position in one case,
authority over a case, and a standing of the organization — in one enum and one list
field, so a participant can hold authority and no position at all. Two doors do that:
a proposal with an empty claim, which ADR-0133 recorded as acceptable, and the
create-case trigger, which hard-codes owner and manager. The demo's late role refusal
is a symptom of that.

ADR-0169 splits the vocabulary three ways by scope, requires every participant to hold
a position, and makes a case proposer claim its position at the call site. Two run-time
guards that patch the shared enum retire, because a role Offer typed to positions
cannot name authority and a removal that edits positions cannot reach it. Once every
door hands over a position, the static check the concern asked for has nothing left to
catch; the leftover want, catching a scenario that lets the wrong actor decide, needs a
decider-to-container mapping that exists only after #5536 and #5537.

Docs PR: <https://github.com/CERTCC/Vultron/pull/5618>.
ADR: `docs/adr/0169-case-roles-split-into-position-authority-and-standing.md`.
Notes: `notes/role-taxonomy-split.md`.
Also filed: #5621, to model the Exploit Publisher as an actor standing.
