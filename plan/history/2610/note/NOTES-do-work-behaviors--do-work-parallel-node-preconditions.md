---
source: NOTES-do-work-behaviors--do-work-parallel-node-preconditions
timestamp: '2026-10-12T19:35:48.449101+00:00'
title: 'Do-Work Parallel Node: Preconditions'
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — the PRIORITY 30 scoping decision is history; the per-sub-behavior trees now carry their own guard nodes (the lasting rule stays in the note)
**Superseded by:** `vultron/core/behaviors/report/` trigger trees; TRIG-02-003

---

## Do-Work Parallel Node: Preconditions

The top-level "do work" behavior in `docs/topics/behavior_logic/do_work_bt.md`
is modeled as a parallel node with several sub-behaviors (assign CVE ID,
notify others, develop fix, deploy fix, publish, etc.). In the documentation
this is simplified as if all sub-behaviors execute simultaneously.

In practice, each sub-behavior requires its own preconditions to determine
when it should be triggered. For example:

- "assign CVE ID": requires that the case be validated, actor has CNA role,
  and no CVE ID has been assigned yet.
- "notify others / identify participants": requires that the case be valid
  and that embargo terms are established or that the notification is
  embargo-compatible.
- "develop fix": requires that the case be validated and assigned to a
  vendor; external trigger.
- "deploy fix": requires that a fix exists and testing is complete; external
  trigger.
- "publish": requires that the embargo period has ended or been waived.

As the implementation matures, each sub-behavior SHOULD have its
preconditions explicitly defined as condition-check nodes in its BT
sub-tree. This will also clarify which behaviors can be triggered
programmatically and which require external input or human confirmation.

**Design Decision**: For PRIORITY 30, focus implementation effort on the
RM/EM-related triggerable behaviors defined in `specs/triggerable-behaviors.yaml`.
Treat `assign-cve-id`, `notify-actor`, and `identify-participants` as
later-phase behaviors (MAY in TRIG-02-003); represent them and any other
non-implemented sub-behaviors as named placeholder nodes in the BTs.
