---
source: NOTES-case-state-model--opp-06-future-vfd-pxa-transition-handling
timestamp: '2026-10-02T16:24:11.908111+00:00'
title: OPP-06 — Future VFD/PXA transition handling
type: note
---

**Archived:** 2026-10-02
**Reason:** delivered + redundant — VFD/PXA transitions go through the dimension transition() methods (ADR-0036, ADR-0075); rule stated by CM-04-005
**Superseded by:** CM-04-005; ADR-0036; ADR-0075

---

## OPP-06 — Future VFD/PXA transition handling

When vendor-fix or public/exploit/attack transitions are implemented beyond
object creation, reuse the authoritative VFD/PXA transition definitions rather
than encoding bespoke conditionals in individual use cases or BT nodes. That
keeps participant-specific VFD logic and shared PXA logic aligned with the
formal state model and ensures future persistence guards stay consistent across
code paths.

See `archived_notes/state-machine-findings.md` OPP-06 and
`specs/case-management.yaml` `CM-04-005`.
