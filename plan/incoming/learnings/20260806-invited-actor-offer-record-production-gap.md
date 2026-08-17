---
title: Production invite path never creates VultronOfferRecord for invited actors
type: learning
timestamp: 2026-08-06
source: ISSUE-2018
signal: concern
---

The `validate-report` trigger requires a `VultronOfferRecord` on the actor's DataLayer, keyed
by `offer_id`. This record is created only at report-submission time on the original receiving
actor. Actors who join via `Accept(Invite)` receive the case replica (via `SeedAnnouncedCaseNode`)
but never receive a `VultronOfferRecord`.

This means that in production, any actor invited mid-case cannot call `validate-report` — the
trigger will fail with "offer not found". The `seed-offer-record` PROTOTYPE endpoint added in
PR #2048 papers over this for demo purposes only.

A Concern issue should be filed to track:

- What the production mechanism should be for propagating or recreating `VultronOfferRecord`
  for invited actors
- Whether `SeedAnnouncedCaseNode` or the `Announce(VulnerabilityCase)` handler should
  synthesize a `VultronOfferRecord` when seeding from an invite path
- Spec update needed in CM-11-002 and/or the announce-case handler spec

**Promoted**: 2026-08-17 — captured in GitHub #2320 (Concern: invited actors advancing RM state — design question).
Docs PR: TBD.
