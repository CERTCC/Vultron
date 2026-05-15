---
source: Priority-320
timestamp: '2026-04-10T00:00:00+00:00'
title: 'Priority 320: additional demo feedback'
type: priority
---

Tasks in this priority: D5-7-EMSTATE-1, D5-7-AUTOENG-2,
D5-7-TRIGNOTIFY-1, D5-7-DEMONOTECLEAN-1.

These are the remaining round-2 demo feedback tasks that are independent of
the SYNC replication work.

Two tasks originally in this group — D5-7-CASEREPL-1 and D5-7-ADDOBJ-1 —
have been **superseded by SYNC-2** (Priority 330). The `Announce(CaseLogEntry)`
replication path replaces the direct `Create(VulnerabilityCase)` and
`Add(CaseParticipant)` delivery paths to participant actors. Implementing
stopgap fixes would require rework immediately after SYNC-2.

D5-7-DEMOREPLCHECK-1 is **deferred to after SYNC-2** (Priority 330) because
meaningful finder-replica verification requires checking log-state consistency,
not just field equality.

**D5-7-TRIGNOTIFY-1** (populate `to` field in trigger activities) is also a
prerequisite for SYNC-2 fan-out to work correctly; complete it as part of
Priority 320 before starting Priority 330.
