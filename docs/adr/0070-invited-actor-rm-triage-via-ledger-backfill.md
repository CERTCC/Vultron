---
status: accepted
date: 2026-08-24
deciders: Allen D. Householder
consulted: CONCERN-2320
informed: []
---

# Reuse `validate-report` for Invited Actors; Derive `VultronOfferRecord` from Ledger Backfill

## Context and Problem Statement

CM-11-002 requires that invited actors run the standard RM triage cycle
(RM.RECEIVED → RM.VALID or RM.INVALID → RM.ACCEPTED or RM.DEFERRED) after
accepting a case invitation. The only RM-validation trigger in the codebase is
`validate-report`, which resolves the case's `VulnerabilityReport` via a
`VultronOfferRecord` keyed by `offer_id`.

Invited actors join via `Accept(Invite)` and receive a case replica via
`Announce(VulnerabilityCase)`. They never process the original
`Offer(VulnerabilityReport)` directly, so their DataLayer initially has no
`VultronOfferRecord`. Before the `add_report_to_case` ledger backfill mechanism
existed, this meant invited actors could not call `validate-report` without a
synthetic injection workaround (`seed-offer-record`, a demo-only scaffold).

Three options were evaluated when CONCERN-2320 was filed.

## Decision Drivers

- Protocol uniformity: all participants should run the same RM triage cycle.
- Avoid forking the RM state-machine path for invited vs. direct-path actors.
- The CaseActor already backfills `add_report_to_case` ledger entries to all
  participants; this backfill embeds the full `VulnerabilityReport` and original
  offer metadata.

## Considered Options

1. **Reuse `validate-report`; derive `VultronOfferRecord` from ledger backfill** —
   Process the `add_report_to_case` ledger entry to create both the
   `VulnerabilityReport` replica and the `VultronOfferRecord` in the invited
   actor's DataLayer, then run the standard `validate-report` trigger.

2. **Separate `engage-case`/`validate-case` trigger** — Add a new trigger that
   advances RM.RECEIVED → RM.VALID for invited actors without requiring an
   OfferRecord, separating "validate the original report offer" from "validate
   the case as a joining participant."

3. **Exempt invited actors from RM.VALID** — Review whether the full RM triage
   cycle is required for invited actors; since CM-11-002 says SHOULD (not MUST),
   allow invited actors to advance directly to RM.ACCEPTED without RM.VALID.

## Decision Outcome

Chosen option: **Option 1 — reuse `validate-report`; derive `VultronOfferRecord`
from the ledger backfill**, because it preserves full protocol uniformity, avoids
introducing a second RM advancement path, and is already implemented as the
`add_report_to_case` ledger backfill mechanism (ISSUE-2134,
`ApplyOfferReportFromLedgerNode`).

### Consequences

- Good, because all participants run the identical RM triage cycle regardless of
  whether they received the original Offer or joined via invitation.
- Good, because no new trigger endpoint is needed; the existing `validate-report`
  and `engage-case` triggers work unchanged for invited actors.
- Good, because the `seed-offer-record` demo scaffold can be removed, eliminating
  a misleading synthetic-injection path.
- Bad, because the invited actor's `validate-report` call is gated on the
  `add_report_to_case` ledger entry being processed first; callers must poll or
  gate on this event before triggering (see `run_invite_path_rm_triage` in
  `vultron/demo/helpers/workflow.py`).

## Validation

`ApplyOfferReportFromLedgerNode`
(`vultron/core/behaviors/sync/nodes/offer_report_effect.py`) creates the
`VultronOfferRecord` from the `add_report_to_case` ledger entry.
`run_invite_path_rm_triage` (`vultron/demo/helpers/workflow.py`) demonstrates
the full invited-actor RM triage cycle using this mechanism without any
synthetic injection; its docstring explicitly states "no spoofing via
seed-offer-record is needed or permitted."

## Pros and Cons of the Options

### Option 1 — Reuse `validate-report`; derive `VultronOfferRecord` from ledger backfill

- Good, because protocol uniformity: one RM path for all participants.
- Good, because no new trigger or message type is needed.
- Good, because the ledger backfill already carries all necessary data
  (offer ID, report, offer actor).
- Bad, because invited actors must wait for the `add_report_to_case` backfill
  to be processed before calling `validate-report`.

### Option 2 — Separate `engage-case`/`validate-case` trigger

- Good, because semantically explicit: "validate the case" is different from
  "validate the original report offer."
- Bad, because it forks the RM advancement path and requires a new trigger,
  a new BT subtree, and potentially a new message type for the notification.
- Bad, because it introduces two distinct ways to reach RM.VALID, making the
  protocol harder to reason about and test.

### Option 3 — Exempt invited actors from RM.VALID

- Good, because simpler: invited actors advance directly from RM.RECEIVED to
  RM.ACCEPTED.
- Bad, because it degrades protocol fidelity: an actor that has not validated
  the vulnerability is recorded as having committed to remediation.
- Bad, because CM-11-002 SHOULD is intentional — it reflects the expectation
  that joining a case should still involve at minimum a validation decision.
  Exempting invited actors silently downgrades this expectation.

## More Information

Generated spec requirements: `case-management.yaml` CM-11-005.

Source concern: CONCERN-2320.
Implementation: ISSUE-2134 (`ApplyOfferReportFromLedgerNode`,
`vultron/core/behaviors/sync/nodes/offer_report_effect.py`).
Cleanup tracked: `seed-offer-record` removal issue created when CONCERN-2320
was resolved.
