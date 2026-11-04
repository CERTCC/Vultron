---
title: User Story Catalog — Speakers, Identity, Coverage, and Citing a Story
status: active
kind: guidance
description: >
  Rules for the user-story catalog under docs/reference/user_stories/: the
  persona hierarchy and the rule for choosing a speaker, story identity and the
  no-reuse rule, why coverage is generated from the specs' `stories:` fields,
  how a requirement with no story gets one, how a catch-all story is split,
  and how contributor stories relate to project and process requirements.
related_specs:
  - specs/traceability.yaml
  - specs/spec-registry.yaml
  - specs/meta-specifications.yaml
  - specs/diataxis-requirements.yaml
related_notes:
  - notes/spec-authoring-rules.md
  - notes/site-information-architecture.md
  - notes/specs-vs-adrs.md
---

# User Story Catalog — Speakers, Identity, Coverage, and Citing a Story

The pages under `docs/reference/user_stories/` are the only "why" a protocol
requirement can cite (SR-11). This note holds the rules for keeping the catalog
and for giving a requirement a story.

## Rules

- **Who may speak.** A persona from the hierarchy below; the speaker is the
  highest level that includes every relevant party and no irrelevant one.
  "Participant" already works this way for the CVD roles, and the same shape
  covers implementers and contributors without long lists.
- **New story IDs** are `story_<year added>_NNN`, numbered from 001 within the
  year; `story_2022_*` is frozen. SR-11-002's pattern allows any year, and the
  year says which catalog generation a story belongs to.
- **A story is never retired.** A story that is split or withdrawn keeps its
  page, marked superseded with the IDs that replace it, and its ID is never
  reused, because a `stories:` reference must resolve for as long as any
  revision of its spec exists. A PR-only guard fails a branch that deletes a
  story page (TRACE-03-002).
- **Coverage is generated, never hand-edited.** The index table and the
  traceability matrix are built from the specs' `stories:` fields and gated by
  `docs-site --check` (TRACE-01-001, TRACE-03-003). A hand-edited matrix drifts;
  the old one linked a fifth of the requirements that carried a story. No page
  carries a dated support level: coverage is the fact the registry holds.
- **A cited story must exist.** A `stories:` entry naming a page not in the
  catalog is a hard, unsuppressible lint error (TRACE-03-001); checking only
  the ID pattern makes a typo a silent broken edge.
- **Binding versus advisory tier.** Every binding protocol requirement gets a
  story (SR-11-003 gates it); a `SHOULD`, `SHOULD_NOT` or `MAY` gets one where an
  existing story fits, and zero is not required (SR-11-004).
- **A requirement no story can motivate is relabeled, never suppressed.** Apply
  the MS-12 tree in `notes/spec-authoring-rules.md`; a protocol requirement that
  cannot be traced to a stakeholder need is usually misclassified, and
  MS-12-007 forbids new `missing_story_reference` suppressions.
- **Project and process requirements** may cite contributor and maintainer
  stories; the written `rationale:` stays the required reason (#4482).
  `spec-lint` prints one `[INFO] no_project_process_story:` summary line per
  file (opt-in IDs via `--list-no-story-ids`), which encourages the link without
  turning every such requirement into a hard-error backlog.

## Persona hierarchy

The glossary's § Story Personas is the registry of persona names, the
speaker rule, and the family-to-stakeholder-type mapping
(`docs/reference/glossary.md`); the catalog index restates them for readers.
Rules for extending it:

- Add a member only when a story needs one, never speculatively; register it
  in the glossary before a story uses it. Demo Operator and Coding Agent exist
  so the hierarchy is complete, and no story is owed to them.
- A persona name that collides with an alias to avoid ("Agent" for Actor,
  "Operator" for Deployer, "Researcher" for Finder, "maintainer" for Vendor)
  is registered as a distinct term with the colliding row cross-referenced,
  so the bare word keeps its protocol meaning.
- A persona is a story speaker, not a `CVDRole` and not a `stakeholder_type`
  value; do not add persona names to `StakeholderType`.

## Story page shape

The catalog index § Adding a Story states the page shape, and
`test/metadata/docs/test_story_pages.py` enforces it on every page (the
`story-page-shape` pre-commit hook and its step in spec-check.yml).
The test checks that the Metadata labels are present, not what they say.
What it cannot check:

- A superseded page keeps its story text and adds a **Superseded by** line
  listing the replacement IDs (TRACE-03-002).
- Metadata labels keep the order `story_2026_001` onward uses: Speaker, Roles
  (Participant speaker only), Related issues, Drafted for, Added.

## Working the protocol story gap

The worklist is the output of the gap report over the spec files being
worked: every `kind: protocol` requirement with no `stories:`, grouped by file
and priority. Read it with `uv run story-gaps --list <FILE-OR-PREFIX>...`
(TRACE-03-004); without `--list` it prints one summary line per spec file, and
a `[suppressed]` mark names a requirement still carrying
`lint_suppress: [missing_story_reference]`.

For each requirement in the worklist:

1. **Reuse first.** If an existing story states the need this requirement
   serves, cite it. Several requirements citing one narrow story is the
   intended shape; one story cited by a hundred is the
   catch-all problem.
2. **Add a story only when none fits.** Write it at the right level of the
   hierarchy, give it the next ID for the year, and cite it.
3. **Relabel when no stakeholder need exists.** A requirement that states a
   code-organization, test-coverage or build fact is not protocol. Apply the
   MS-12 tree in `notes/spec-authoring-rules.md`, correct `kind:`, and add a
   `verification:` clause if the move requires one (MS-10-008). Record the
   verdict in the PR.
4. **Remove the suppression** when a story is added; `scripts/apply_story_mappings.py`
   does the formatting-preserving edit. Never add one (MS-12-007). That script
   edits only items that carry the suppression; for an unsuppressed item, give
   `scripts/relabel_spec_kinds.py` `{"kind": null, "stories": [...]}`, which
   handles both shapes.

## Splitting a catch-all story

A story that many unrelated requirements cite answers "why does this
requirement exist?" for none of them, so it is split. Read the citing
requirements to choose the narrower stories. Candidate axes are a start, not a
closed set: each of the three #4516 splits needed axes its candidate list
lacked. Re-point onto an existing story before writing a new page.

Each citation is re-pointed to the narrowest story that states its need, or
dropped when the requirement already cites one. A citation stays on the old ID
only when the general reading is genuinely what the requirement serves; the aim
is zero. The old pages are marked superseded.

A story's need is what its citers serve, not the message type they mention.
A wire-form requirement cites the story whose need the message carries (an
embargo decision's wire form cites the decision story), not a story about wire
mappings in general; a story keyed on a message type grows into the next
catch-all (#4516).
