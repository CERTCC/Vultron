---
title: Documentation Sweeps — Verification Budget
status: active
description: >
  Why relocating a documentation claim is not the same as verifying it,
  how mechanical sweeps surface defects as a side effect, and what agents
  must do when moving or republishing content under docs/.
related_notes:
  - notes/diataxis-framework.md
  - notes/documentation-strategy.md
---

# Documentation Sweeps — Verification Budget

A mechanical pass over prose — a naming sweep, a Diátaxis extraction, a page
split — forces an agent to read claims it would otherwise skim.
Two sessions have now surfaced real defects this way, in both cases as a side
effect rather than as the stated goal.
The corollary: a sweep that only *moves* text carries the source's errors
forward with full authority, and the act of copying is the cheapest moment to
catch them.

## The core insight: re-reading in a new context

Reading moved content in a new context is a different act from reading it in
place.

In place, a Mermaid diagram is furniture — part of the page's visual rhythm.
Copied onto a page whose job is to justify a design decision, the same diagram
becomes a set of falsifiable claims.
"This participant sends this message to that one."
Either the code confirms it or the code contradicts it.

The page that originally contained the diagram was already reviewed; the
diagram survived because no reviewer had reason to interrogate its individual
arrows.
Moved to an Explanation page, each arrow is an assertion waiting for a reader
to ask "is this actually what the code does?"

A faithful copy satisfies the sweep's usual success criterion — "all content
accounted for" — perfectly, while propagating a false statement to a second
location with more authority than it had in the first.

## The two witnesses

### Witness 1 — #3342 (CaseActor → CASE_MANAGER rename, 2026-09-17)

A naming sweep forced re-reading of the rationale text surrounding each
occurrence of `CaseActor`.
That reading exposed CM-20-001/004/005, which claimed to `refines:` CBT-01-003
while asserting its opposite.
The specs had coexisted on `main` until the sweep.
Recorded in `plan/incoming/learnings/20260917-3342-caseactor-rename-keeps-infrastructure-concrete.md`.

### Witness 2 — #3002 (Diátaxis extraction, 2026-09-18)

A Diátaxis extraction copied a Mermaid diagram from `docs/howto/acknowledge.md`
onto a new `docs/topics/` Explanation page.
Reading the diagram as a set of claims — not as page furniture — exposed three
wrong AS2 verb attributions that had survived issue #2785, whose stated purpose
was correcting accuracy errors on those same pages.
The near-miss: the new Explanation page almost shipped telling implementers to
emit `Leave(VulnerabilityReport)`, an activity matching no registered
`ActivityPattern`.
Defects filed as #3395.

## What agents must do when moving content

### Verify claims; do not just copy them

When a documentation sweep moves, extracts, or republishes existing content,
every claim must be re-read as an assertion and verified against its authority
before the change is committed.

Authorities, in descending precedence:

1. The source code — for any claim about what the implementation does.
2. A spec entry in `specs/*.yaml` — for any normative statement.
3. A reference page in `docs/reference/` — for any factual summary.

"The original page said this" is not an authority.
Re-reading the source in its new context is the minimum act of verification.

Faithful copying is not verification (DF-10-001).
The move is not complete until each claim that is now a first-class assertion
on the destination page has been confirmed.

### Prefer includes over copying

When the same content legitimately belongs on two pages, create an
`{% include-markdown %}` fragment rather than copying prose.
One authoritative source, multiple render points — drift is structurally
impossible (DF-10-002).

Fragment naming convention: `docs/includes/_<slug>.md`.
The fragment itself must satisfy all style rules applicable to the quadrant of
each host page (DF-09-007, DF-09-008).

### Scope the verification budget before starting

Before beginning a sweep of more than a few pages, identify which content will
move and whether any of it contains first-order empirical claims (code
behavior, protocol verb attributions, state machine transitions).
Budget explicit verification time for those claims.
A sweep that has no verification budget is a sweep that will silently propagate
whatever was wrong in the source.

## Normative anchors

- DF-10-001 (MUST): verify moved claims — `specs/diataxis-requirements.yaml`
- DF-10-002 (SHOULD): use `{% include-markdown %}` for shared content — `specs/diataxis-requirements.yaml`

## Reference

Source: CONCERN-3403 (second witness).
Related: #3395 (AS2 verb defects surfaced by witness 2), #3402 (automated
AS2 verb-pairing checks), #3414 (implementation issue).
