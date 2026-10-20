---
source: CONCERN-4980
timestamp: '2026-10-20T19:56:43.111369+00:00'
title: 'A failed received act leaves only intake''s archive: unverified HTTP redelivery
  and no notice to the sender'
type: learning
---

## Concern

After #4933 (PR #4979, ADR-0151), a received embargo act whose consequence fails keeps no ledger entry and no consequence. Intake's archive of the received activity (`ReceivedActivityRecord`) still stands. Two things about that state are not verified:

- **A later delivery over HTTP.** The in-process tests call the use case directly, and a redelivery there runs the act again. Through the FastAPI inbox, `FastAPIIngressAdapter.rehydrate` (`vultron/adapters/driving/fastapi/inbox_orchestration.py`) treats an activity that intake already archived as a redelivery and rebuilds it without this body's received evidence ("the handlers' own idempotency guards answer the repeat"). Nobody has checked that this rebuilt activity commits the same entry (the ledger is a postmark on the received envelope, ADR-0107) when the first delivery's act rolled back.
- **The sender is not told.** The inbox answers 202 before processing, and a refusal notice answers only a precondition guard's refusal (CLP-10-022). A failed act is an internal error that is only logged. This was already so before #4933.

## Why it matters

ADR-0151 states that a later delivery of a failed received act is not stopped as a repeat and runs the act again. If the HTTP rebuild path cannot commit it, the claim holds only in process, and a failed received act is lost with no signal to anyone.

## Suggested approach

- Add an integration test: fail a received proposal's relay through the inbox, then post the same body again and assert the act is applied.
- Decide whether a failed received act needs any signal to its sender; the maintainer's rule forbids repair passes, so this is about notice, not recovery.

Governing specs: CLP-07-015, CLP-10-017, IE-10-001, VM-08-002

Where: vultron/adapters/driving/fastapi/inbox_orchestration.py

**Resolved**: 2026-10-20 — implementation tracked in #4981.

Docs PR: <https://github.com/CERTCC/Vultron/pull/4985>.

Spec: `specs/protocol-asks.yaml` (ASK-07-010).
