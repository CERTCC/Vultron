---
title: "VCR-019c \u2014 Enum/state consolidation study (2026-03-18)"
type: implementation
date: '2026-03-18'
source: VCR-019c
legacy_file: plan/history/IMPLEMENTATION_HISTORY.md
legacy_line: 2068
legacy_heading: "VCR-019c \u2014 Enum/state consolidation study (2026-03-18)"
date_source: git-blame
legacy_heading_dates:
- '2026-03-18'
---

## VCR-019c — Enum/state consolidation study (2026-03-18)

**Backfilled from**: `plan/history/IMPLEMENTATION_HISTORY.md:2068`
**Canonical date**: 2026-03-18 (git blame)
**Legacy heading**

```text
VCR-019c — Enum/state consolidation study (2026-03-18)
```

**Legacy heading dates**: 2026-03-18

**Task**: Study task — identify which enums across `vultron/case_states/` and
`vultron/bt/**/states.py` can be consolidated before implementing VCR-019a/b.

**What was done**: Inventoried all state/enum definitions across both packages
and analysed cross-layer import patterns to determine correct relocation targets
for VCR-019a/b. Documented findings in `plan/IMPLEMENTATION_NOTES.md`.

**Key findings**:

- No duplicates exist between `case_states/` enums and `bt/**/states.py` enums.
- Enums categorised into four groups:
  - **Group A** (move to `vultron/core/states/`): `RM`, `EM`, `CS`/`CS_vfd`/
    `CS_pxa`/component IntEnums/helper functions, `CVDRoles`
  - **Group B** (merge into `vultron/errors.py`): `CvdStateModelError`
    hierarchy
  - **Group C** (move with `case_states/` as `vultron/core/case_states/`):
    `EmbargoViability`, SSVC-2, CVSS-3.1, `Actions`, VEP, zero-day enums
  - **Group D** (stay in `vultron/bt/`): `MessageTypes`, `CapabilityFlag`,
    `ActorState`
- VCR-019a/b plan updated with prerequisite notes and clarified scope (019b
  scope narrowed: only Group A enums move; `ActorState` stays in bt/).
- 60+ import sites in `vultron/` and 21+ in `test/` will need updating in
  VCR-019a/b.

**Lessons learned**: The plan listed 019c after 019a/b; in practice it is a
prerequisite. Updated plan task ordering to reflect this dependency.

### Test results

No code changes; test suite unchanged at 981 passed, 5581 subtests.
