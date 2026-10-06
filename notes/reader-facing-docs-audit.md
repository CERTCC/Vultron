---
title: Reader-Facing Docs Audit — Cross-Page Rulings
status: active
description: >
  Dated audit of every reader-facing docs/ page against the site information
  architecture (ADR-0102). The per-page routing ledger is archived (every
  remediation task closed); what stays are the judgments that cannot be made
  from inside one page — which overlapping page wins, inbound link counts, level
  violations, and missing pages.
related_notes:
  - notes/site-information-architecture.md
  - notes/documentation-sweeps.md
related_specs:
  - specs/diataxis-requirements.yaml
---

# Reader-Facing Docs Audit — Cross-Page Rulings

This note records the audit that #3526 commissioned. It routes pages and does
not prescribe fixes. Each remediation task re-reads its own pages with context
loaded and decides the fix there; see "Audit routes; the fix decides" in
`notes/site-information-architecture.md`. What this note *does* settle is the
set of judgments that cannot be made from inside a single page. A page-local
fixer MUST treat the rulings below as decided, not re-derive them.

**This is a dated record, not a live figure.** Audited 2026-09-24 against
`main` at `669560698`. Levels and stakeholder types were written into each
page's frontmatter in the same change, so the frontmatter, not this table, is
the standing answer for those two fields. When a remediation task changes a
page's audience or depth, it updates the frontmatter and leaves this table
alone (MS-16-001).

## Method

- **Scope.** Every published `docs/` page that `docs-frontmatter` classifies
  as reader-facing, excluding the four pages #3524 owns exclusively
  (`docs/index.md`, `topics/background/interoperability.md`,
  `topics/background/what-is-vultron.md`, `topics/capability_model/index.md`).
  That was 148 pages. Ten of them turned out to be project working record and
  were reclassified (see below), leaving 138 leveled pages.
- **Reading.** Six section readers each read their pages in full, in a single
  pass per page, applying all seven lenses of #3526: level, stakeholder type,
  constituent narrowing, register, nav enumeration, gap, and continuity.
  Repeated openings and re-expanded acronyms were *not* recorded as defects
  (DF-11-007).
- **Inbound links.** Counted as relative `](path.md)` links and
  `include-markdown` targets across `docs/**/*.md`, resolved against each
  source file's directory. Nav entries in `mkdocs.yml` and absolute URLs are
  not counted. Anchored links count toward the page they point into.
- **Level violations.** Computed from each reader's `depends_on` list: a
  concept used without introducing, defining, or linking it, pointing at a
  page with a higher declared level (DF-11-002).

## Headline numbers

| | Pages |
|---|---|
| Audited | 148 |
| Reclassified as working record | 10 |
| Leveled and tagged in frontmatter | 138 |
| Verdict `ok` | 67 |
| Verdict `revise` | 50 |
| Verdict `relocate` | 10 |
| Verdict `extract` | 9 |
| Verdict `split` | 6 |
| Verdict `merge` | 6 |
| Level 100 / 200 / 300 / 400 / 500 (leveled pages only) | 3 / 14 / 54 / 53 / 14 |
| In the nav but should sit behind a routing page | 18 (12 reader-facing, 6 now working record) |
| Upward level dependencies (DF-11-002) | 24 |

The level shape is inverted from the one ADR-0102 expects. `ALL` should be
heavy at 100 and thin out above it. Instead, three pages sit at 100, all of them
About boilerplate, and 107 of 138 sit at 300 or 400. The site has almost no
page that a reader who knows nothing about CVD or Vultron can start from,
apart from the four entry pages #3524 is rewriting.

## Constituent narrowing: no evidence to split `cvd-practitioner`

Thirty pages are addressed to `cvd-practitioner`. **None narrows** in its own
text to security researchers, vendor PSIRTs, or national CSIRTs/ISACs/ISAOs.
The only per-constituent content in the tree is
`topics/other_uses/roles_influence.md`, which is addressed to a
`process-researcher`. The split condition in
`notes/site-information-architecture.md` is therefore not met, and
`cvd-practitioner` stays whole. The more pressing finding runs the other way:
very little of the tree is addressed to practitioners at all (see "Missing
pages").

## Reclassified as working record

Ten pages the reader-facing schema had caught are, by DF-11-003's own
categories, project working record. `WORKING_RECORD_PATTERNS` in
`vultron/metadata/docs/page_schema.py` now names them:

- **Generated code documentation**: `reference/behaviors/**`, the four
  generated behavior-tree renderings and their index.
- **Contributor-facing material**: `reference/specs/project.md` and
  `reference/specs/process.md`, the generated Python-codebase and CI/agent
  requirements; `about/contributing.md`.
- **Retained design history**: `reference/ontology/index.md`, the tombstone for
  the unmaintained OWL files.
- **Requirements-traceability records**: `reference/user_stories/traceability.md`
  joins the 111 story pages. It is contributor-facing, with a hand-edit
  EDITOR NOTES block, a Line column, and gap analysis keyed to issue numbers.
  That makes it a working-record routing page in the same way as `adr/index.md`.
  DF-11-003 is amended to name user stories; `user_stories/index.md` is
  addressed to readers and stays leveled.

Tagging these (`[project-contributor]`, no level) and moving them behind their
routing door belong to #3528, together with the rest of the working record,
and #3528 did both: the door is `about/project_record.md`.

## Cross-page rulings

### Concept registries: four, not three

The Concern named three registries. There are four, and two of them claim
authority:

| Registry | What it is | Addressed to | Inbound files |
|---|---|---|---|
| `reference/vultron-spec/_terminology.md` (spec §2) | Normative protocol terms, including the role enumeration; says it is authoritative | `platform-developer` | via the spec |
| `reference/glossary.md` | The project's ubiquitous language: CVD terms beside hexagonal ports, DataLayer methods, work tracking, and dialogues | effectively `project-contributor` | 14 |
| `reference/terms.md` | The seven CVD-Guide roles plus Case, Participant, and Report; defers to the glossary as "canonical" | `cvd-practitioner` | 2 |
| `reference/vultron-taxonomy.md` | A concept-scope document: layers, capability sets and shapes, roles, planned views, dissolved concepts | `platform-developer`, `project-contributor` | 1 |

They disagree. Vendor is "synonymous with Supplier" in `terms.md` while the
glossary lists "supplier" as an alias to avoid. Coordinator has three different
definitions. The taxonomy counts five capability shapes including Sentinel,
while the glossary, spec Annex G, and ADR-0097 count four. The glossary gives
case states as both 32 and 40, and messages as 29 against 28 everywhere else.

**Ruling — division of labor:**

1. **Spec §2 wins every normative definition** of a protocol term. Where
   another registry defines the same term, it links to §2 rather than
   restating it. That is the only way a definition cannot drift.
2. **The glossary stays the registry of *names***: every term, the aliases to
   avoid for it, and its Flagged Ambiguities. Its protocol-term rows link to
   §2 for the normative definition. Its codebase vocabulary stays. The
   `glossary-index` tool and every agent skill read this file, so it is not
   renamed or moved.
3. **`terms.md` is merged into the glossary and retired.** Its CERT-Guide and
   ISO alignment notes survive as glossary content. Its two inbound links
   are repointed, which is cheap. Each role definition it carries is verified
   against §2 before it moves, not copied (DF-10-001).
4. **The taxonomy stays, as a scope document rather than a registry.** Its
   capability-set and capability-shape tables become links to spec §12 and
   Annex G, and the five-shape count is corrected to four.
5. **Count drift is settled against the spec**: the number of state machines,
   case states, and messages. `quick_reference.md` and `fv-demo-protocol.md`
   say three state machines where the spec says five (RM, EM, PEC, VFD, PXA).

### `topics/background/index.md`: what is extracted and what stays

The page is 211 lines titled "Vultron Contextualized". Section by section:

| Section | Neighbor that already carries it | Ruling |
|---|---|---|
| Prerequisites admonition | — (copy of `topics/index.md`'s) | Stays on the index |
| "New to Vultron?" tip | — | Stays on the index |
| Untitled CVD Guide quote ("who else needs to know what, and when") | none | Moves to the new page, as its opening |
| H2 "CVD Is MPCVD, and MPCVD Is CVD" (two diagrams, supply-chain argument, usage convention) | none; the glossary defines MPCVD as 3+ organizations, contradicting it | Moves to the new page; the glossary definition is reconciled with it (#3624) |
| H2 "Context of Our Recent Work" (four SEI source documents) | none | Moves to the new page |
| H2 "What We Mean by Protocol", part (a): dictionary definitions and protocol senses | `what-is-vultron.md` "Four Senses" | Folds into `what-is-vultron.md` (#3524's page) |
| H2 "What We Mean by Protocol", part (b): the narrative / prescriptive / normative triad | none | Moves to the new page, after the lineage it cites |
| Sidebar "Why Vultron?" (the Voltron name) | none | Folds into `what-is-vultron.md` (#3524); if #3524 declines it, it goes to the new page |

**The extracted page is titled "CVD as a Coordination Problem"**, at
`topics/background/cvd-coordination-problem.md`. That exact phrase is already
the link text for `background/index.md` in
`reference/vultron-spec/_introduction.md` and `_protocol-overview.md`, so both
links become correct by repointing, with no relabeling.

**The index keeps orientation and routing only**, retitled "Background": the
prerequisites admonition, the "New to Vultron?" pointer, and one line per
child in dependency order — `what-is-vultron.md`, then
`cvd-coordination-problem.md`, `interoperability.md`, and `cvd_success.md`.

### Other overlap rulings

Each is settled here because it spans several pages and a page-local fixer
would get it wrong.

- **Embargo negotiation before a case exists (ADR-0096).** The withdrawal
  reached only `model_interactions/rm_em.md`, and even that page still assumes
  the old rule in later sections. `reference/formal_protocol/transitions.md`
  (the EMB-01 note), `model_interactions/rm_em_cs.md` (Vendor Notification),
  and `em/defaults.md` still state it. These four pages are fixed together, by
  one task (#3620).
- **Case State transition grammar.** `cs/transitions.md` and
  `cs/model_definition.md` both give `VFdPxA → X VFDPXA`, which changes two
  letters in one step. The code allows one event per step
  (`vultron/core/states/cs_invariants.py`); the target is `VFdPXA`.
- **Case State subsection owners.** The states are stated on `cs_model.md`,
  the transitions and grammar on `cs/transitions.md`, and routing only on
  `cs/index.md`. `model_definition.md` and `events.md` duplicate them and have
  only 3 and 2 inbound links, so merging them away is cheap. `events.md`
  (500, a toy model) and `cs_model_limitations.md` (500) are research material
  that opens and closes the explanation path; they belong beside
  `topics/measuring_cvd/`.
- **EM, RM and PEC told three times.** The spec's state-machine sections win
  the normative content; `behavior_logic/use-cases/*` win the explanation;
  `process_models/em/participant-embargo-consent.md` is merged away (5 inbound
  links). The formal DFA in `em/index.md` and `rm/index.md` is checked against
  the spec before any new page is created for it — the spec may already carry
  it, in which case it becomes a link.
- **`reference/formal_protocol/` against `topics/process_models/`.** Formal
  protocol is Reference and process models is Explanation; where they
  disagree, the spec wins. The participant-state tuple order is unified to the
  spec's. The ~500 lines of state-space size estimates in
  `formal_protocol/states.md` are research content and leave the Reference page.
- **Case proposal.** `behavior_logic/use-cases/propose-case.md` is the fuller,
  current treatment and wins. `case_lifecycle/case_initialization.md` keeps
  only why the vendor does not create the case, plus pointers.
- **Conformance levels.** Spec §12.5's L1–L4 wins. The second L1–L4 definition
  in `howto/process_implementation.md`, which names L2 differently, becomes a
  link. `what-is-vultron.md`'s three-level scheme is reconciled by #3524.
- **Stub objects.** `message_semantics.md` and `actor-knowledge-model.md`
  define a stub's fields differently and neither links the other. The spec's
  definition wins and both link to it.
- **Who writes case state.** `activitypub/objects.md` and
  `messages/case_management.md` say the case owner; `ledger_replication.md`
  and the spec say the CASE_MANAGER. The spec wins (ADR-0088).
- **Actor discovery.** `future_work/_oq-actor-discovery.md` wins;
  `other_uses/cvd_directory.md` (a 2022 essay, and the one page in Other Uses
  that is not a use of the CS model) is merged into it.
- **Demo walkthroughs, five places.** `tutorials/fv-demo.md`,
  `tutorials/container_demos.md`, `howto/demos/fvv-demo.md`,
  `reference/fv-demo-protocol.md`, and `topics/scenarios/*` describe
  overlapping runs, and the first two describe the same default FV command
  differently. Division: a tutorial page carries the run-it-yourself steps for
  a scenario; `fv-demo-protocol.md` carries the message trace as Reference;
  `topics/scenarios/` carries per-scenario explanation behind its generated
  index. One task (#3622) owns all five, and resolves the contradiction against
  the running demo, not against either page (DF-10-001).
- **Future Work is not research.** `future_work/federation.md` and
  `open_questions.md` are addressed to `platform-developer` at 400. #3528's
  plan puts Future Work in the 500-level `process-researcher` section; it
  belongs on the adoption path instead, linked from the pages it extends
  (`case_ledger_sync.md`, `ownership_transfer.md`, `reference_architecture.md`).
  Settled in #3528: Future Work stays in Explanation, and the Research section
  carries only Measuring CVD and Other Uses.

## Inbound links: where a move is expensive

Most pages are cheap to move. The load-bearing targets, where a rename or
extraction must keep headings and anchors resolvable:

| Page | Inbound links | Files |
|---|---|---|
| `reference/specs/protocol.md` | 592 | 39 |
| `reference/vultron-spec/index.md` | 220 | 25 |
| `topics/process_models/rm/index.md` | 79 | 24 |
| `reference/formal_protocol/messages.md` | 47 | 14 |
| `topics/process_models/cs/index.md` | 44 | 23 |
| `topics/process_models/em/index.md` | 42 | 24 |
| `reference/formal_protocol/transitions.md` | 32 | 12 |
| `reference/formal_protocol/index.md` | 29 | 22 |

Both `em/index.md` and `rm/index.md` carry `extract` verdicts, and many of their
inbound links target section anchors. An extraction that leaves an anchor
unresolved is caught by `mkdocs build --strict` only for links it can see; the
fixer checks anchored inbound links explicitly.

Twenty-four audited pages have **zero** inbound links. They include all nine
scenario leaves, `quick_reference.md`, `benchmarking_mpcvd.md`, `em/split_merge.md`, and
`howto/demos/fvv-demo.md`; each is reached only through the nav.

## Level violations (DF-11-002)

Twenty-four upward dependencies. They cluster on two 400-level pages, which is
the finding: the concepts those pages introduce are needed at 300 and have no
300-level introduction.

| Depended-on page (level) | Dependents at a lower level |
|---|---|
| `topics/case_lifecycle/case_ledger_sync.md` (400) | 11: all nine scenario leaves, `tutorials/fv-demo.md`, `howto/demos/fvv-demo.md` |
| `topics/case_lifecycle/case_model.md` (400) | 5: the `initialize_case`, `invite_actor`, `manage_participants`, `role_delegation`, and `suggest_actor` how-tos |
| `topics/process_models/em/index.md` (400) | `em/negotiating.md` (300) |
| `topics/process_models/em/participant-embargo-consent.md` (400) | `howto/.../establish_embargo.md` (300) |
| `topics/process_models/rm/index.md` (400) | `tutorials/receive_report_demo.md` (300) |
| `topics/case_lifecycle/ownership_transfer.md` (400) | `model_interactions/index.md` (300) |
| `reference/formal_protocol/index.md` (400) | `topics/background/index.md` (200), `reference/fv-demo-protocol.md` (300) |
| `reference/formal_protocol/states.md` (400) | `reference/glossary.md` (300) |
| `reference/vultron-spec/index.md` (400) | `reference/activitypub/objects.md` (300) |

Linking out at first use satisfies the rule (SG-11), so most of these are
fixed where the dependent page lives. The two clusters are not: the CASE_MANAGER,
the case ledger, and replica fan-out need a 300-level introduction (see
"Missing pages"). `howto/activitypub/activities/_demo_prerequisites.md`, which
all thirteen activity guides include, is the one place a back-reference would
reach them all.

The formal DFA opening `em/index.md` and `rm/index.md` puts a 400 page first in
each nav group, ahead of the 300-level pages that use its shorthand. Extracting
it is what makes the order legal.

## Missing pages

Pages that do not exist and that some stakeholder type's path needs at the
point shown:

1. **A practitioner's view of a case under Vultron** (`cvd-practitioner`,
   ~200–300, Explanation): who owns the case, what each participant sees, what
   an embargo invitation asks of them — before ledger and wire detail begins.
   After `background/`, no Explanation page is addressed to a practitioner.
2. **A practitioner adoption path** (`cvd-practitioner`, Tutorial or How-to):
   every tutorial and how-to today is a developer exercise.
3. **A 300-level introduction to the case model and ledger**
   (`platform-developer`): the CASE_MANAGER, the replica, and fan-out, which 16
   lower-level pages currently need from 400-level pages.
4. **A capability set × role conformance matrix** (`platform-developer`,
   Reference): the taxonomy's View 3 promises it and spec §12 gives it only in
   prose.
5. **A standards-clause to normative-requirement crosswalk**
   (`cvd-practitioner`, Reference): the ISO and SSVC crosswalks map clauses to
   simulator-era `behavior_logic/` and `formal_protocol/` pages, never to spec
   sections.
6. **How a case split or merge is expressed in the protocol**
   (`platform-developer`): `em/split_merge.md` discusses the embargo side and
   has no inbound links.
7. **Running your own program's measurement** (`cvd-practitioner`): nothing
   turns the measuring-CVD models or action rules into guidance a program
   owner can apply.
8. **EM rules mapped to their wire activities** (`platform-developer`): no
   300-level EM page links `establish_embargo.md` or `manage_embargo.md`.
   This is links, not a page, and belongs to #3620.
