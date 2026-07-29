---
status: accepted
date: 2026-07-29
deciders: [adh]
---

# Use the ADR `status` Field as the Confidence Signal (Extend Its Vocabulary Rather Than Add a New Field)

## Context and Problem Statement

Coding agents load ADRs as authoritative context and, by default, treat them as
settled fact: `deepen-context` framed ADRs as "settled choices" not to
re-litigate. But not every ADR is equally settled. Some are ratified and
validated; some are explicitly "formed in sand" pending validation (ADR-0025);
some were never given a status at all (ADR-0024 had a blank status field); and
`docs/adr/index.md` has drifted from the per-file `status:` frontmatter
(ADR-0027 is listed as *(provisional)* in the index while its file says
`accepted`).

The consequence is a recurring, expensive failure mode: an implementer builds
on an ADR's premise as though it were validated, the premise turns out to be
provisional or wrong, and a maintainer has to interject and unwind the work.
There is no confidence signal that reaches the agent to say "this decision is
not yet validated — challenge it before you build on it."

**The design question:** how should a decision's confidence level be
represented so it reliably reaches the agent that consumes it?

## Decision Drivers

- Agents already read the `status:` frontmatter; whatever signal we choose must
  reach them without new plumbing.
- A single source of truth — the signal must not be able to drift against
  another field describing the same thing.
- The `proposed | accepted` binary is too coarse: it cannot express "ratified
  as the current direction but explicitly not yet validated."
- The signal must be lint-enforceable so status and prose cannot silently
  disagree.

## Considered Options

1. **Add a new `confidence:` (or `provisional:`) frontmatter field** alongside
   `status:`.
2. **Extend the existing `status:` vocabulary** with an
   `accepted-provisional` value and enforce status↔prose agreement by lint.
3. **Do nothing structural** — rely on authors to phrase prose carefully and on
   reviewers to catch over-confident ADRs.

## Decision Outcome

Chosen option: **Option 2 — extend the existing `status:` vocabulary.**

We add `accepted-provisional` to the ADR status value set (joining the
MADR-standard `proposed`, `accepted`, `deprecated`, `superseded` (+ `superseded_by:` field),
`rejected`). A decision tree for choosing the value lives in
`notes/specs-vs-adrs.md`, and the cardinal rule — **status and prose must
agree; a provisional/"formed in sand" body may not carry `status: accepted`** —
is enforced by a spec lint check (`specs/meta-specifications.yaml` MS-14,
implemented in `vultron/metadata/specs/lint.py`).

A separate `confidence:` field (Option 1) was rejected because it duplicates
what `status:` already expresses and creates a second thing to keep in sync —
exactly the drift that caused the ADR-0027 index/frontmatter mismatch. Option 3
was rejected because the failure is recurring precisely *because* prose-only
signals do not reliably reach agents.

### Consequences

- Good, because the confidence signal rides the field agents already read; no
  new plumbing and no parallel field to drift.
- Good, because `accepted-provisional` lets an ADR be followed as current
  direction while flagging its details as challengeable.
- Good, because the lint check makes status↔prose contradiction a hard signal
  rather than a thing a reviewer must notice.
- Bad, because `accepted-provisional` is a non-standard MADR value; readers
  coming from vanilla MADR must consult the decision tree. Mitigated by
  documenting it in `docs/adr/_adr-template.md` and `notes/specs-vs-adrs.md`.

## Validation

The `decision-audit` skill (`.agents/skills/decision-audit/`) periodically
audits ADRs for status/prose contradiction and index drift, and
`deepen-context` weights ADR trust by status. The MS-14 lint check fails CI on
a blank/invalid status or an `accepted` ADR whose prose contains provisional
markers.

## More Information

Related: ADR-0038 (spec taxonomy), `notes/specs-vs-adrs.md` (the status
decision tree). This decision is process-only and generates the MS-14 spec
group rather than a per-change requirement family.

Generated spec requirements: `meta-specifications.yaml` MS-14.
