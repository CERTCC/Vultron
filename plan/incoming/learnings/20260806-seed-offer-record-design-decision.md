---
title: Chose PROTOTYPE seed endpoint over modifying invite-accept flow for CM-11-002 demo
type: learning
timestamp: 2026-08-06
source: ISSUE-2018
signal: design-question
---

To unblock Vendor2's `validate-report` call in the FVCV-handoff demo, two approaches were
available:

1. Modify `SeedAnnouncedCaseNode` or the invite-accept BT flow to also create a
   `VultronOfferRecord` when seeding an invited actor's case replica.
2. Add a PROTOTYPE-only `seed-offer-record` admin endpoint that demo scripts call explicitly.

Chose option 2 because option 1 would change production invite semantics without a spec backing
the new behavior — the production shape of offer-record propagation is unresolved (see
`20260806-invited-actor-offer-record-spec-gap.md`). The PROTOTYPE-only endpoint is explicitly
scoped to demo use and will be superseded once the spec gap is addressed.

**Promoted**: 2026-08-17 — captured in GitHub #2320 (Concern: invited actors advancing RM state — design context).
Docs PR: TBD.
