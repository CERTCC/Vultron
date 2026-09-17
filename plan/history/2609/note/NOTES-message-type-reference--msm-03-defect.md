---
source: NOTES-message-type-reference--msm-03-defect
timestamp: '2026-09-17T17:25:25.559461+00:00'
title: 'MSM-03 defect: CV/CF/CD were mapped to the wrong object'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a,e) fixed in MSM-03-001/002/003; standing rule promoted to spec-authoring-rules.md
**Superseded by:** specs/message-semantics-mapping.yaml MSM-03; notes/spec-authoring-rules.md

---

## MSM-03 defect: `CV`/`CF`/`CD` were mapped to the wrong object

MSM-03-001, MSM-03-002, and MSM-03-003 asserted — at `MUST` / `kind: protocol` —
that `CV`, `CF`, and `CD` dispatch as `ADD_CASE_STATUS_TO_CASE` with wire form
`Add(CaseStatus)[target=VulnerabilityCase]`, and that the `CaseStatus` payload
"encodes the `vendor_aware` / `fix_ready` / `fix_deployed` state flag."

All three claims were wrong:

- `as_CaseStatus` carries only `em_state` and `pxa_state`. There are no
  `vendor_aware`, `fix_ready`, or `fix_deployed` fields on it, in any spelling.
- The VF and D dimensions live on `as_ParticipantStatus` as `vf_state: CS_vf`
  and `d_state: CS_d`, so the correct semantic is
  `ADD_PARTICIPANT_STATUS_TO_PARTICIPANT` and the correct wire form is
  `Add(ParticipantStatus)[target=CaseParticipant]`.
- Per ADR-0075, this is necessary, not incidental: VF is **vendor-scoped** and D
  is **deployer-scoped**. **There are no case-level VF/D states at all** — those
  dimensions are always participant-specific. A case-level status cannot express
  *which* vendor is aware, which is the entire purpose of the VF dimension in
  MPCVD.

The last point is worth stating as a standing rule, because the CS model's own
name invites the error. The CS "case state" hypercube mixes two scopes:

| Dimensions | Scope | Wire home |
|---|---|---|
| `V` `F` `D` | **Participant** — one per (actor × case) | `as_ParticipantStatus.vf_state` / `.d_state` |
| `P` `X` `A` | **Case** — one per case | `as_CaseStatus.pxa_state` |

`notes/case-state-model.md` § `CaseStatus` / `ParticipantStatus` already records
this, including that `vf` and `d` are `None` for non-VENDOR and non-DEPLOYER
participants and that this is *structurally enforced*. So MSM-03 did not merely
lack an update — it asserted, normatively, the opposite of an invariant the
domain model enforces.

Cause: MSM-03 predates the VF/D split (ADR-0075) and the dimension-object
decomposition (ADR-0036), and its group description generalized "All CS
shorthands (CV through CA) share the `ADD_CASE_STATUS_TO_CASE` semantic" onto
entries that should have diverged. An implementer following it faithfully would
have dropped the vendor identity — see `notes/spec-authoring-rules.md` §
"Name the Authority 'CASE_MANAGER', Not 'CaseActor'" for the same failure mode.

**Guidance:** when a spec group description asserts a property of "all" its
members, check each member against the code before relying on the
generalization. Group descriptions are written once and rarely revisited when one
member's behaviour changes.
