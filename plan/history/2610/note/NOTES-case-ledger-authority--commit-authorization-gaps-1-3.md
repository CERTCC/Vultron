---
source: NOTES-case-ledger-authority--commit-authorization-gaps-1-3
timestamp: '2026-10-02T16:22:21.606331+00:00'
title: 'Commit Authorization and Coverage: Gaps 1-3'
type: note
---

**Archived:** 2026-10-02
**Reason:** redundant + closed linked items — CLP-09-001/003/004 rationale restates all three gaps; #788, #998, #923 closed
**Superseded by:** CLP-09-001, CLP-09-003, CLP-09-004

---

## Gap 1: Authorization Was a Convention, Not a Gate

`CommitCaseLedgerEntryNode` (the canonical commit mechanism established by
PR #1017 / BT-06-006) had no built-in authorization check. An audit found
that only one of roughly ten call sites guarded the commit, and it did so
with an ad hoc Python-level identity check (`_is_case_actor_receiver`)
*outside* the BT, not a role check inside it. The other call sites
committed unconditionally.

The fix is a reusable guarded-commit composition, following the same
Selector/Sequence/Success idiom already used elsewhere in this codebase
(see `notes/bt-integration.md` § "Conditional BT Branches as Selector
Composites" and § "Guarded Commit: Role-Gated Canonical Writes"):

```text
Selector
├─ Sequence
│  ├─ CheckIsCaseManagerNode   # role check, not identity comparison
│  └─ CommitCaseLedgerEntryNode
└─ Success("CommitCaseLedgerEntrySkippedNotCaseManager")
```

CLP-09-001 requires every commit call site to reach the commit only through
this kind of guarded composition. CLP-09-002 requires a test that fails if
any call site bypasses it.

## Gap 2: Commit Coverage Had No Structural Check

`validate_report`, `ack_report`, and `close_case` produced **no** canonical
ledger entry at all on `main` for an unknown span of time (issue #998).
Dispatch completeness already has a structural guarantee — DR-02-002 and
UCORG-02-002 require every `MessageSemantics` value to resolve to a callable
use case, enforced by a coverage test. Commit completeness had no
equivalent: a use case could be fully wired for dispatch and still never
touch the ledger, and nothing would fail until someone manually re-audited
the tree-by-tree commit sites (which is how #998/#1022 found the gap).
CLP-09-003 closes this by requiring the same kind of enumerated coverage
test for commits that already exists for dispatch.

## Gap 3: Dual-Invocation Use Cases Need Per-Invocation Authorization

Some use-case classes are invoked more than once for the same logical
activity, with different receiving actors. The clearest example is
`ack_report` in the two/three-actor demo: the same `AckReportReceivedUseCase`
runs once with the vendor (which holds `CVDRole.CASE_MANAGER`) as receiver, and
once with the finder as a relay target. Only the CASE_MANAGER's invocation
should commit.

This is structurally the same bug shape that produced the original
hash-chain fork in issue #923 — a use case authored or committing on behalf
of the wrong actor. CLP-09-004 makes the general rule explicit: authorization
for a commit must be evaluated **per invocation**, against the actor that is
actually active for that invocation, never assumed from the use-case class
itself or from a prior invocation having been authorized.
