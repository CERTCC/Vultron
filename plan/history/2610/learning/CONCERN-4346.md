---
signal: spec-contradiction
source: CONCERN-4346
timestamp: '2026-10-08T19:23:18.552940+00:00'
title: Removed dead CreateCaseParticipantNode chain; its spec clause BTND-05-003 mandated
  recreating it
type: learning
---

`CreateCaseParticipantNode` (`vultron/core/behaviors/case/participant_tree.py`) and the leaf nodes only it composes are not reachable from any production tree. Only `test/core/behaviors/case/nodes/participant/test_participant_add.py` builds them.

PR #4337 removed the chain's last step, `QueueAddParticipantNotificationNode`, because it sent `Add(CaseParticipant)` when it seated a participant. That message now only reinstates a removed participant (CM-31-011, ADR-0116). The rest of the chain is still dead code, and it seats a member without a stub Invite, which ADR-0114 does not allow.

**Why it matters**: a later change could wire the chain back into a tree. It would then seat a participant without the stub-Invite flow, and the flow's checks would not run (CM-11-006, CM-17-004).

**Planning finding (beyond the original concern)**: the spec clause BTND-05-003 mandated `CreateCaseParticipantNode` as the required "generic participant creation node" — i.e. the spec actively instructed a future agent to recreate the exact dead chain. The node bundled embargo-signatory seeding (`SeedParticipantAsSignatoryIfEmbargoActiveNode`) that is incompatible with the inert, non-signatory invitee seating ADR-0114 requires, so it could never have served the invitee flow. The real DRY center is the policy-free helper `_create_and_attach_participant`, which owner, reporter, and proposal seating already share. BTND-05-003 centralized at the wrong layer (the policy-bundling composite node) and was miscategorized `kind: protocol` though it names a reference-implementation construct. This matches the known pattern where a spec clause pins a defective idiom (ISSUE-3293).

**Resolved**: 2026-10-08 — spec reconciled in docs PR #4366 (BTND-05-003 re-grounded on `_create_and_attach_participant` and relabeled `kind: protocol` → `kind: project`; `MAX_UNCOVERED_PROTOCOL_SPECS` lowered 712 → 711). Code removal and the live invitee-node DRY reconciliation tracked in #4367. Docs PR: <https://github.com/CERTCC/Vultron/pull/4366>. Spec: `specs/behavior-tree-node-design.yaml` (BTND-05-003).
