---
name: lint-docs
description: >
  Audit pages under docs/ against the Vultron documentation style guide. Fixes
  mechanical findings (spelling, acronym registration, filler, legacy mermaid
  syntax, isolated voice slips) and reports judgment findings (concept order,
  list discipline, quadrant misclassification) with a recommendation. Use after
  writing docs, as check-docs-sync's gate, or to audit an existing tree.
---

# Skill: Lint Docs

Semantic linter for hand-written `docs/` prose. Complements `format-markdown`
(mechanical markdown) and `build-docs` (link and nav validity) — this skill
checks what neither can see.

Rules and IDs: [`../shared/docs-style-guide.md`](../shared/docs-style-guide.md).
Normative anchor: `specs/diataxis-requirements.yaml` DF-09-001.

## Interface

| Invocation | Targets |
|---|---|
| no argument | Pages changed on this branch: `git diff origin/main...HEAD --name-only -- docs/` |
| explicit paths | Named files or directories, e.g. `lint-docs docs/howto/` |
| `--quadrant <name>` | The tree for one quadrant: `tutorial`, `howto`, `reference`, `explanation` |

**Returns**: the list of fixes applied and the findings reported.

### Auto-fix guard

Count the resolved target set before touching anything. **Above 20 files,
switch to report-only** and say so in the output. A large target set means an
audit, not an edit, and a 400-file prose diff is never the right output.

---

## Phase 1 — Resolve targets

Expand the invocation to a file list, then drop the exempt paths:

- `docs/adr/**` — MADR template, own conventions
- `docs/reference/code/**` — mkdocstrings-generated
- `docs/reference/case_states/**` — generated state pages
- `docs/includes/**`, `docs/_acronyms/**`, `docs/ns/**` — snippets and namespace files
- anything matching `not_in_nav`'s generated patterns (`*diagram*.md`, `*table*.md`,
  `_*.md`, `reference/user_stories/story_*.md`)

Report the target count and whether the auto-fix guard tripped.

## Phase 2 — Classify each page

Determine each page's Diátaxis quadrant from its tree and its content. The
quadrant selects the voice rules (SG-17 through SG-19) and the list exemption
(SG-31), so classification precedes every other check.

Where tree and content disagree, that is itself a Phase 4 finding.

## Phase 3 — Mechanical pass (fix)

Apply these directly, unless the auto-fix guard tripped:

| Check | Rule | Action |
|---|---|---|
| British spelling in prose | SG-37 | Replace. Skip filenames and ADR titles. |
| Banned glossary alias | SG-02 | Replace with the canonical term where unambiguous. |
| Acronym unexpanded at first use on the page | SG-07 | Insert the expansion. |
| Acronym missing from `_acronyms/index.md` | SG-08 | Add it in strict alphabetical order, case-insensitive. |
| Filler and hedging | SG-24 | Delete where the sentence survives it. |
| Legacy `graph` mermaid syntax | SG-35 | Rewrite as `flowchart`. |
| Isolated out-of-quadrant pronoun | SG-17–SG-19 | Rewrite that sentence for the quadrant's voice. |

"Isolated" means a small number of occurrences confined to one or two
sections. Pervasive drift is Phase 4, not Phase 3 — see SG-20.

## Phase 4 — Judgment pass (report)

Report these with the file, the line, the rule ID, and a recommended fix. Do
not apply them.

- **Concept order** (SG-10) — a section using a concept the page has not
  introduced. Name the forward reference and the section order that fixes it.
- **Unlinked first use** (SG-11) — a glossary or taxonomy term used without a
  link to its canonical introduction.
- **Unregistered term** (SG-04, SG-05) — domain vocabulary absent from both the
  glossary and the taxonomy.
- **Synonym drift** (SG-06) — two names for one concept on one page.
- **Sentence and paragraph shape** (SG-13–SG-16) — sentences well past 28 words
  carrying two claims; paragraphs past five sentences.
- **List discipline** (SG-28–SG-30) — bullets carrying argument rather than
  parallel members; unordered sets numbered; term/definition pairs as bullets
  where a table belongs. Skip how-to and tutorial bodies (SG-31).
- **Diagram warrant and standalone prose** (SG-32, SG-33) — a diagram with no
  adjacent sentence saying what it shows, or a decorative diagram.
- **Uncited normative claim** (SG-25) — "must" in explanation prose with no
  spec ID or ADR number.
- **Register** (SG-21–SG-23, SG-26, SG-27) — non-declarative opening, inflated
  `warning` admonitions, emphasis sprawl.
- **Grandfathered ASCII diagrams** (SG-36) — low priority; never auto-convert.

### Quadrant misclassification

Pervasive out-of-quadrant voice means the page may be the wrong Diátaxis type
(SG-20, DF-01-002). A how-to full of "we'll now explore" is a tutorial or an
explanation in the wrong tree; a tutorial full of "you should understand that"
is drifting into explanation.

Escalate with a recommendation: state which type the page actually is, whether
it should be relocated, split, or rewritten in place, and which you would
choose and why. Then ask for confirmation. Never swap the pronouns to hide it,
and never ask an open "what should I do with this page?".

## Phase 5 — Revalidate

If Phase 3 changed any file:

1. `format-markdown`
2. `build-docs` — `mkdocs build --strict`

Skip both when nothing was fixed.

## Phase 6 — Report

Output, in this order:

1. Target count, and whether the auto-fix guard tripped.
2. Fixes applied, grouped by rule ID, with file and line.
3. Findings reported, most consequential first, each with a recommended fix.
4. Any escalation awaiting a decision.
5. An explicit "no findings" statement when a page is clean.

---

## Constraints

- Never edit outside the resolved target set, except `docs/_acronyms/index.md`
  for SG-08 registration.
- Never apply a Phase 4 finding without confirmation. Those are judgment calls
  by construction.
- Above 20 target files, report only.
- Do not duplicate `format-markdown` or `build-docs` checks. Line length, list
  markers, emphasis style, and link validity belong to those tools; MD013 is
  disabled repo-wide and no line-length rule applies here (SG-38).
- Escalate with a recommendation, not an open question.
