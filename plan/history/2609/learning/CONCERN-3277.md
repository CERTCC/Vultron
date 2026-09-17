---
source: CONCERN-3277
timestamp: '2026-09-17T14:04:56.974214+00:00'
title: 'PEC state naming: UNBOUND replaces NO_EMBARGO; EM alias dropped'
type: learning
---

## Concern

`PEC.NO_EMBARGO` had two problems: (1) the name reads as negation ("no
embargo") rather than stating the participant's position clearly; (2) the
`EM.NO_EMBARGO = NONE` alias made both machines share a name for semantically
different states, inviting the misread that PEC's state is a projection of
EM's state.

ADR-0048 fixed the *transition semantics* but deliberately deferred the
rename. `_oq-no-embargo-naming.md` in the spec acknowledged the open question.

## Decision

Rename `PEC.NO_EMBARGO` → `PEC.UNBOUND`. Wire value changes from `"NO_EMBARGO"`
to `"UNBOUND"` (breaking; acceptable pre-production). Drop `EM.NO_EMBARGO = NONE`
alias entirely; all references migrate to `EM.NONE`.

**What UNBOUND means:** the participant is not bound by any embargo terms.
This is correct whether the case has no embargo at all (`EM.NONE`) or has an
active embargo the participant hasn't agreed to. In the latter case, being
`UNBOUND` is *restrictive* — the CASE_MANAGER withholds embargoed content
until the participant becomes `SIGNATORY`.

## ADR

ADR-0091: `docs/adr/0091-rename-pec-no-embargo-to-unbound.md`
ADR-0048 amended in-place to note the subsequent rename.

## Scope

Eradication task: `NO_EMBARGO` replaced in all specs, notes, and docs files
in this planning PR. Code rename deferred to impl Task #3308.

## PR

<https://github.com/CERTCC/Vultron/pull/3307>

## Implementation

Task #3308 covers code + test rename: 20+ production files, 50+ test occurrences.
