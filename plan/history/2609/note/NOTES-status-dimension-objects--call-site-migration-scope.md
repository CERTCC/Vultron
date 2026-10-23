---
source: NOTES-status-dimension-objects--call-site-migration-scope
timestamp: '2026-09-17T17:32:54.967937+00:00'
title: Call-Site Migration Scope
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** dimension objects are the live access pattern

---

## Call-Site Migration Scope

There are approximately 308 call sites in `vultron/` and `test/` (excluding
`vultron/bt/`) that access the old flat enum fields. The migration pattern
is mechanical:

| Old access pattern | New access pattern |
|---|---|
| `status.em_state` | `status.em.state` |
| `status.pxa_state` | `status.pxa.state` |
| `status.rm_state` | `status.rm.state` |
| `status.vfd_state` | `status.vf.state` (VENDOR) or `status.d.state` (DEPLOYER) |
| `status.em_consent_state` | `status.consent.state` (or `None` check) |
| `CaseStatus(em_state=EM.ACTIVE, ...)` | `CaseStatus(em=EmDimension(state=EM.ACTIVE), ...)` |

The `vultron/bt/` legacy simulator is **out of scope** — it uses the custom
BT engine and accesses enums directly; migrating it is a separate effort.

---
