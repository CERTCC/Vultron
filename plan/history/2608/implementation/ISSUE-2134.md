---
source: ISSUE-2134
timestamp: '2026-08-10T23:29:25.919632+00:00'
title: fix invite-path RM triage crash (EmitValidateReportActivity)
type: implementation
---

Fixes #2134. `EmitValidateReportActivity` crashed with `AttributeError: 'NoneType' has no attribute 'model_dump'` on invite-path vendor triage.

**Root cause chain (4 links):**

1. `Announce(VulnerabilityCase)` sent bare report ID refs, violating CBT-01-007
2. `SeedAnnouncedCaseNode` did not store embedded `VulnerabilityReport` objects
3. No `VultronOfferRecord` was created for invited actors from the canonical `("Offer","VulnerabilityReport")` ledger backfill
4. `validate_report` fell through to a None offer and crashed at `offer.model_dump(by_alias=True)`

**Fix summary:**

- `announce_vulnerability_case()` now embeds full `as_VulnerabilityReport` objects (CBT-01-007)
- New `_store_embedded_reports()` in `SeedAnnouncedCaseNode` persists embedded reports
- New `ApplyOfferReportFromLedgerNode` (own file per BTND-07-004) creates `VultronOfferRecord` from `submit_report` ledger entries during SYNC backfill
- `_ReportsMixin._resolve_offer()` reconstitutes wire Offer from `VultronOfferRecord` + `VulnerabilityReport` when direct DL read returns None
- Demo `run_invite_path_rm_triage` no longer spoofs via `seed_offer_record_for_actor`; protocol does the work

**PR:** <https://github.com/CERTCC/Vultron/pull/2168>
