---
name: write-docs
description: >
  Author or rewrite a page under docs/ — classify its Diátaxis quadrant, plan
  concept order, draft it against the Vultron documentation style guide,
  register new terms and acronyms, wire mkdocs.yml nav, and validate. Use when
  asked to write, add, or rewrite documentation, or when check-docs-sync
  identifies a docs change too large for an inline edit.
---

# Skill: Write Docs

Authors hand-written pages under `docs/` — the published Diátaxis quadrants
plus the maintainer-facing `docs/developer/` and `docs/agents/` trees.

Rules live in [`../shared/docs-style-guide.md`](../shared/docs-style-guide.md)
(`SG-nn` rule IDs). Normative anchors: `specs/diataxis-requirements.yaml`
DF-01 through DF-09.

Out of scope: `docs/adr/` (use `create-architectural-decision-record`),
generated trees (`docs/reference/code/`, `docs/reference/case_states/`),
`notes/`, and `specs/`.

## Interface

| Parameter | Description |
|---|---|
| `topic` | What the page must cover. Required. |
| `quadrant` | `tutorial`, `howto`, `reference`, or `explanation`. Inferred if omitted. |
| `target` | Existing page to rewrite. Omit to create a new page. |
| `mode` | `pr` (default when invoked conversationally) or `inline` (leave changes in the caller's branch) |

**Returns**: the list of pages written, plus the PR URL in `pr` mode.

---

## Phase 1 — Load context

Read, in order:

1. `.claude/skills/shared/docs-style-guide.md` — the rules.
2. `docs/reference/glossary.md` — canonical terms and banned aliases (SG-01, SG-02).
3. `docs/reference/vultron-taxonomy.md` — concept names (SG-03). Skim the Quick
   Reference table unless the page is about a taxonomy concept.
4. `docs/_acronyms/index.md` — which acronyms are already registered (SG-08).

Load the DF requirements via `load-specs` if not already in context.

Do not read exemplar pages wholesale. The style guide's section 6 carries the
register; read a specific page only when this page must align closely with it.

## Phase 2 — Classify the quadrant

Apply the Diátaxis compass (`notes/diataxis-framework.md` §6):

- Action + acquisition → **tutorial**
- Action + application → **how-to**
- Cognition + application → **reference**
- Cognition + acquisition → **explanation**

The classification decides voice (SG-17 through SG-19), list discipline
(SG-31), and which tree the page lands in. Get it right before drafting.

### Cross-quadrant requests

DF-01-003 forbids mixing content types on one page. A request like "document
the embargo lifecycle" often spans quadrants: an explanation of why embargoes
work the way they do, a how-to for negotiating one, and a reference table of EM
states.

When the topic spans quadrants, **recommend a split and ask for confirmation**:
name each page, its quadrant, its path, and the cross-links between them. Do
not silently write one blended page, and do not ask an open "how should I
structure this?".

## Phase 3 — Plan concept order

Before writing prose, list the concepts the page must introduce and order them
so each depends only on what precedes it (SG-10). Concepts the page will not
introduce get a link to their canonical introduction instead (SG-11).

Write the section outline from that order. If the outline requires a forward
reference, the outline is wrong — reorder, or link out.

## Phase 4 — Draft

Write against the style guide. The rules that most often get missed:

- Voice by agency for the quadrant (SG-17, SG-18, SG-19) — a reference page
  makes the system the grammatical subject and never instructs.
- Expand each acronym at first use on this page (SG-07).
- Link each glossary or taxonomy term at first use (SG-11).
- One sentence per line (SG-38).
- Bullets only for parallel members of a set; tables for pairs (SG-28, SG-30).
- A diagram only where it earns its place, with a prose sentence stating what
  it shows (SG-32, SG-33).
- Cite spec IDs and ADR numbers for normative claims (SG-25).
- American spelling (SG-37), sentence-case H2s (SG-39).

Page furniture per SG-41: H1, a two-to-four sentence orientation paragraph,
`---`-separated sections, and a `## Summary` table and/or `## Further reading`
list where a recap helps.

## Phase 5 — Register terms and acronyms

1. Any acronym used and not present in `docs/_acronyms/index.md` gets added
   there, in strict alphabetical order, case-insensitive (SG-08). Do not order
   by length — the `abbr` extension sorts its own list, so file position does
   not affect which abbreviation matches.
2. Any durable domain term the page introduces gets a `glossary.md` entry with
   a definition and its aliases to avoid (SG-05). For a term that needs
   discussion rather than a definition, invoke `ubiquitous-language`.

Never coin a term without registering it.

## Phase 6 — Wire the nav

`mkdocs.yml` sets `validation.nav.omitted_files: warn`, and `build-docs` runs
`--strict`, so a page absent from the nav fails the build. Every new page must
be navved or explicitly listed under `not_in_nav`.

Nav order carries reading order, so **propose the slot and confirm it**: name
the section, the position within it, and the label, with one sentence of
reasoning. Maintainer-facing pages (`docs/developer/`, `docs/agents/`) are
covered by existing `not_in_nav` patterns and need no nav entry.

## Phase 7 — Validate

In this order:

1. `lint-docs` on the pages written — fixes mechanical findings, reports the rest.
   Resolve every reported finding before proceeding.
2. `format-markdown` — markdownlint-cli2 via `./mdlint.sh`.
3. `build-docs` — `mkdocs build --strict`, which must pass with no warnings
   (PD-04-001).

## Phase 8 — Deliver

- `mode: pr` — commit via `commit`, then invoke `create-pr` with
  `type: docs` and the `specs-notes` label where specs changed.
- `mode: inline` — leave the changes staged in the caller's branch and return
  the list of pages written. The caller owns the commit and the PR.

---

## Constraints

- Only write under `docs/`, plus `docs/_acronyms/index.md`, `glossary.md`, and
  `mkdocs.yml`. Do not modify code, tests, or `specs/`.
- One page, one quadrant (DF-01-002, DF-01-003). Split rather than blend.
- Never leave a new page out of the nav without a `not_in_nav` match.
- Escalate judgment calls with a recommendation, not an open question. This
  applies to quadrant splits (Phase 2) and nav placement (Phase 6).
- Do not rewrite a page outside the requested scope. A page that needs work you
  were not asked for is a finding to report, not a change to make.
