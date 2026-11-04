---
title: User Story Catalog — Personas, Identity, Coverage, and the Protocol Story Gap
status: active
kind: plan
tracks:
  - "#4506"
  - "#4507"
  - "#4508"
  - "#4510"
  - "#4512"
  - "#4513"
  - "#4514"
  - "#4516"
  - "#4517"
  - '#2717'
description: >
  Design decisions for the user-story catalog under docs/reference/user_stories/:
  the persona hierarchy and the rule for choosing a speaker, story identity and
  the no-reuse rule, why the dated support level is retired in favour of coverage
  generated from the specs' `stories:` fields, how the protocol story gap is
  worked by spec-file area, the seed stories distilled from the five SR-11 gap
  Ideas, how the three catch-all stories are split, and how contributor stories
  relate to project and process requirements. Plan source: #4487 and #2596–#2600.
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

# User Story Catalog — Personas, Identity, Coverage, and the Protocol Story Gap

The pages under `docs/reference/user_stories/` are the only "why" a protocol
requirement can cite (SR-11). This note records how the catalog is kept and how
the protocol requirements that have no story get one. The planning decisions
were made on 2026-10-12 from the Concern #4487 and the five SR-11 gap
Ideas #2596–#2600; the measurements below are from the same day.

## What was measured

| Fact | Figure (2026-10-12) |
|---|---|
| Protocol requirements with no `stories:` | 488 of 1,286 |
| … of which binding (`MUST` 135, `MUST_NOT` 128) | 263 |
| … of which advisory tier (`SHOULD`, `SHOULD_NOT`, `MAY`) | 225 |
| `missing_story_reference` suppressions (all `kind: protocol`: 135 `MUST`, 4 `MUST_NOT`, 2 `MAY`) | 141 (ratchet ceiling) |
| Requirements citing a story (798 protocol, 3 project) | 801 |
| Requirement IDs the hand-edited traceability matrix links | 161 |
| Stories whose text starts "As a Participant" | 84 of 111 |
| Citations carried by stories 088, 045 and 014 together | 419 |
| Stories no requirement cites (all five about bounties) | 5 |

Two of those rows are the reason this note exists. The matrix that TRACE-01
calls the traceability record links one fifth of the requirements that
actually carry a story: it was hand-edited after ADR-0072 made the spec files
authoritative, so it can only drift. And the five Ideas each carry a spec list
from the 2026-08-25 mapping pass; about a third of the IDs on those lists have
since been relabeled to `kind: project` or deleted, so the lists cannot drive
the work. The spec registry can.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Who may speak in a story | A persona from the hierarchy below; the speaker is the highest level that includes every relevant party and no irrelevant one | "Participant" already works this way for the CVD roles; the same shape covers implementers and contributors without long lists |
| New story IDs | `story_<year added>_NNN`, numbered from 001 within the year; `story_2022_*` is frozen | SR-11-002's pattern already allows any year; the year says which catalog generation a story belongs to |
| Retiring a story | Never. A story that is split or withdrawn keeps its page, marked superseded with the IDs that replace it, and its ID is never reused | A `stories:` reference in a spec must resolve for as long as any revision of that spec exists |
| Support level (`as of v0.4.0`) | Retired from every page and from the index legend. The index table and the traceability matrix are generated from the specs' `stories:` fields and show coverage instead | A dated judgment cannot stay true; most of the stories it marks Out-of-scope are cited by requirements today. Coverage is a fact the registry already holds |
| Traceability matrix | Generated and gated by a check mode, like the other committed site artifacts (TRACE-01-001, TRACE-03-003; built in #4506) | Hand editing is how it reached 161 of 801 |
| A cited story must exist | Hard lint error, not suppressible, when a `stories:` entry names a story page that is not in the catalog (TRACE-03-001; built in #4506) | Checking only the ID pattern makes a typo a silent broken edge |
| A story page is never removed | A PR-only guard fails a branch that deletes one; a superseded story keeps its page (TRACE-03-002; built in #4506) | A `stories:` entry must resolve for every revision of its citers, and a freed ID can be reused |
| How the protocol gap is worked | By spec-file area, one Task per area, worklist read from a per-file gap report; reuse an existing story first, add one only when none fits | One agent stays in one area of knowledge, worklists do not overlap, and the same cut the rationale backfill uses (#4483–#4486) means the same context serves both |
| Binding versus advisory tier | Every binding protocol requirement in an area gets a story; a `SHOULD`, `SHOULD_NOT` or `MAY` gets one where an existing story fits, and zero is not required | SR-11-003 gates the binding tier; SR-11-004 is advisory |
| A requirement no story can motivate | Apply the MS-12 decision tree and relabel; never add a `missing_story_reference` suppression | A protocol requirement that cannot be traced to a stakeholder need is usually misclassified (`notes/spec-authoring-rules.md`); MS-12-007 forbids new suppressions |
| Catch-all stories 088, 045, 014 | Split into narrower stories after the area drafting lands; old IDs stay as superseded pages; every citation is re-pointed by hand | A link that reaches 156 requirements barely answers "why does this one exist?" |
| Project and process requirements | May cite contributor and maintainer stories; `spec-lint` prints one `[INFO] no_project_process_story:` summary line per file (lint code `no_project_process_story`, opt-in IDs via `--list-no-story-ids`); the written `rationale:` stays the required reason (#4482). No sweep of the existing corpus | Stories encourage the link without turning 1,888 requirements into a hard-error backlog |
| Bounty stories 055–057, 084, 085 | No change here. Their disposition follows the scope decision in #2563; generated coverage shows them as uncited until then | The scope decision is #2563's to make |

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

The worklist for an area is the output of the gap report over that area's spec
files: every `kind: protocol` requirement with no `stories:`, grouped by file
and priority. Read it with `uv run story-gaps --list <FILE-OR-PREFIX>...`
(TRACE-03-004); without `--list` it prints one summary line per spec file, and
a `[suppressed]` mark names a requirement still carrying
`lint_suppress: [missing_story_reference]`. The report replaces the
hand-maintained lists in the Idea bodies and the hand-off lists #3601 was to
write into them.

For each requirement in the worklist:

1. **Reuse first.** If an existing story, including a seed story below, states
   the need this requirement serves, cite it. Several requirements citing one
   narrow story is the intended shape; one story cited by a hundred is the
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

Order relative to the rationale backfill: the rationale backfill for every
area (#4483–#4486) is complete, so no drafting Task waits on it. Every
requirement now carries a rationale (SR-02-009), and it tells the story author
which need the requirement serves.

### Areas and their binding worklists

Measured 2026-10-12; the gap report is authoritative at execution time.

| Area (mirrors the rationale backfill) | Spec prefixes with binding gaps | Binding |
|---|---|---|
| Core protocol text (#4483 files) | MSM 12, ASK 8, DUR 8, AKM 5, EP 4, OID 4, VP 3, ENC 3, LST 3, SDO 3, RF 2 | 55 |
| Ledger and replication (#4484 files, part 1) | CLP 31, SYNC 17, PCR 13, VAM 8, CBT 4, VM 4 | 77 |
| Case management and state machines (#4484 files, part 2) | CM 25, CSB 13, RSH 12, EMB 10, SM 5, PRM 4, CP 4, RMB 3 | 76 |
| Implementation architecture (#4485 files) | SE 15, MV 10, IE 8, TRIG 6, BT 4, OX 3, AR 2, SL 2, BTND 1, EDF 1, CS 1 | 53 |
| Tooling, process and demos (#4486 files) | BW 2 | 2 |

The core protocol area also holds 90 advisory-tier `VP` requirements with no
story: the protocol specification itself. Most should map to existing stories
and are worth the pass even though the tier does not require it.

## Seed stories

The seed stories distilled from the five SR-11 gap Ideas and #4487 are
`story_2026_010`–`story_2026_027` (#4507). The area Tasks cite them before
adding new ones; the prefixes are the expected citers, not a commitment.

| Stories | Speaker | Expected citers |
|---|---|---|
| 010, 011, 012 | Peer Implementer: response encoding, semantic wire mapping, datetime serialization | RF, VAM, MSM, DUR, CS |
| 013, 014 | Peer Implementer: malformed-activity rule, idempotency | VAM, MV, SE, IE, CM-13, OX |
| 015, 016 | Peer Implementer: commit before announce, URI round-trip | CM-16, CM-17, OX-03, CLP, OID, VM |
| 017, 018, 019 | Node Operator: HTTP error statuses, log identifiers, timeouts | IE, ENC, SL, CLP-06, SYNC-05 |
| 020, 021 | Tool Author: semantic registry, OpenAPI schema | SE, VAM-01, AR |
| 022 | Protocol Author: case state invariants | CSB-17–19, SM |
| 023 | Auditor: append-only single-writer ledger (took part of 045) | CLP, SYNC, VP-17, CM-02 |
| 024 | Participant: timezone-aware embargo deadlines | DUR-06, CM-28 |
| 025, 026, 027 | Contributor / Maintainer: requirement rationale, ratchet gates, generated traceability | SR-11, MS-10, MS-12-007, MS-12-008, TRACE |

## Splitting a catch-all story

A story that many unrelated requirements cite answers "why does this
requirement exist?" for none of them, so it is split. Read the citing
requirements to choose the narrower stories. Candidate axes are a start, not a
closed set: each of the three #4516 splits needed axes the candidate list
lacked. Re-point onto an existing story before writing a new page.

Each citation is re-pointed to the narrowest story that states its need, or
dropped when the requirement already cites one. A citation stays on the old ID
only when the general reading is genuinely what the requirement serves; the aim
is zero. The old pages are marked superseded.

## Implementation Tasks

Created 2026-10-12 under Epic #2717, in dependency order; each is blocked by the
ones it reads from.

| Task | Does | Runs after |
|---|---|---|
| #4506 | Generated table and matrix, cited-story-exists lint, `story-gaps` report, TRACE spec amendments | — |
| #4507 | Persona hierarchy in the glossary, seed `story_2026` pages, support level retired | #4506 |
| #4514 | Per-file advisory for project and process requirements with no story | #4507 |
| #4508 | Drafting: core protocol text | #4507, #4483 |
| #4510 | Drafting: ledger and replication | #4507, #4484 |
| #4512 | Drafting: case management and state machines | #4507, #4484 |
| #4513 | Drafting: implementation architecture | #4507, #4485 |
| #4516 | Split catch-all stories 088, 045, 014 | the four drafting Tasks |
| #4517 | Gate covers `MUST_NOT`; last suppressions retired | the four drafting Tasks |

## Relation to other work under the Epic

- **#4483–#4486** (rationale backfill by area) are complete; see above.
  Where a contributor or maintainer seed story fits a project or process
  requirement they touch, they may cite it; the rationale is still the reason.
- **#4482** (rationale rule) and **#4315** (PR-only growth
  guards replacing the count ceilings) build the helper the project/process
  story advisory reuses, so a guard is written once.
- **#3601** (adjudicating suppressed protocol specs) was to hand the five Ideas
  their worklists by hand. With the Ideas closed by this plan and the gap report
  in place, its hand-off acceptance criteria point at the area Tasks instead;
  its per-spec verdicts remain its own and are recorded in the Tasks' PRs when
  an area reaches them first.
- **#4481** (link-type meaning and direction) does not touch `stories:`, which
  is a field of its own (ADR-0072), not a `rel_type`.
