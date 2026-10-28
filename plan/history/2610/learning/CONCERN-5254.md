---
source: CONCERN-5254
timestamp: '2026-10-28T14:17:08.955856+00:00'
title: 'Core protocol text: requirements that contradict each other or the communication
  model'
type: learning
---

## Problem

Writing rationales for the core protocol text (#4483) exposed requirement statements that contradict each other or no longer match the protocol. #4483 forbids changing statements (its AC-4), so each one is recorded here instead.

### Direct conflicts

- **DUR-07-004 vs EP-04-008 (and EP-04-005).** DUR-07-004 says an embargo end time MUST be set before a case moves to `RM.VALID`. EP-04-008 says a case created with P, X or A set stays at `EM.NONE`, with no embargo. Read together, such a case can never be validated. DUR-07-004 needs an exception for cases that cannot have an embargo, or EP-04-008 is wrong.
- **VP-06-008 and VP-06-008b vs VP-14-007.** VP-06-008 lets a participant propose or accept a new embargo in `VFdpxa`. VP-14-007 says that once Fix Ready (`VF·pxa`, which includes `VFdpxa`), no new negotiation SHOULD start and pending proposals SHOULD be rejected.
- **VP-06-003 vs VP-07-004, VP-07-012, VP-05-002 and VP-06-002.** VP-06-003 says receivers SHOULD accept *any* embargo a reporter proposes. The others make the receiver's shorter default win, let it reject an extension, cap an embargo at `P1Y`, and say not to accept once the fix is deployed. "Any" is too strong.
- **VP-11-004 and VP-11-005 vs VP-03-009 and VP-03-011.** The RM rules say that once a case exists, the CASE_MANAGER's ledger entry is the acknowledgement, so no `$RK$` is sent. The EM rules still say SHOULD send `$EK$` for every `$E*$` and `$EE$`. The occasion registry (`vultron/metadata/msm/occasions.yaml`, `vultron/semantic_registry/sync.py`) gives the EK/CK purpose to the ledger's `Reject(CaseLedgerEntry)`. The EM and RM halves no longer agree.
- **DUR-03-001 vs DUR-03-003 (minor).** "Prefer the largest unit without remainder" gives `P0D` for zero. DUR-03-003 says to prefer `PT0S`. DUR-03-001 does not name that exception.

### Wording that contradicts the communication model

- **VP-02-019, VP-03-012 ("send a message to other Participants") and VP-05-012 ("removed by the remaining Participants").** These imply that participants message and remove each other directly. VP-18-002 and PCR-08-001 route all traffic through the CASE_MANAGER. The new rationales assume delivery by CASE_MANAGER fan-out.

### Overlap and compound statements

- VP-02-015 and VP-02-020 are near-duplicates: SHOULD create a case for reports entering Valid, and for all Valid reports.
- Three rules are each stated several times:
  - No new embargo once P, X or A holds: VP-06-001, VP-11-001, VP-14-001, VP-14-002 and VP-14-003.
  - Terminate on public awareness or exploit: VP-09-001, VP-11-002, VP-14-001 and VP-14-002.
  - Terminate on attacks: VP-09-003, VP-11-006, VP-12-002b and VP-14-013.
- VP-03-013 is `priority: MAY` ("Recipients MAY ignore…") but also holds a MUST NOT for the CASE_MANAGER (record no later inbound message). That is two priorities in one statement.
- VP-11-002 is compound: terminate, who starts it, who has authority, who carries it out, and what others may do.
- VP-02-002's `verification:` checks only that Valid alone advances to Accepted, not the priority ordering its statement asserts.

## Decision needed

For each conflict: which requirement states the protocol, and how is the other reworded, split or retired? The overlap and compound items follow the MS-03 split rule. The near-duplicates are retired by MS-04 (an ID is never reused).

Where: specs/vultron-protocol-spec.yaml, specs/duration.yaml, specs/embargo-policy.yaml

Governing specs: VP-06, VP-07, VP-11, VP-14, DUR-03, DUR-07, EP-04, MS-03

**Resolved**: 2026-10-28 — implementation tracked in #5297, #5298, #5299.

Decisions: DUR-07-004 is scoped to embargo-eligible cases, and the `RM.VALID` guard
admits an ineligible case at `EM.NONE`. A placeholder terminated embargo was rejected
because it fabricates records and contradicts EP-04-008. VP-14-007 is the Fix Ready
default, and a brief publication-prep embargo (VP-06-008b) is its one exception.
VP-06-003 becomes "counter-propose rather than reject". The repeated rules live in
VP-06-001, VP-09-001 and VP-09-003, and their copies are removed. VP-11-004 and
VP-11-005 follow EP-09-009, so the ledger commit is the acknowledgement. No ADR.
