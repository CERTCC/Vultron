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
related_specs:
  - specs/diataxis-requirements.yaml
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

A naming sweep over `specs/*.yaml` forced re-reading of the rationale text
surrounding each occurrence of `CaseActor`.
That reading exposed CM-20-001, CM-20-004 and CM-20-005, which contradicted
CBT-01-003 while resting on it.
Only CM-20-001 carried the contradiction structurally, in a declared
`refines: CBT-01-003` relation.
CM-20-004 and CM-20-005 cited CBT-01-003 in their rationale prose instead, which
is why no relation check could have found them and only reading could.
The three had coexisted with CBT-01-003 on `main` until the sweep corrected them
in commit `2b0184756`.
Recorded in `plan/incoming/learnings/20260917-3342-caseactor-rename-keeps-infrastructure-concrete.md`.

This witness therefore sits outside DF-10's `docs/` scope.
The mechanism is not specific to either tree: DF-10 makes it normative for
`docs/` because that is where sweeps are most common, not because prose elsewhere
is exempt from the same failure.

### Witness 2 — #3002 (Diátaxis extraction, 2026-09-18)

A Diátaxis extraction copied a Mermaid diagram from
`docs/howto/activitypub/activities/acknowledge.md` onto a new `docs/topics/`
Explanation page.
Reading the copied diagram and its source page as sets of claims — not as page
furniture — exposed wrong AS2 verb attributions repeated across
`acknowledge.md`, `manage_case.md` and `report_vulnerability.md`:
`RmInvalidateReport` filed under `as:Reject` when its wire class is
`as_TentativeReject`, `RmCloseReport` filed under `as:Leave` when it is
`as_Reject`, and the post-validation state written `RM:VALIDATED` when the state
is `RM.VALID`.
The same pairing was wrong in several places at once, because each page had
copied it from the last.

Those defects had survived #2785, an earlier pass whose express purpose was
correcting accuracy errors in this same directory — but whose acceptance
criteria named four other pages, so it never read these.
Proximity to a prior accuracy sweep is not coverage by it.

The sharpest instance: `acknowledge.md` prose asserted that both report closures
were `as:Leave` subclasses, and no registered `ActivityPattern` pairs `Leave`
with a report — the only `Leave` pattern in
`vultron/wire/as2/extractor/_instances.py` pairs it with `VulnerabilityCase`.
Republished onto an Explanation page, whose job is to justify the design, that
sentence reads as implementation guidance.
Defects filed as #3395.

This particular class is now ratcheted: `test/architecture/test_docs_activity_verbs.py`
reads the verb each activity class and each registered `ActivityPattern` actually
declares, and fails when a `docs/` page pairs an activity with a different one
(#3402).
Note what the ratchet does *not* cover, which is the general case this note is
about: it checks one narrow family of claim — activity-to-verb pairings — and
only where the page writes them in one of two recognised shapes.
A ratchet for the claim class you just moved is the best possible outcome of a
sweep; it is not a substitute for reading.

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

Three mechanics matter, and getting any of them wrong costs more than the copy
would have.

**Placement.** Put the fragment where its hosts are — a `_<slug>.md` file
alongside the pages that include it, which is what the existing fragments do
(`docs/topics/process_models/cs/_events_sigma.md`,
`docs/reference/vultron-spec/includes/_rm-states-table.md`).
Reserve `docs/includes/` for banners included from across the whole tree
(`normative.md`, `not_normative.md`); its files carry no `_` prefix.

**Path.** The include argument resolves relative to the *including* file, never
to `docs/`.
`mkdocs.yml` configures the plugin with no `base_path`, and every existing
directive is relative — `{% include-markdown "./_events_sigma.md" %}`,
`{% include-markdown "../../../includes/normative.md" %}`.
A `docs/`-rooted argument fails the strict build.

**Lint scope.** A fragment is linted as source for sentence- and block-scoped
rules, while page-scoped rules — acronym first use, concept order, page
furniture — are evaluated against the assembled page instead (DF-09-007).
Quadrant, and so the voice rules, comes from every page that includes the
fragment rather than from the fragment's own directory (DF-09-008).
Until #3318 lands, `lint-docs` drops both `docs/includes/**` and `_*.md` from
its target set, so a fragment you create today is unlinted and its prose needs a
manual pass.
Extracting a fragment therefore moves prose *out* of automated lint scope, which
is one more reason the claims in it must be verified at the moment of the move.

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
