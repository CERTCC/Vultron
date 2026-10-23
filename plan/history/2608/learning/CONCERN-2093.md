---
source: CONCERN-2093
timestamp: '2026-08-11T18:33:15.042089+00:00'
title: Observer participant role — admission path, content scope, VFD exclusion, role
  stacking
type: learning
---

## Outcome

Concern #2093 resolved. All four design questions raised by the concern were answered and codified in ADR-0056 and spec groups CM-25/CM-26.

**Key decisions:**

- `CVDRole.OTHER` renamed to `CVDRole.OBSERVER` — the rename exposes the pre-existing gap; defining semantics is what enables the rename
- Observer is the **base role** (lowest non-null privilege set); all other CVD roles are additive
- Admission: standard Invite/Accept flow; `Invite` carries `case_roles=[CVDRole.OBSERVER]` — satisfies CM-17-003 and closes the `[]` hole from #1288
- Content scope: full case content via existing MV-10-005 gate; no new delivery tier needed
- RM triage: full RM cycle applies; `RM.ACCEPTED` = "engaged/monitoring", not "developing fix"
- VFD exclusion: sole-OBSERVER participants MUST NOT emit VFD transitions (CV, CF, CD); check is `case_roles == [CVDRole.OBSERVER]` (sole-role), NOT `CVDRole.OBSERVER in case_roles` (membership)
- Role stacking: union of permissions — a MUST NOT on OBSERVER is superseded when any co-role carries MAY/SHOULD/MUST for the same action class (CM-26-001)

**Pitfall (codified in ADR-0056 Consequences):**
Code checking the VFD exclusion MUST test whether OBSERVER is the participant's *only* role, not merely whether they hold OBSERVER. OBSERVER + DEPLOYER can and should emit VFD/D transitions.

**Wiring:**

- Issue #2092 (sentinel) blocked-by impl issue #2192 (code rename)
- Impl issue #2192 blocked-by #2093 (this concern); child of epic #1935

## PR

<https://github.com/CERTCC/Vultron/pull/2190>

## Implementation Issue

<https://github.com/CERTCC/Vultron/issues/2192>
