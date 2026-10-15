---
source: CONCERN-4697
timestamp: '2026-10-15T19:35:18.799611+00:00'
title: Stub Invite omits the embargo terms when the case is in EM REVISE
type: learning
---

## Problem

A stub Invite carries the embargo terms only when the case's EM state is exactly `ACTIVE` (CM-17-002, CM-17-011; `_project_case_to_stub()` in `vultron/wire/as2/factories/case.py`).
When the case is in EM `REVISE`, an embargo is still in force (the register has one `ACTIVE` entry plus a `PROPOSED` revision, `derive_em()` in `vultron/core/states/embargo_register.py`), but the stub goes out with no `activeEmbargo` and no `caseStatus`.
The invitee then accepts without seeing the terms it will be bound by, which is the uninformed consent CM-17-002 and MV-10-006 exist to prevent.

Found while reviewing PR #4690 (the CM-17-002 / CM-17-011 split for #4673). Not in that PR's scope: widening CM-17-002 to `REVISE` changes what the protocol rule obliges, so it needs a maintainer decision.

## Questions to decide

1. Should CM-17-002 apply whenever an embargo is in force (EM `ACTIVE` or `REVISE`), not only `ACTIVE`?
2. If so, does the stub also carry the pending revision proposal, so the invitee can see both the current terms and the proposed change?

## Affected

- `specs/case-management.yaml` CM-17-002, CM-17-011
- `vultron/wire/as2/factories/case.py` `_project_case_to_stub()`

Where: vultron/wire/as2/factories/case.py

**Resolved**: 2026-10-15 — implementation tracked in #4744.
Docs PR: <https://github.com/CERTCC/Vultron/pull/4743>.
Spec: `specs/case-management.yaml`.
Notes: `notes/stub-objects.md`.
