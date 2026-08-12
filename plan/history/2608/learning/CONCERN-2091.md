---
source: CONCERN-2091
timestamp: '2026-08-11T18:13:28.941708+00:00'
title: embargo_adherence specified as derived but implemented as stored fail-open
  field
type: learning
---

`embargo_adherence: bool = True` on `ParticipantStatus` is a stored field that
can drift from the PEC state it projects, and its fail-open default (`True`)
reads as "is a signatory" even when consent has never been recorded.

**Root cause**: `_sync_latest_status_metadata()` updates `consent`
(`PecDimension`) on every PEC write but never touches `embargo_adherence`.
No code sets `embargo_adherence = False`; no construction path derives it.

**Decision**: `embargo_adherence` is strictly derived from PEC state —
`True` iff `PEC.SIGNATORY`, `False` otherwise (draft spec §6.4.6, ADR-0056).
Implement as a Pydantic `@computed_field` on `ParticipantStatus`. Wire layer
(`as_ParticipantStatus.from_core()`) computes from `consent.state` rather than
copying. Wire default changes from `True` to `False`.

**Out of scope**: `apply_pec_trigger` fail-open on invalid triggers → #1871.

**Resolved**: 2026-08-11 — implementation tracked in #2189.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2188>.
Spec: `specs/case-management.yaml` CM-18-008.
ADR: `docs/adr/0056-embargo-adherence-computed-field.md`.
