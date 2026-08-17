---
title: CM-11-002 does not specify how invited actors acquire VultronOfferRecord for triage
type: learning
timestamp: 2026-08-06T00:00:00Z
source: ISSUE-2018-invited-spec-gap
signal: spec-gap
---

CM-11-002 states that actors receiving a case via `Accept(Invite)` SHOULD run the standard RM
triage cycle (RECEIVED → VALID → ACCEPTED). However, `validate-report` requires a
`VultronOfferRecord` keyed to the original `offer_id`, which is only created when the report is
first submitted (at `Offer(VulnerabilityReport)` time on the original receiver's DataLayer).

The spec does not address how invited actors — who never saw the original `Offer` activity —
should obtain this record. The demo works around this with a PROTOTYPE-only `seed-offer-record`
endpoint, but the production path is unspecified.

A spec entry covering how `VultronOfferRecord` propagates (or is recreated) for invited actors
is needed before CM-11-002 can be considered fully implemented in production.

**Promoted**: 2026-08-17 — captured in GitHub #2320 (Concern: invited actors advancing RM state — design question).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
