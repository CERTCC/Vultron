---
title: "Pydantic v2 runs mode='before' validators in reverse definition order"
type: learning
timestamp: "2026-08-28T00:00:00Z"
source: ISSUE-2662
signal: theme-candidate
---

When multiple `@model_validator(mode="before")` validators are defined on the
same Pydantic v2 model, they execute in **reverse definition order** — the
last-defined validator runs first.

This caused a silent data-loss bug in `ParticipantStatus`: `_enforce_role_dimension_invariant`
(defined after `_migrate_flat_fields`) fired first, saw `data['vf'] is None`,
seeded `data['vf'] = {}`, and then `_migrate_flat_fields` found the key already
present and skipped flat-key migration. Result: `vf_state=CS_vf.Vf` passed at
construction was silently reset to the initial state.

**Fix**: check for flat keys (`vf_state`, `vfState`, `d_state`, `dState`) in the
invariant validator before seeding the empty dict. The invariant should only seed
when *no* form of the value is present in the raw data.

**How to apply**: whenever two `mode="before"` validators on the same model have
an ordering dependency, either (a) merge them into a single validator, or (b)
explicitly guard the later-running (earlier-defined) validator against data already
set by the first-running (later-defined) validator.

---

**Promoted**: 2026-09-03 — captured in `notes/domain-validation.md` ("Pitfall: `mode=\"before\"` Validators Run in Reverse Definition Order"). Docs PR: <https://github.com/CERTCC/Vultron/pull/3147>.
