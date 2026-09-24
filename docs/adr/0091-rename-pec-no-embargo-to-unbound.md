---
status: accepted
date: 2026-09-17
deciders: [adh, Claude Sonnet 4.6]
---

# ADR-0091: Rename PEC `NO_EMBARGO` to `UNBOUND`; Drop `EM.NO_EMBARGO` Alias

## Context and Problem Statement

ADR-0048 fixed the PEC transition semantics: `NO_EMBARGO` is the *absence-of-embargo*
state, not a pre-consent state. ADR-0048 deliberately deferred renaming the state,
noting that its own Context section admitted "the two readings contradict each other"
and that the open-question admonition `_oq-no-embargo-naming.md` in the spec still
asked whether the state should be renamed.

Two coupled problems remained after ADR-0048:

1. **`PEC.NO_EMBARGO` reads as negation.** The name `NO_EMBARGO` reads as either
   "absence of embargo context" or "not participating in any embargo obligation" —
   both correct but neither salient. The semantically cleaner reading is: the
   participant is **not bound by any embargo terms**. The name fails to carry that
   meaning on its own.

2. **`EM.NO_EMBARGO = NONE` alias causes a naming collision.** The Python EM
   enumeration defined `NO_EMBARGO = NONE` as an alias for the `NONE` state — making
   both machines share the name `NO_EMBARGO` for semantically different states. This
   invited the misread that PEC's `NO_EMBARGO` is a projection of EM's `NO_EMBARGO`,
   which is exactly the conflation the two-machine design exists to prevent.

The wire format is pre-production, so a breaking wire-format change is acceptable.

## Decision Drivers

- The state name should express its meaning plainly: the participant is not bound
  by any embargo terms
- The two machines MUST NOT share a state name for semantically different states
- ADR-0048's own notes identified this as unresolved; the open-question admonition
  in the spec should be resolved, not left open
- Pre-production project: breaking wire changes are acceptable

## Considered Options

1. **Rename `PEC.NO_EMBARGO` → `UNBOUND`** (chosen): "participant is not bound by any
   embargo terms." Accurate regardless of whether the case has an embargo or not —
   if the case is at `EM.NONE`, being `UNBOUND` is expected; if the case is at
   `EM.ACTIVE`, being `UNBOUND` means the participant has not agreed to the terms.
   Wire value changes from `"NO_EMBARGO"` to `"UNBOUND"`.

2. **Rename to `UNEMBARGOED`**: Considered but rejected — reads as a negative
   form of "embargoed" rather than stating a positive condition. `UNBOUND` is more
   idiomatic: "not bound by the terms" is a natural formulation in legal and
   coordination contexts.

3. **Keep `NO_EMBARGO`; only fix the alias**: Rejected — the open question
   was "should the consent state be renamed to something that states its meaning
   more plainly." Keeping the name and only dropping the alias addresses the
   collision but not the readability problem.

## Decision Outcome

**Chosen option: rename `PEC.NO_EMBARGO` → `PEC.UNBOUND` and drop `EM.NO_EMBARGO`.**

### Changes

- `PEC.UNBOUND = "UNBOUND"` — wire value changes from `"NO_EMBARGO"` to `"UNBOUND"`;
  breaking change accepted because the project is pre-production.
- `EM.NO_EMBARGO = NONE` alias is deleted — all references replace it with `EM.NONE`.
- All spec, notes, docs, code, and test references to `NO_EMBARGO` in the PEC context
  are replaced with `UNBOUND`. References to `EM.NO_EMBARGO` are replaced with `EM.NONE`.
- The open-question admonition `_oq-no-embargo-naming.md` is deleted; the question
  is answered.
- CM-18-001 gloss is updated: `UNBOUND (initial state)`.

### What `UNBOUND` means

A participant is `UNBOUND` when no embargo terms bind it. This is the correct state
for a participant when:

- The case has no embargo (`EM.NONE` or `EM.EXITED`) — the participant has nothing
  to consent to.
- The case has an active embargo but the participant has not yet agreed to the terms —
  the participant is present but not bound.

When the case is at `EM.ACTIVE` and a participant is `UNBOUND`, the CASE_MANAGER MUST
NOT deliver embargoed case content to that participant until they become `SIGNATORY`.
Being `UNBOUND` in that context is restrictive, not neutral. The name makes this
explicit: "not bound by the embargo terms currently in force."

### Consequences

- Good: the state name states its meaning without ambiguity — `UNBOUND` is plain
  English for "not bound by any embargo terms"
- Good: `EM.NONE` and `PEC.UNBOUND` are now distinct names for distinct concepts;
  the naming collision is eliminated
- Good: the open question and its admonition in the spec are resolved and deleted
- Bad: breaking wire-format change (`"NO_EMBARGO"` → `"UNBOUND"` in `emConsentState`
  ledger field); accepted because the project is pre-production

## More Information

- Supersedes the deferred naming question from ADR-0048 Context
- Builds on ADR-0048 (PEC `NO_EMBARGO` is absence of embargo, not pre-consent)
- Source: Issue #3277
- Spec amendment: CM-18-001 gloss updated
