---
source: CONCERN-6003
timestamp: '2026-11-12T17:32:14.688669+00:00'
title: ADR-0154's stage-isolation rule vs. the path answer ADR-0153 requires
type: learning
---

Theme: theme:protocol-correctness — settles which in-memory reads across a received stage boundary are allowed, so the stage-isolation rule and the path stage agree.

## Summary

ADR-0154 says a received stage reads only the record and the store, never what an earlier stage left in memory. ADR-0153 and HP-01-036 require the path branches to read the answer the path stage door resolved, in memory. Read literally, the two decisions conflict. #5047's AC-2 architecture test (`test/architecture/test_received_stages_read_the_record.py`) found this one read and pins it, citing this issue.

## Surface Symptom vs. Underlying Problem

- **Surface symptom**: one pinned exemption in an architecture test. `CheckReceivedPathNode` reads `ReceivedPathNode`'s resolved path across the door/handling-tree boundary.
- **Underlying problem**: the rule as written does not say which in-memory state it forbids. Two reads have this shape, and they differ:
  1. **The retired `rerun` flag recorded history**: "this run is a re-run". Only memory knew that, and a restart loses it. ADR-0154's rule exists for that hazard. #5047 removed the flag: a re-run is now read from the record's `HANDLED` stage.
  2. **The path answer is derived.** The path stage computes it again from the store on every run, so a restart loses nothing: the next run asks again.
  3. **The path answer read is load-bearing.** The path is decided once, at the door, before the act's own writes. Some acts change who the CASE_MANAGER is partway through the run (an ownership transfer, a role delegation). Branches that asked `has_role` again after those writes could get a different answer from the door's. HP-01-036 and ADR-0153 prevent exactly that divergence.

What the rule seems to need to forbid is in-memory state that cannot be computed again from the record and the store. The path answer can; `rerun` could not.

## Category

Decision conflict between two accepted ADRs (ADR-0153, ADR-0154).

## Severity

Low. No behavior is wrong today. The pin keeps the AC-2 test failing on any other cross-boundary read.

## Evidence

- `vultron/core/behaviors/case/nodes/path_branch.py`: `CheckReceivedPathNode(stage, path)` holds the path stage node and reads its answer.
- `test/architecture/test_received_stages_read_the_record.py`: `PATH_ANSWER_READS` pins exactly that read, and the test fails on every other door-to-handling read. It was proved with a planted `rerun`-style closure and with a second planted door read.
- HP-01-036: the receiver's role is asked once per message, in the path stage.

## Impact if Ignored

The pin stays as an unexplained exception to a rule that reads as absolute, and a later change may break one decision while trying to satisfy the other.

## Suggested Action

The maintainer decides between:

- amending ADR-0154's stage-isolation rule to forbid only in-memory state that cannot be computed again from the record and the store, which admits the path answer; or
- recording the path on the received record, so the branches read it from the record. This is a further record-schema change beyond the one stage approved for #5047.

**Resolved**: 2026-11-12. The maintainer chose "start over": a received run with no verdict is run again from its door checks and never resumes partway. Each stage boundary hands over one named input, and the resolved path is the doors' input to the handling tree. ADR-0154 detail 8 was rewritten in place (with `status_override:`), CLP-10-083 and CLP-10-084 were added, and the architecture test's pin now cites CLP-10-084. No implementation issue: the run-twice sweep from #5047 already covers ownership transfer and role delegation.
Docs PR: https://github.com/CERTCC/Vultron/pull/6346.
Spec: `specs/case-ledger-processing.yaml`.
