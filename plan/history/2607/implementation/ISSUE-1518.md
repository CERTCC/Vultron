---
source: ISSUE-1518
timestamp: '2026-07-20T17:41:01.099255+00:00'
title: Migrate report/offer semantic reads to VultronOfferRecord
type: implementation
---

## Issue #1518 — Migrate report/offer semantic activity reads off dl.read (core state)

Implemented ADR-0035 DL-06 Category B migration for the report/offer domain. All three core sites that re-read stored wire Offer activities have been migrated to read from the new VultronOfferRecord core state record.

**New:** `VultronOfferRecord` (vultron/core/models/offer_record.py) — captures offer_id, report_id, offer_actor_id, offer_to at adapter time. Wire vocab registration at vultron/wire/as2/vocab/objects/offer_record.py enables dl.read() round-trip.

**Migrated:** _resolve_offer_and_report (report.py), _compute_report_addressees (emit.py),_collect_create_case_addressees (case_creation.py).

**Ratchet:** "Offer" removed from ACTIVITY_TYPE_EXEMPTIONS (AC-3 satisfied).

**Error path:** non-offer IDs now raise VultronNotFoundError (404) instead of VultronValidationError (422).

**Rebase note:** origin/main had concurrent #1517 changes to the same files; resolved one conflict in report.py (_build_tree needed both offer_id=self._offer.offer_id and captured=self._captured from the two branches).

PR: <https://github.com/CERTCC/Vultron/pull/1538>
