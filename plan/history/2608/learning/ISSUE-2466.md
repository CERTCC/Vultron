---
title: MUST_WITHOUT_VERIFICATION gate may need to extend to MUST_NOT requirements
type: learning
timestamp: "2026-08-24T00:00:00Z"
source: ISSUE-2466
signal: concern
---

The new `must_without_verification` linter warning (added in ISSUE-2466) fires
only for `priority: MUST` specs. MUST_NOT requirements impose equally strong
negative obligations — a MUST_NOT with no `verification:` field is equally
unverifiable.

Deferred as #2535 (size:S, concern, Schedule=Someday) because:

- Extending to MUST_NOT was explicitly out-of-scope per the issue body.
- The blast radius (how many MUST_NOT specs lack verification:) was not
  measured at PR time.

Follow-up: check whether the MUST_NOT population is large enough to justify
adding it to the gate in the same sweep as MUST verification backfill, or
whether a separate task is cleaner.

**Promoted**: 2026-08-27 — archived (already in specs/notes/AGENTS.md or tracked as GitHub issue). Docs PR: <pending>.
