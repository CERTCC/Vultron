---
source: CONCERN-3681
timestamp: '2026-09-25T13:47:59.237996+00:00'
title: 'EM state display names: spec Revised/Exited vs enum and pages Revise/eXited'
type: learning
---

## Problem

The EM state names disagree between the normative spec and everything else:

- `docs/reference/vultron-spec/_em-state-machine.md` (spec §7) calls the states *Revised* and *Exited*, for example at lines 43–48, 57 and 109.
- The code enum `vultron/core/states/em.py` uses `REVISE` and `EXITED`, and the process-model pages (`docs/topics/process_models/em/*`) say *Revise* and *eXited* (the X is the DFA shorthand letter).

A reader moving from the explanation pages to spec §7 meets two names for the same state. This came up while remediating those pages in #3620 (PR #3680). I left the names alone there because a rename was out of scope.

## Decision needed

Pick one display name for each state and apply it across the spec prose, `docs/topics/process_models/em/*` and the glossary. The enum values themselves are wire and persistence identifiers, and renaming them would be a breaking change. The likely fix is to make the spec prose match the enum (*Revise*), or to document the prose-versus-enum difference in one place.

Governing specs: none cited; related to the EM state machine in spec §7.

---

**Resolved**: 2026-09-25 — implementation tracked in #3686.

Decision: keep both name sets. Spec §7 uses *Revised*/*Exited* on purpose, because those are the names the RFC review asked for (`notes/rfc-review-rubric.md`, which also warns against a blind rename sweep). The process-model pages keep *Revise*/*eXited* because the capital letters give the DFA shorthand R and X. Nothing is renamed. #3686 moves the explanation, which is currently written out on two pages, into one include fragment and adds the spec's names to the glossary.

Docs PR: <https://github.com/CERTCC/Vultron/pull/3688>.
