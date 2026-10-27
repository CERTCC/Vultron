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

The 111 pages under `docs/reference/user_stories/` are the only "why" a protocol
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
| Support level (`as of v0.4.0`) | Retired from every page and from the index legend. The index table and the traceability matrix are generated from the specs' `stories:` fields and show coverage instead | A dated judgment cannot stay true; nine of the eleven Out-of-scope stories are cited by requirements today. Coverage is a fact the registry already holds |
| Traceability matrix | Generated and gated by a check mode, like the other committed site artifacts (DF-11-005, DF-11-011) | Hand editing is how it reached 161 of 801 |
| A cited story must exist | Hard lint error when a `stories:` entry names a story page that is not in the catalog | Today only the ID pattern is checked, so a typo is a silent broken edge |
| How the protocol gap is worked | By spec-file area, one Task per area, worklist read from a per-file gap report; reuse an existing story first, add one only when none fits | One agent stays in one area of knowledge, worklists do not overlap, and the same cut the rationale backfill uses (#4483–#4486) means the same context serves both |
| Binding versus advisory tier | Every binding protocol requirement in an area gets a story; a `SHOULD`, `SHOULD_NOT` or `MAY` gets one where an existing story fits, and zero is not required | SR-11-003 gates the binding tier; SR-11-004 is advisory |
| A requirement no story can motivate | Apply the MS-12 decision tree and relabel; never add a `missing_story_reference` suppression | A protocol requirement that cannot be traced to a stakeholder need is usually misclassified (`notes/spec-authoring-rules.md`); MS-12-007 forbids new suppressions |
| Catch-all stories 088, 045, 014 | Split into narrower stories after the area drafting lands; old IDs stay as superseded pages; every citation is re-pointed by hand | A link that reaches 156 requirements barely answers "why does this one exist?" |
| Project and process requirements | May cite contributor and maintainer stories; a lint advisory names those with no story, aggregated per file; the written `rationale:` stays the required reason (#4482). No sweep of the existing corpus | Stories encourage the link without turning 1,888 requirements into a hard-error backlog |
| Bounty stories 055–057, 084, 085 | No change here. Their disposition follows the scope decision in #2563; generated coverage shows them as uncited until then | The scope decision is #2563's to make |

## Persona hierarchy

Each documentation stakeholder type (DF-11-001, glossary § Documentation
Audience) is the top of one persona family. A story's speaker is written at the
highest level of the family that includes every relevant party and no irrelevant
one, so "As a Participant" still means every CVD role, and "As a Vendor" means
one.

| Stakeholder type | Family (story voice) | Members |
|---|---|---|
| `cvd-practitioner` | **Participant** | the CVD roles: Reporter, Vendor, Coordinator, Deployer, Observer, CVE Numbering Authority, Case Owner, Case Manager (glossary § CVD Roles and Participants) |
| `platform-developer` | **Implementer** | **Peer Implementer** (builds a Vultron-compatible peer), **Node Operator** (runs a Vultron deployment), **Tool Author** (builds conformance suites, clients, or automated clients that consume the API) |
| `process-researcher` | **Researcher** | **Protocol Author** (writes or audits the protocol model), **Auditor** (reviews a case record after the fact) |
| `project-contributor` | **Contributor** | **Maintainer** (owns the repository's gates and releases), **Coding Agent** (an AI or scripted contributor working under the repository's rules), **Demo Operator** (runs the multi-actor demos to evaluate the protocol) |

Rules:

- The family name is the speaker when the story holds for every member. Name a
  member when it does not.
- Members are added when a story needs one, never speculatively. Demo Operator
  and Coding Agent are defined so the hierarchy is complete; no story is owed
  to them by this plan.
- Every persona name is registered in `docs/reference/glossary.md` by the seed
  task before a story uses it. Two names need care: the glossary lists "Agent"
  as an alias to avoid for **Actor** and "Operator" as an alias to avoid for
  **Deployer**. The compound names **Coding Agent** and **Node Operator** are
  registered as distinct terms with those rows cross-referenced, so the bare
  words keep their protocol meanings.
- A persona is a story speaker, not a `CVDRole` and not a `stakeholder_type`
  value; the three vocabularies stay disjoint except that the family rows above
  map one to one onto the stakeholder types.

## Story page shape

Every story page is a working-record page (DF-11-003): frontmatter declares
`stakeholder_type: [project-contributor]` and no `level` (DF-11-012),
`page_type` (DF-11-018) or `subject` (DF-11-025). The
story text sits between the `<!-- story-start -->` and `<!-- story-end -->`
markers so the generated table can quote it.

Pages added from 2026 on carry, under **Metadata**: the speaker (family and
member), the CVD roles it concerns where the speaker is a Participant, the
issue the story was drafted for, and the date added. They do not carry the
2022 fields (`Original ID`, `2022 Whitepaper ID`, `Potential future process or
service`) and no page carries a support level. A superseded page keeps its
story text and adds a **Superseded by** line listing the replacement IDs.

New story pages are reached the way existing ones are: the `not_in_nav` pattern
in `mkdocs.yml` already covers `reference/user_stories/story_*.md`, and the
generated index table and traceability matrix link every page (DF-11-006).

## Working the protocol story gap

The worklist for an area is the output of the gap report over that area's spec
files: every `kind: protocol` requirement with no `stories:`, grouped by file
and priority. The report replaces the hand-maintained lists in the Idea bodies
and the hand-off lists #3601 was to write into them.

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
   does the formatting-preserving edit. Never add one (MS-12-007).

Order relative to the rationale backfill: each drafting Task is blocked by the
rationale-backfill Task for the same files (#4483–#4486). Both edit the same
YAML items, so running them together guarantees conflicts, and a written
rationale tells the story author which need the requirement serves.

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
and are worth the pass even though the tier does not require it. The two `BW`
requirements are adjudication candidates and fold into the closing step rather
than a Task of their own.

## Seed stories

Distilled from the five Ideas' suggested framings and deduplicated. The seed
task writes these as pages, finalizing wording; the area tasks cite them before
adding new ones. Spec prefixes are the expected citers, not a commitment.

### Implementer family

- *Peer Implementer*: every response activity (Accept, Reject, TentativeReject)
  has one specified wire encoding, so that a peer interoperates without guessing.
  (RF, VAM)
- *Peer Implementer*: the wire mapping of every message semantic is specified,
  including acknowledgments and error signals that change no state, so that a
  peer knows which activities carry them and what receipt obliges. (MSM, VAM)
- *Peer Implementer*: datetimes and durations have one canonical wire
  serialization, so that interoperability does not rest on implementation
  choices. (DUR, CS)
- *Peer Implementer*: an unrecognized or malformed activity is handled by a
  specified rule — classified unknown, dead-lettered, or refused with a defined
  status — so that two conforming peers fail the same way. (VAM, MV, SE, IE)
- *Peer Implementer*: message handling is idempotent, so that duplicate delivery
  and retries converge on the same case state. (CM-13, MV-09, OX)
- *Peer Implementer*: a ledger entry is committed before the message announcing
  it is delivered, so that no recipient holds an announcement the canonical
  record lacks. (CM-16, CM-17, OX-03, CLP)
- *Peer Implementer*: every object reference resolves to a full URI that
  round-trips through storage, so that identity is stable across peers and
  restarts. (OID, VM)
- *Node Operator*: malformed, oversized or undecryptable requests are refused
  with specified HTTP statuses and structured error bodies, so that clients
  diagnose faults without operator help. (IE, ENC)
- *Node Operator*: every log entry carries the activity and actor identifiers it
  concerns, so that one protocol event can be followed through the system.
  (SL, IE-09)
- *Node Operator*: pending assertions and retries time out on documented
  defaults, so that stale state does not accumulate. (CLP-06, SYNC-05)
- *Tool Author*: the semantic pattern registry is complete, ordered and
  discriminating by rule, so that a conformance suite can verify that an
  implementation routes every activity to the right handler. (SE, VAM-01)
- *Tool Author*: every endpoint is discoverable in the published OpenAPI schema,
  so that a client can be generated without reading the source. (AR)

### Researcher family

- *Protocol Author*: the case state machine's forbidden states, ephemeral states
  and forced successors are stated as invariants, so that an implementation is
  checked against the model rather than against examples. (CSB-17–19, SM)
- *Auditor*: the case ledger is append-only, tamper-evident and written by one
  authority, so that disputes about what happened and when are settled by the
  record. (CLP, SYNC, VP-17, CM-02) — a candidate product of splitting story
  045.

### Participant family

- *Participant*: embargo deadlines are computed from one timezone-aware formula,
  so that expiry is unambiguous for every party. (DUR-06, CM-28)

### Contributor family

- *Contributor*: every requirement states why it exists and links to what
  motivated it, so that the system can be changed without breaking an unstated
  intent. (SR-11, MS-10, the rationale rule from #4482)
- *Maintainer*: lint and ratchet gates fail on new debt and not on inherited
  debt, so that the corpus improves without blocking unrelated work.
  (MS-12-007, MS-12-008, the growth guards from #4315)
- *Contributor*: the traceability record is generated and checked, so that no
  one hand-edits a matrix that drifts. (TRACE)

## Splitting the catch-all stories

Candidate axes; the splitting task decides the final set by reading the citing
requirements, not the other way round.

- **088** "maintain knowledge of the state of case and what options are
  available" (156): knowing the current case state; knowing which actions are
  available now; detecting and recovering loss of sync.
- **045** "produce a shared verified public record of case activity" (135):
  a record every participant shares; a record whose integrity can be verified;
  a record that becomes public on disclosure.
- **014** "negotiate embargo/disclosure schedules…" (128): proposing an
  embargo; revising one; accepting or rejecting a proposal; ending one.

Each citation is re-pointed to the narrowest new story that states its need. A
citation stays on the old ID only when the general reading is genuinely what
the requirement serves; the aim is zero. The old pages are marked superseded.

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

- **#4483–#4486** (rationale backfill by area) run first per area; see above.
  Where a contributor or maintainer seed story fits a project or process
  requirement they touch, they may cite it; the rationale is still the reason.
- **#4482** (rationale rule and growth guard) and **#4315** (PR-only growth
  guards replacing the count ceilings) build the helper the project/process
  story advisory and the closing step should reuse, so a guard is written once.
- **#3601** (adjudicating suppressed protocol specs) was to hand the five Ideas
  their worklists by hand. With the Ideas closed by this plan and the gap report
  in place, its hand-off acceptance criteria point at the area Tasks instead;
  its per-spec verdicts remain its own and are recorded in the Tasks' PRs when
  an area reaches them first.
- **Closing step** (SR-11-003 covers `MUST_NOT`, the MS-02-003 exception is
  removed, no `missing_story_reference` suppression remains): a Task of its own,
  blocked by the area Tasks, as the Epic's done-when already states.
- **#4481** (link-type meaning and direction) does not touch `stories:`, which
  is a field of its own (ADR-0072), not a `rel_type`.
