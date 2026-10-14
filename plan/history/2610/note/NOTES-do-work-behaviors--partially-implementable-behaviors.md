---
source: NOTES-do-work-behaviors--partially-implementable-behaviors
timestamp: '2026-10-12T19:35:48.955388+00:00'
title: Partially Implementable Behaviors
type: note
---

**Archived:** 2026-10-12
**Reason:** delivered — ID assignment and publication trees are built
**Superseded by:** `vultron/core/behaviors/report/assign_cve_id_tree.py`, `publication_tree.py`, `publish_artifact_tree.py`; CM-05-004/005

---

## Partially Implementable Behaviors

The following behaviors can be partially supported by the application:

### ID Assignment

Assigning identifiers to vulnerabilities (e.g., CVE numbers) could be
implemented as a stub behavior that:

1. Calls an external numbering API (e.g., CVE Services API) if available
2. Composes an identifier record in the case

See `docs/topics/behavior_logic/id_assignment_bt.md`. For the prototype, a
stub that records a locally-generated placeholder ID is sufficient.

### Publication

Publication typically occurs outside Vultron (e.g., a vendor advisory or
NVD database entry), but publication events SHOULD be represented as an
application-level action that:

1. Triggers state transitions (e.g., adds a `PUBLIC` PXA case status)
2. Accepts reference metadata (url, name, tags) as a `CaseReference`
3. Stores a note on the case with the metadata

See `docs/topics/behavior_logic/publication_bt.md` and
`specs/case-management.yaml` CM-05-004 and CM-05-005.
