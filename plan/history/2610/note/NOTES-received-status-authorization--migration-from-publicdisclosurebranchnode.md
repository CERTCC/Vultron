---
source: NOTES-received-status-authorization--migration-from-publicdisclosurebranchnode
timestamp: '2026-10-02T16:24:11.323365+00:00'
title: Migration from PublicDisclosureBranchNode
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered — migration complete; the table is now wrong (ThreatTerminationBranchNode runs in both add_participant_status_tree and add_case_status_tree)
**Superseded by:** vultron/core/behaviors/status/nodes/threat_termination.py; RSH-03-001

---

## Migration from PublicDisclosureBranchNode

| Before | After |
|---|---|
| `PublicDisclosureBranchNode` in `add_participant_status_tree` | Removed |
| Gates: CS.P AND CASE_OWNER sender | N/A |
| Runs before canonical write | N/A |
| `ThreatTerminationBranchNode` in `add_case_status_tree` | Added |
| Gates: CS.P OR CS.X OR CS.A (no sender gate) | Correct tree, post-write |

---
