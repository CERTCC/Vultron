---
source: CONCERN-3748
timestamp: '2026-10-12T15:07:03.962619+00:00'
title: Specify what the CASE_MANAGER does on receiving a rejected case ownership transfer
type: learning
---

## Problem

CM-21-010 says a `Reject(Offer(VulnerabilityCase))` for an ownership transfer is addressed to the CASE_MANAGER's inbox, which matches the Accept path. Nothing says what the CASE_MANAGER does after it receives one.

Today `RejectCaseOwnershipTransferReceivedUseCase` (`vultron/core/use_cases/received/actor/ownership.py`) only logs the rejection and returns `applied`. That means:

- no ledger entry is committed, although the Offer was ledgered and broadcast to every participant, so every replica still shows a transfer in flight;
- the offerer is not told, because the Reject no longer goes to the offerer;
- nothing says whether the case can be offered again, to the same transferee or to a different one.

These questions used to sit in an "Open question: rejected transfers" section of `docs/topics/case_lifecycle/ownership_transfer.md`. #3621 rewrote that page to describe how a transfer works and linked this issue in place of the list.

## Questions to settle

1. Does a declined transfer get a ledger entry and an `Announce(CaseLedgerEntry)`, as the Accept does under CM-21-007?
2. How does the offerer learn that its offer was declined?
3. Can the case be offered again, and does anything have to be cleared first?

The answers probably add received-side CM-21 requirements, and may extend ADR-0053.

Governing specs: CM-21, CM-24

**Resolved**: 2026-10-12. Implementation tracked in #4475, #4476 and #4477.

Outcome:

- **Ledgering.** The CASE_MANAGER ledgers and broadcasts the transferee's Reject (CM-21-012). Only the pending Offer's transferee may send it (CM-21-013). The offerer learns of the decline from the broadcast.
- **Re-offering.** One ownership Offer may be open per case. Once it is answered, it may be offered again to anyone, with nothing to clear (CM-21-014).
- **Trigger.** A `reject-case-ownership-transfer` trigger is added (TRIG-11-005).
- **Root cause.** "Reject" named both the AS2 activity and the CASE_MANAGER's ledger verdict. The verdict is now "admitted"/"refused" (CLP-02-012, glossary "Ledger Admission"). The activities that are not case events form a closed list (CLP-02-013). The never-written CLP-09-003 commit-coverage gate lands as a strict xfail; #4476 tracks making it pass.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4474>.
Spec: `specs/case-management.yaml`, `specs/case-ledger-processing.yaml`, `specs/triggerable-behaviors.yaml`.
Notes: `notes/ownership-transfer.md`, `notes/case-ledger-authority.md`.
