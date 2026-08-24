---
source: CONCERN-2320
timestamp: '2026-08-24T16:36:41.888703+00:00'
title: Invited actors advancing RM state — validate-report via ledger backfill
type: learning
---

## Problem

CM-11-002 says invited actors SHOULD run the standard RM triage cycle, including
validating the reported vulnerability (RM.RECEIVED → RM.VALID or RM.INVALID).
The only RM-validation trigger in the codebase is `validate-report`, which requires
a `VultronOfferRecord` via `VultronOfferRecord.build_id(offer_id)`.

Invited actors never receive the original report offer. They join the case after it
has already been created by the original receiving coordinator. There is no
`VultronOfferRecord` for them because they never processed the original Offer.

## Current workaround

The demo uses a PROTOTYPE-ONLY endpoint:
`/{actor_id}/demo/seed-offer-record` via `seed_offer_record_for_actor()` in
`vultron/demo/helpers/workflow.py`. This endpoint exists **only** in the demo
adapters and explicitly labels itself as prototype scaffolding. In production,
invited actors have no mechanism to obtain an OfferRecord.

## Design question

Invited actors join a case that was already created. They are **validating the case**
(deciding whether to participate in coordination), not the original report. Is
`validate-report` (which is designed for the original receiver and requires an
OfferRecord) even the right mechanism for invited actors advancing RM?

Options evaluated:

1. **No change to validate-report** — provide invited actors with a forwarded/synthetic
   OfferRecord at invite-acceptance time. This keeps the RM mechanics identical but
   requires designing the forwarding path for the OfferRecord (or re-using the case
   object ID as a stand-in).

2. **Separate invite-path RM trigger** — add an `engage-case` or `validate-case`
   trigger that advances RM.RECEIVED → RM.VALID for invited actors without needing
   an OfferRecord. This separates "validate the original report offer" from "validate
   the case as a joining participant."

3. **Invited actors don't need RM.VALID** — review whether the full RM triage cycle
   is even required for invited actors vs. just RM.RECEIVED → RM.ACCEPTED. CM-11-002
   says SHOULD, not MUST.

## Resolution

**Option 1 chosen.** `ApplyOfferReportFromLedgerNode` (ISSUE-2134,
`vultron/core/behaviors/sync/nodes/offer_report_effect.py`) already derives the
`VultronOfferRecord` from the `add_report_to_case` `CaseLedgerEntry` backfilled by
the CaseActor. Invited actors wait for that backfill, then call the standard
`validate-report` trigger unchanged. Options 2 and 3 were rejected: Option 2 would
fork the RM path and require a new message type; Option 3 silently degrades protocol
fidelity against the SHOULD in CM-11-002.

**Resolved**: 2026-08-24 — implementation tracked in #2514.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2512>.
Spec: `specs/case-management.yaml` CM-11-005.
Notes: ADR `docs/adr/0070-invited-actor-rm-triage-via-ledger-backfill.md`.
