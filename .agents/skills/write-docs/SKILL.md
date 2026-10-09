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
DF-01 through DF-10.

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
5. `notes/site-information-architecture.md` — the rules above the page: the
   stakeholder types (§ "Stakeholder type is not CVD role" and § "The
   stakeholder types"), the 100–500 level ladder (§ "Levels 100–500: a rule,
   not a label"), and how the nav and routing pages relate (§ "Routing: nav
   enumerates groups, routing pages carry leaves"). Phases 3 and 6 apply these;
   do not re-derive them from taste.

Load the DF requirements if not already in context:
`PYTHONPATH= uv run spec-dump --topic DF --text`.

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

Settle the page's frontmatter here, because the concept list decides it
(SG-40). Both keys are required on every reader-facing page (DF-11-001); a
working-record page declares `stakeholder_type: [project-contributor]` and no
`level` (DF-11-012); a fragment declares neither (DF-11-010):

- **`stakeholder_type`**: who the page is *addressed to* — not what it is about,
  and not who might find it useful. A list of members from
  `docs/includes/stakeholder_types.md`, or the bare scalar `ALL` when it is
  genuinely every type. This is a **stakeholder type, not a CVDRole**. A role
  (Reporter, Vendor, Coordinator, Deployer, …) is a position an actor holds in
  one case — assumable, inhabitable, temporal — and changes from case to case;
  a stakeholder type is why the reader is here and does not. No value appears
  in both vocabularies, so if you have written `vendor` or `coordinator` you have
  reached for the wrong list: a page *about* vendors addressed to someone
  building a tracker is `[platform-developer]`
  (`notes/site-information-architecture.md` § "Stakeholder type is not CVD
  role").
- **`level`**: the page's prerequisite level (100–500), read off the ladder in
  the note's § "Levels 100–500" — what the reader must already know, not how
  advanced the topic feels. A page's level must be at least the level of every
  page whose concepts it uses unlinked (DF-11-002). If the concept list forces
  a level higher than the intended reader can meet, the page is doing two jobs:
  split it, or link out (SG-11) instead of introducing.
- **`introduces:`**: the glossary terms for which this page is the canonical
  introduction. Leave a term out if another page already introduces it: check
  with `grep -rn "introduces:" docs/`, since a term has one introducer.
- **Links out**: for each concept the page uses but does not introduce, link
  its first use to the page that introduces it, or to its glossary entry.
  `docs-level-order` fails an unlinked use of a concept introduced above this
  page's level.

Write the section outline from that order. If the outline requires a forward
reference, the outline is wrong — reorder, or link out.

## Phase 4 — Draft

### Moved or republished content (sweeps)

If this page is being written as part of a sweep — a naming pass, a Diátaxis
extraction, a page split, or any task that moves existing prose from one
location to another — apply the following before writing any sentence drawn
from the source:

1. **Re-read each claim as an assertion**, not as furniture. A diagram or bullet
   that was unremarkable in its source context may be a falsifiable statement in
   the destination context.
2. **Verify each first-order empirical claim** against its authority: source
   code, a `specs/*.yaml` entry, or a `docs/reference/` page. Do not inherit
   correctness from the source location (DF-10-001).
3. **Prefer includes over copying.** When the same content belongs on two pages,
   create an `{% include-markdown %}` fragment rather than copying prose. One
   authoritative source, multiple render points — silent drift is structurally
   impossible (DF-10-002). Three mechanics:
   - **Placement** — a `_<slug>.md` file alongside the pages that include it.
     `docs/includes/` is reserved for whole-tree banners (`normative.md`) and its
     files carry no `_` prefix.
   - **Path** — relative to the *including* file, never rooted at `docs/`. There
     is no `base_path` configured, so `{% include-markdown "./_slug.md" %}` and
     `{% include-markdown "../../includes/normative.md" %}` are the shapes that
     resolve; a `docs/`-rooted argument fails the strict build.
   - **Lint scope** — a fragment is a `lint-docs` target in its own right, so
     pass it explicitly (or lint the branch diff, which includes it). Page-scoped
     rules belong to the assembled page, not the fragment (DF-09-007); quadrant
     comes from each host page (DF-09-008). See `lint-docs` § "Fragments and
     assembly units".

The move is not complete until every claim that is now a first-class assertion
on this page has been confirmed. Flag any claim that cannot be verified as a
finding rather than including it verbatim.

### Drafting rules

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
- **Never render the page's own `level` or `stakeholder_type`** — not in prose,
  a heading, an admonition, a badge, or the nav label (DF-11-004, DF-11-009).
  Say who the page is for in the reader's situation ("if you are wiring a
  tracker into a case"), never by the type's name; the level is invisible by
  design, so "this is a 300-level page" is a defect, not orientation.
- **Write the page for a deep-link arrival** (SG-44, DF-11-007). State the
  prerequisites and expand the acronyms even though the previous page in the
  nav already did. Do not thin an opening because a neighbor "already covers
  it": the reader who arrived from search never saw the neighbor.

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
3. If this page is the new term's canonical introduction, add it to the page's
   `introduces:` list, so lower-level pages that use it must link here.

Never coin a term without registering it.

## Phase 6 — Wire the nav

`mkdocs.yml` sets `validation.nav.omitted_files: warn`, and `build-docs` runs
`--strict`, so a page absent from the nav fails the build. Every new page must
be navved or explicitly listed under `not_in_nav`.

Nav order carries **dependency and prominence**, not narrative flow. A reader
does not read the nav top to bottom (SG-44), so the order is not a story; what it
encodes is which pages a page depends on and how prominent the group is on a
stakeholder type's path. That is what makes a slot reviewable: a page placed
before one it depends on is wrong, and a reviewer can check it from frontmatter
(`notes/site-information-architecture.md` § "Routing: nav enumerates groups,
routing pages carry leaves"; ADR-0102, DF-11).

**Derive the slot from the frontmatter settled in Phase 3, then propose it and
confirm it.** The recipe:

1. **Section** — the Diátaxis quadrant from Phase 2 picks the top-level section.
   Every section index that declares `contents: generated` is regenerated from
   frontmatter (`uv run docs-site --write`, DF-11-005); do not hand-edit a
   generated listing. The blurb beside a new page's link is its `description:`
   frontmatter, so write one. A new `index.md` that opens a nav group must
   declare `contents: generated | routing | rendered` or `docs-site --check`
   fails; a `routing` index must link every member of its section. The
   decision table is `notes/site-information-architecture.md`
   § "Sub-section index decisions".
2. **Group** — the page's `stakeholder_type` picks the group within the section:
   the group whose other pages address the same reader, or the routing page
   (`docs/start/*.md`, `docs/research/index.md`) that carries that type's path.
   A large set of sibling leaves goes behind a routing page rather than into the
   nav (DF-11-006).
3. **Position** — the page's `level` fixes the position inside the group: after
   every sibling whose level is lower and before every sibling whose level is
   higher, and never before a page it depends on (DF-11-002). Equal levels order
   by prominence on the reader's path, not by narrative.
4. **Label** — the label matches the H1 in substance (SG-39) and carries neither
   the level nor the stakeholder type (DF-11-004, DF-11-009).

Propose it as: section, group, the sibling it follows and the one it precedes,
the label, and one sentence naming the `level` and `stakeholder_type` that
justify each choice. Then ask for confirmation. Maintainer-facing pages
(`docs/developer/`, `docs/agents/`) are covered by existing `not_in_nav` patterns
and need no nav entry.

Two traps the note settles, restated because they recur: a page's own level and
stakeholder type are never rendered or navigated by (DF-11-004, DF-11-009), and
repeated openings on adjacent pages are **required** for deep-link arrivals —
never remove them to make neighbors read as a sequence (SG-44, DF-11-007).

## Phase 7 — Validate

In this order:

1. `lint-docs` on the pages written — fixes mechanical findings, reports the rest.
   Resolve every reported finding before proceeding.
2. `uv run docs-frontmatter` and `uv run docs-level-order`, the frontmatter and
   level-order gates the pre-commit hooks run. Both are site-wide, so a new
   `introduces:` term can also flag an existing lower-level page that uses it
   unlinked. Link that use; if the finding is on a page this change does not
   touch and linking it would collide with another task's ownership of that
   page, stop and ask rather than baselining it.
3. `format-markdown` — markdownlint-cli2 via `./mdlint.sh`.
4. `build-docs` — `mkdocs build --strict`, which must pass with no warnings
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
- Every reader-facing page declares `stakeholder_type` and `level` (DF-11-001)
  and renders neither (DF-11-004, DF-11-009). `stakeholder_type` is a reader
  type, never a CVDRole.
- Never leave a new page out of the nav without a `not_in_nav` match.
- Escalate judgment calls with a recommendation, not an open question. This
  applies to quadrant splits (Phase 2) and nav placement (Phase 6).
- Do not rewrite a page outside the requested scope. A page that needs work you
  were not asked for is a finding to report, not a change to make.
