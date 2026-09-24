---
title: Reader-Facing Docs Audit — Routing Ledger and Cross-Page Rulings
status: active
description: >
  Dated audit of every reader-facing docs/ page against the site information
  architecture (ADR-0102): each page's level, stakeholder type, verdict and
  owning remediation task, plus the judgments that cannot be made from inside
  one page — which overlapping page wins, inbound link counts, level
  violations, and missing pages.
related_notes:
  - notes/site-information-architecture.md
  - notes/documentation-sweeps.md
related_specs:
  - specs/diataxis-requirements.yaml
---

# Reader-Facing Docs Audit — Routing Ledger and Cross-Page Rulings

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
routing door belong to #3528, together with the rest of the working record.

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

## Remediation partition

Remediation is cut by page, and each task owns its files exclusively. Nav
edits are never done in parallel: `mkdocs.yml` is held by #3528 and then by the
nav task (#3627), one after the other. A `relocate` verdict is a nav change, so it
belongs to the nav task. No page is moved on disk.

| Task | Owns |
|---|---|
| #3619 (R1) — Background | `topics/background/index.md`, `cvd_success.md`, the new `cvd-coordination-problem.md`, and the two repointed links in `vultron-spec/_introduction.md` and `_protocol-overview.md` |
| #3620 (R2) — Process models and formal protocol | `topics/process_models/**`, `reference/formal_protocol/**` |
| #3621 (R3) — Case lifecycle and protocol explanation | `topics/case_lifecycle/**`, `topics/behavior_logic/index.md` and `use-cases/**`, `protocol_flow.md`, `message_semantics.md`, `activity_vocabulary_design.md`, `actor-knowledge-model.md`, `reference_architecture.md`, missing page 3 |
| #3622 (R4) — Demos, tutorials, and scenarios | `tutorials/*` except the landing page, `howto/demos/**`, `reference/fv-demo-protocol.md`, `topics/scenarios/**` |
| #3623 (R5) — How-to guides, About, namespace | `howto/activitypub/**`, `howto/case_object.md`, `howto/process_implementation.md`, `howto/wire_capability.md`, `about/*`, `ns/index.md` |
| #3624 (R6) — Concept registries | `reference/glossary.md`, `terms.md`, `vultron-taxonomy.md`, `notation.md`, `quick_reference.md` |
| #3625 (R7) — Wire and protocol reference | the rest of `reference/` that is reader-facing, missing pages 4 and 5 |
| #3626 (R8) — Research | `topics/measuring_cvd/**`, `topics/other_uses/**`, `topics/future_work/**`, missing page 7 |
| #3627 (Nav) | `mkdocs.yml`: level order within each group, the 12 reader-facing pages that should sit behind a routing page, and every `relocate` verdict. Blocked by #3528. |
| #3628 (Practitioner pages) | missing pages 1 and 2. Blocked by #3524, whose entry pages route to them. |

The four section landing pages (`topics/`, `reference/`, `tutorials/`,
`howto/index.md`) belong to #3527's generator and are in no remediation task.

## Routing ledger

One row per audited page, grouped by owning task. **Evidence** is the
reader's one-line reason for the verdict; **Continuity** is a missing
transition or back-reference, where one was found. Neither is a prescription.
Level and addressed-to were true on 2026-09-24; the page's frontmatter is the
current value.

### #3619 (R1) — Background

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `topics/background/cvd_success.md` | 200 | cvd-practitioner, process-researcher | revise | 4 | Twelve D/F/V/P/X/A ordering preferences in ≺ notation drawn from the 2021 report; never says how a coordinator would use them in a case. | Opens with 'some notation is necessary to proceed here' as if read after background/index.md; no transition to the case-lifecycle pages that act on these goals. |
| `topics/background/index.md` | 200 | cvd-practitioner, process-researcher | extract | 5 | 211-line essay titled 'Vultron Contextualized' on an index: CVD Guide quote, two mermaid role diagrams, CVD⇔MPCVD convention, SEI report lineage, OED protocol definitions. | Lineage and OED sections read as a report preface ('we offer this documentation as a proposal') and hand off to nothing; no link to cvd_success.md or interoperability.md. |

### #3620 (R2) — Process models and formal protocol

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `reference/formal_protocol/conclusion.md` | 400 | platform-developer, process-researcher | ok | 1 | Symbol table plus RM/EM/CS summary diagrams recapping the quadruple; a clean reference summary with links back to each defining page. | Ends on a worked-example tip; nothing points the reader on to the wire-level mapping in reference/messages/ that a platform developer needs next. |
| `reference/formal_protocol/index.md` | 400 | platform-developer, process-researcher | extract | 29 | An index.md that carries the Brand-Zafiropulo protocol and global-state definitions and a 'Number of Processes' content section, not only orientation and routing. | — |
| `reference/formal_protocol/messages.md` | 400 | platform-developer | ok | 47 | Normative tables of the 28 formal message types with emit-when conditions, and AS2 notes that bridge to the wire vocabulary and fault/ack pages. | — |
| `reference/formal_protocol/states.md` | 400 | platform-developer, process-researcher | split | 8 | 926 lines. The normative S_i and o_i definitions and the start-state table are buried under per-role state-space counts (1400, 352, 128, 72, 29) and 10^2000 lower-bound estimates for log4j and Meltdown, which is research analysis. | Its closing line hands off to Transitions, then says 'first, the message types must be defined'. The nav order (States, Messages, Transitions) matches this, but the hand-off does not link Messages. |
| `reference/formal_protocol/transitions.md` | 400 | platform-developer | revise | 32 | The EMB-01 note says Participants 'MAY begin embargo negotiations before sending the report', so an E* message at q^rm in S is not an error. ADR-0096 withdrew this, and rm_em.md now says EM SHALL NOT begin before a case exists. The tuple order here is (q^cs, q^rm, q^em); states.md uses (q^rm, q^em, q^cs). | — |
| `topics/process_models/cs/cs_model.md` | 400 | platform-developer, process-researcher | ok | 10 | Defines Q^cs, q0 and F, the vendor fix path, and wildcard notation as a DFA 5-tuple, in parallel with the RM and EM models, and links each prerequisite. | Opens with 'begun in the [previous page](index.md)', but its nav predecessor is events.md, not cs/index.md. |
| `topics/process_models/cs/cs_model_limitations.md` | 500 | process-researcher | relocate | 1 | White-paper 'Limitations and Future Work' (e.g. 'We agree with the reviewer', 'this white paper', utilitarianism) on transition probabilities, total order over histories, and equity. It depends on the measuring_cvd pages, but it sits at the end of the CS explanation path. | — |
| `topics/process_models/cs/events.md` | 500 | process-researcher | merge | 2 | Non-normative 'toy model' literature comparison (Arbaugh, Frei, Bilge, Lewis) of lifecycle events. It repeats cs/index.md's per-substate literature mapping and its shrinkwrap/SaaS text almost word for word, yet it is first in the CS nav. | Says 'which we will later expand into the MPCVD space' but never links where. Its inbound links come from measuring_cvd pages, not from the CS pages that follow it in the nav. |
| `topics/process_models/cs/index.md` | 300 | cvd-practitioner, platform-developer | extract | 44 | An index.md that carries the full definitions of the six substates, in first-person research voice citing three academic papers. It routes only to cs_model.md; none of its other four children are linked. | — |
| `topics/process_models/cs/model_definition.md` | 400 | platform-developer, process-researcher | merge | 3 | Macrostate diagram and prose, then a 'fully defined' block that repeats the Q^cs set from cs_model.md and the delta^cs grammar from cs/transitions.md verbatim. It opens with 'the vendor fix flow above', which is not on this page. | Macrostate prose relies on the 'instability of pX and vP' that cs/transitions.md establishes, without a back-reference. |
| `topics/process_models/cs/transitions.md` | 400 | platform-developer, process-researcher | revise | 7 | The grammar is introduced as 'Following the complete state machine diagram above', but that diagram is on model_definition.md, the next page. '[CVD Case Substates](./cs_model.md) table above' points to another page. The delta^cs row 'VFdPxA -> X VFDPXA' appears to skip a state (expected VFdPXA), and the same row is copied into model_definition.md. | Forward-references a diagram that the reader has not yet reached in the nav. |
| `topics/process_models/em/defaults.md` | 300 | cvd-practitioner, platform-developer | revise | 18 | Practitioner norms (publish a default in your VDP, shortest-wins) argued via a 70-line zero-indexed vector/logical-AND proof and a game-theory aside; implementer-only rules (protocol default MUST be configurable, 72h-5d) sit in the same voice. | — |
| `topics/process_models/em/early_termination.md` | 300 | cvd-practitioner | ok | 11 | Short, practitioner-voiced causes and reasons for early termination with normative boxes; CS formalism kept in optional inline sidebars and linked to cs_model.md. | Says nothing about what a Participant does or sends when termination happens; PEC page claims this page covers how ET drives the PEC reset, but it does not mention PEC. |
| `topics/process_models/em/index.md` | 400 | cvd-practitioner, platform-developer, process-researcher | extract | 42 | 372-line index.md that is a full DFA derivation (states, sigma, right-linear grammar, regex, exhaustive list of ~70 traces of length <=7); never routes to its 7 nav children; em_dfa_diagram.md is included twice. | Only split-in-passing links to early_termination.md and defaults.md; no orientation telling the reader that principles/negotiating/defaults are the practitioner-facing pages. |
| `topics/process_models/em/negotiating.md` | 300 | cvd-practitioner | revise | 11 | Opens with the 'habitable zone' stated primarily as CS bit-pattern formulas (q^cs in ...P..) and asks the reader to take the notation on trust; uses EM shorthand N/P/A and the P-a->A transition with no link to the EM model. | — |
| `topics/process_models/em/participant-embargo-consent.md` | 400 | platform-developer, project-contributor | merge | 5 | A second normative spec in the Explanation section: cites MSM/EP/CM/EMB spec IDs and repo paths (specs/*.yaml, notes/*.md), CASE_MANAGER internals, full transition table (SIGNATORY-ER row listed twice); substantially the same content as vultron-spec section 9. | Further Reading claims early_termination.md explains the ET/PEC reset and negotiating.md explains EP/EA/ER exchange; neither page does. |
| `topics/process_models/em/principles.md` | 300 | cvd-practitioner | ok | 6 | Practitioner norms (social agreement, short and small, free to disengage, termination is not publication) in plain voice; single formal expression is linked to the EM model. | — |
| `topics/process_models/em/split_merge.md` | 300 | cvd-practitioner | ok | 0 | Clear practitioner guidance with worked split/merge examples; zero inbound links from any page, reachable only via nav. | No page links in (0 inbound); EM index and principles never mention case splits or merges, so the page is an orphan in the reading flow. |
| `topics/process_models/em/working_with_others.md` | 300 | cvd-practitioner | ok | 12 | Practitioner-voiced who/when-to-invite guidance with concrete examples (7-day vendor policy, untrustworthy participants); back-references defaults.md explicitly. | — |
| `topics/process_models/index.md` | 300 | cvd-practitioner, platform-developer | revise | 6 | A routing page built from RM/EM/CS excerpts and diagrams. It never routes to the Model Interactions subsection that is its nav child, and it uses 'deterministic finite automata' without saying what that means for the reader. | It does not tell the reader that Model Interactions and the Formal Protocol reference build on these three models. |
| `topics/process_models/model_interactions/index.md` | 300 | cvd-practitioner, platform-developer | extract | 8 | An index.md that carries content (participant-agnostic vs participant-specific essay and a normative-sounding 'Closing a Case While an Embargo Is Active' rule) and never links its two children rm_em.md and rm_em_cs.md. | — |
| `topics/process_models/model_interactions/rm_em.md` | 400 | cvd-practitioner, platform-developer | revise | 2 | Updated to ADR-0096 at the top ('EM SHALL NOT begin before a case exists'), but later sections still assume pre-case negotiation: the P->A diagram lists RM Start, and 'don't lose momentum' has a None->Propose flow in RM Invalid. ADR-0096 is cited by number only. | — |
| `topics/process_models/model_interactions/rm_em_cs.md` | 400 | cvd-practitioner, platform-developer | revise | 2 | The Vendor Notification section says EM 'might already be underway prior to Vendor notification' and 'if the EM process has not started, it SHOULD begin as soon as possible'. Both contradict rm_em.md and ADR-0096 (EM SHALL begin at case creation). '[CS Transitions](../cs/cs_model.md)' links the wrong page. | — |
| `topics/process_models/rm/index.md` | 400 | cvd-practitioner, platform-developer, process-researcher | extract | 79 | 692-line index.md carrying the whole RM model: practitioner state guidance mixed with DFA sigma/delta grammar, 15 shortest trace strings and state-subset algebra; routes to its one child only in passing; CERT Guide prioritization URL is malformed (certcc.github.io/topics/...). | — |
| `topics/process_models/rm/rm_interactions.md` | 300 | cvd-practitioner, process-researcher | revise | 12 | Recognizable CERT/CC scenarios (finder-vendor, coordinator, supply chain) but four near-identical 30-line full-DFA mermaid blocks carry them; seven links to 'participants interact from the accepted state' point at bare index.md, not the anchor. | Ends after the supply-chain diagram with no transition to EM or to model_interactions/rm_em.md, the next nav group that uses these multi-participant patterns. |

### #3621 (R3) — Case lifecycle and protocol explanation

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `topics/activity_vocabulary_design.md` | 400 | platform-developer, project-contributor | ok | 19 | Explains each AS2 verb choice from two stated design rules, cites ADR-0083/0039/0050 and MSM ids; worked examples with diagrams. | — |
| `topics/actor-knowledge-model.md` | 300 | platform-developer | ok | 6 | States one invariant, derives the full-inline-object rule and co-location rule, gives an implementer's test; cites AKM ids. | — |
| `topics/behavior_logic/index.md` | 400 | platform-developer, project-contributor | extract | 15 | Index carries a BT primer: node-type table, two example trees, reading-orientation rules, five external BT references; plus the three-views routing table. | 'With the formal definition of the Vultron Protocol behind us' assumes the reader just finished Reference/formal_protocol, which is in another quadrant. |
| `topics/behavior_logic/use-cases/embargo-lifecycle.md` | 400 | platform-developer | ok | 2 | Follows the five-question anatomy: EM vs PEC scopes, transition table, mandatory public-case override, call-out defaults, pocket veto; EMB/EP ids cited. | — |
| `topics/behavior_logic/use-cases/index.md` | 300 | platform-developer | extract | 2 | Beyond routing, carries conceptual sections (mechanical vs delegated decisions, three call-out point properties with BT-18/BT-23 ids) that restate the capability model. | — |
| `topics/behavior_logic/use-cases/prioritize-report.md` | 400 | platform-developer | ok | 3 | Explains why prioritization is mandatory, the guard/commit/effect ordering, Evaluator vs Actuator hooks, and why deferral is announced; RMB ids tabled. | — |
| `topics/behavior_logic/use-cases/propose-case.md` | 400 | platform-developer | ok | 5 | Eleven-step accept cascade, admission-gate placement and its two anti-bypass properties, CP ids tabled; the fullest treatment of case proposal. | — |
| `topics/behavior_logic/use-cases/validate-report.md` | 400 | platform-developer | ok | 3 | Covers self vs received-side paths, five precondition checks before first write, credibility-then-validity Evaluators, RMB table. | — |
| `topics/case_lifecycle/case_initialization.md` | 400 | platform-developer, project-contributor | split | 5 | Mixes explanation (why the vendor does not create the case) with wire-example reference, env-var/Python config how-to, and a demo tutorial block. | — |
| `topics/case_lifecycle/case_ledger_sync.md` | 400 | platform-developer | ok | 6 | Explains single writer, recorded projection, log_index as causal order, holding area and drain-time CS checks; every rule linked to CLP/SYNC/CSB ids. | — |
| `topics/case_lifecycle/case_model.md` | 400 | platform-developer, project-contributor | split | 11 | Short distributed-state explanation followed by field tables keyed to vultron/core/models/*.py and a class diagram, which is reference material. | — |
| `topics/case_lifecycle/index.md` | 300 | platform-developer, project-contributor | ok | 1 | 19-line routing page: one-line descriptions of its four children, no essay content. | — |
| `topics/case_lifecycle/ownership_transfer.md` | 400 | platform-developer, project-contributor | revise | 6 | Framed as a bug history ('Before ADR-0053 ... two routing gaps', 'The fix is simple') rather than as how transfer works; ends in an open-question list. | — |
| `topics/message_semantics.md` | 300 | platform-developer | ok | 2 | Two design decisions (announcements not commands; full vs stub objects, redaction vs null) in plain imperative voice with a when-to-use table. | — |
| `topics/protocol_flow.md` | 300 | platform-developer | ok | 12 | Inbox/outbox worker model, primary event vs cascade, ask-and-stop with deadlines, fault replies; written in short plain sentences for implementers. | — |
| `topics/reference_architecture.md` | 400 | platform-developer, project-contributor | revise | 4 | Says it is for CVD practitioners evaluating adoption, but the body is Python package paths, ratchet tests and ADR citations; conformance L1-L4 conflicts with what-is-vultron's three levels. | — |

### #3622 (R4) — Demos, tutorials, and scenarios

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `howto/demos/fvv-demo.md` | 300 | cvd-practitioner, platform-developer | relocate | 0 | A step-by-step tutorial (clone, run, what happens, milestones, troubleshooting) filed under How-to > Demos; its own Next steps says to run the FV tutorial first. | Milestone numbering jumps M2 to M4 with no M3 and no explanation, unlike fv-demo.md which explains its M3/M2 ordering. |
| `reference/fv-demo-protocol.md` | 300 | platform-developer | revise | 1 | Stale against code: lists MessageSemantics OFFER_CASE_MANAGER_ROLE / ACCEPT_CASE_MANAGER_ROLE (absent from vultron/, and messages/case_management.md says that wire form was removed per SE-08-005), cites vultron/wire/as2/extractor.py (now a package), and says the demo uses 'all three' state machines. | — |
| `topics/scenarios/fccv-extension.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the C1's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fccv-handoff.md` | 300 | platform-developer, project-contributor | revise | 0 | Step 6 omits that the offer routes via the Case Actor, and the unobservable table says only the accept is ledgered, contradicting ownership_transfer.md's offer-recorded entry. | — |
| `topics/scenarios/fcv-reject.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the Coordinator's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fcv.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the Coordinator's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fcvcv.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the C1's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fv.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the Vendor's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fvcv-extension.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the Vendor1's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/fvcv-handoff.md` | 300 | platform-developer, project-contributor | revise | 0 | Unobservable-edges table says the ownership offer is not ledgered and then 'may also produce' an entry; ownership_transfer.md says the offer commits an offer-recorded entry. Also retired FINDER role, CaseActor as 'Vendor1's internal sub-actor'. | — |
| `topics/scenarios/fvv.md` | 300 | platform-developer, project-contributor | revise | 0 | Templated ledger-event narrative, 0 inbound links; calls the retired FINDER role (ADR-0078) a participant and the CaseActor 'the Vendor1's internal sub-actor', contradicting case_model.md's role-based authority. | — |
| `topics/scenarios/index.md` | 300 | project-contributor | extract | 2 | Beyond the generated routing table, carries contributor-only material: causal_edges YAML schema, CI invariant check, DEMOMA update-together rule for test files. | Does not link the tutorials that run the same scenarios (tutorials/fv-demo.md, tutorials/container_demos.md). |
| `tutorials/container_demos.md` | 300 | cvd-practitioner, platform-developer | revise | 4 | Describes FV as a notes-exchange run ending at RM ACCEPTED, while fv-demo.md describes the same default run as the full VFDPxa lifecycle to case closure; omits the docker/.env step fv-demo says is required; internal label "D5-2". | — |
| `tutorials/fv-demo.md` | 300 | cvd-practitioner, platform-developer | revise | 2 | Internally inconsistent: "four narrative phases", "six demo phases", "seven milestones"; lists five containers of which two take part; success line reads TWO-ACTOR DEMO; VFDPxa, LedgerFanout and trust bootstrap used unlinked. | — |
| `tutorials/other_demos.md` | 300 | platform-developer | revise | 4 | Diagrams contradict the How-to guides they link: embargo proposal shown as Offer (guides: Invite(Event)), termination ends in EM NONE (guides: EM.EXITED), engage-path closure as RmCloseReport (guides: Leave(VulnerabilityCase)). | Step 1 restarts the container after telling the reader to follow receive_report_demo Steps 1-2 first; the two instructions overlap confusingly. |
| `tutorials/receive_report_demo.md` | 300 | cvd-practitioner, platform-developer | revise | 10 | Demo 2 diagram note says "Case created" while the prose says no case is created; uses internal class names (RmSubmitReport, RmValidateReport) as the vocabulary; RM state machine named without a link. | — |
| `tutorials/submit-a-report.md` | 200 | platform-developer | ok | 1 | Genuine first tutorial: six concrete steps, rendered from a tested module, links glossary terms, confirms the result, and says what it does not cover. | Submits via Create(VulnerabilityReport) while the next tutorial and the How-to use Offer as submission; Next steps flags this but only in passing. |
| `tutorials/worked_example.md` | 400 | cvd-practitioner, platform-developer | relocate | 6 | Not a tutorial: a narrated set of sequence diagrams in formal two-letter message codes (RS, EP, RK, EK, CV...) with no steps for the reader; its sections are also include-sourced into reference/vultron-spec/_annexes.md. | — |

### #3623 (R5) — How-to guides, About, namespace

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `about/acknowledgements.md` | 100 | ALL | ok | 0 | One-line include of repo-root Acknowledgements.md; boilerplate About page. | — |
| `about/faq.md` | 200 | platform-developer | revise | 0 | Three questions only; answers are dated ("We're not there yet", links from 2017-2023), and none answers the site's lead questions (what kind of thing is this, would it help me, it doesn't do X). | — |
| `about/license.md` | 100 | ALL | ok | 0 | One-line include of LICENSE.md. | — |
| `about/whats_new.md` | 100 | ALL | ok | 0 | Generated list of pages added in the last 90 days; no hand-maintained content. | — |
| `howto/activitypub/activities/acknowledge.md` | 300 | platform-developer | revise | 4 | Justifies the nested Read(Offer) wire form by naming Python internals (AckReportPattern, rm_read_report_activity) in a guide addressed to implementers in any language. | — |
| `howto/activitypub/activities/error.md` | 300 | platform-developer | ok | 4 | Clear decision table of three failure modes with send/verify steps; closing note about VultronError is a codebase aside but labeled. | Only guide in the set (with role_delegation) without a See-it-end-to-end demo; no signal whether one exists. |
| `howto/activitypub/activities/establish_embargo.md` | 300 | platform-developer | ok | 4 | Task-shaped: prerequisites, both routes to EM.ACTIVE, verify table, demo; points to EM model before designing behavior. | — |
| `howto/activitypub/activities/index.md` | 300 | platform-developer | ok | 10 | Routing page: states its reader, points out to Message Types, Activity Vocabulary Design and Tutorials, then lists the 13 guides grouped by task. | — |
| `howto/activitypub/activities/initialize_case.md` | 300 | platform-developer | ok | 5 | Numbered steps, inline-carry shortcut, verify table and demo; CASE_MANAGER used without introduction. | — |
| `howto/activitypub/activities/initialize_participant.md` | 300 | platform-developer | ok | 5 | Two-activity recipe with context/target discriminator warning, per-case binding note, verify and demo. | — |
| `howto/activitypub/activities/invite_actor.md` | 300 | platform-developer | ok | 6 | Task recipe with sender/attributedTo routing rule; dense with spec/ADR IDs (PCR-08-007, CM-28-002, EP-07-006, ADR-0065) but they are citations, not the argument. | — |
| `howto/activitypub/activities/manage_case.md` | 300 | platform-developer | ok | 7 | Engage/defer/close recipe with owner-closure and active-embargo refusal; cites ADR-0050/0085 and CM-23-xxx unlinked as citations. | — |
| `howto/activitypub/activities/manage_embargo.md` | 300 | platform-developer | ok | 10 | Revise/terminate recipe with verify table and demo; links EM model, early termination and consent pages. | — |
| `howto/activitypub/activities/manage_participants.md` | 300 | platform-developer | ok | 2 | Composes invite, seat, status and remove into one lifecycle and links each component guide; target-vs-origin warning cites issue #3438. | — |
| `howto/activitypub/activities/report_vulnerability.md` | 300 | platform-developer | ok | 12 | Opening RM exchange with both Reporter and recipient steps, verify table and demo; links RM model and message reference. | — |
| `howto/activitypub/activities/role_delegation.md` | 300 | platform-developer | revise | 5 | Tells implementers to carry an `as_CaseParticipantRole` object, which is a Python class name (as_* prefix being removed), while ns/index.md lists the wire type as CaseParticipantRole. | Has no See-it-end-to-end section, unlike its neighbors, and does not say whether a demo exists. |
| `howto/activitypub/activities/status_updates.md` | 300 | platform-developer | ok | 14 | Field-by-field recipe for CV/CF/CD and CP/CX/CA with the context-vs-target warning, note posting, verify and demo; uses vfd/pxa letters without linking the CS model. | — |
| `howto/activitypub/activities/suggest_actor.md` | 300 | platform-developer | ok | 5 | Recommend and decide recipes routed through CASE_MANAGER with a clear warning; verify table and demo. | — |
| `howto/activitypub/index.md` | 300 | platform-developer | revise | 6 | Frames Vultron as something that "can be mapped onto" ActivityPub, while the child guides treat AS2 as the wire vocabulary; its example activity list is not the current vocabulary, yet _demo_prerequisites.md sends every guide's reader here for the verb/object/target shape. | — |
| `howto/case_object.md` | 300 | platform-developer | relocate | 10 | 10-line moved-page tombstone pointing to topics/case_lifecycle/case_model.md, still holding a How-to nav slot and listed on howto/index.md; 10 inbound links make keeping the URL cheap and the nav entry unnecessary. | — |
| `howto/process_implementation.md` | 400 | platform-developer | split | 4 | Does two jobs: essay-style integration notes (RM as ITSM, EM as iCalendar, vfd/pxa) with no steps, plus a normative-sounding Conformance Levels L1-L4 section; message codes RK/RI/RV/CV/CF/CP used unlinked; cites ISO/IEC 29148 (requirements engineering) for pre-publication review. | — |
| `howto/wire_capability.md` | 400 | platform-developer, project-contributor | ok | 2 | Concrete three-step recipe (identify fuzzer node, implement factory, wire bundle) with a full worked example; links Capability Model and architecture pages. | — |
| `ns/index.md` | 300 | platform-developer | ok | 0 | Namespace landing: declared wire types, context usage and stability note; withheld from the build on purpose (draft_docs) until the term set settles. | — |

### #3624 (R6) — Concept registries

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `reference/glossary.md` | 300 | project-contributor | split | 14 | 721-line ubiquitous-language dump: reader CVD terms sit beside hexagonal ports, DataLayer methods, 'Priority 473', TASK-AF dialogues and GitHub work tracking. 'Flagged Ambiguities' repeats 'CVD Domain Ambiguities' item for item. CS is given as '32 reachable' and also '40 total states', and Message Type as 29 where other pages say 28. | — |
| `reference/notation.md` | 300 | ALL | split | 2 | Does two jobs: site admonition and normative-banner conventions (100-level, for everyone) and ZF set/DFA/CFSM notation (400). Its placeholder admonitions ('It is also an example example.', 'What is a question? This is.') are part of the rendered page. Its math half is also included into vultron-spec Annex C. | — |
| `reference/quick_reference.md` | 400 | platform-developer | revise | 0 | Summarizes participant state as the triple (cs,rm,em) with three state machines, while the spec and taxonomy define five (RM, EM, PEC, VFD, PXA), and it omits PEC entirely. Its role table has a 'Finder / Reporter' row although Finder is not a role (ADR-0078). 0 inbound links. | — |
| `reference/terms.md` | 200 | cvd-practitioner | merge | 2 | 89-line page of seven CVD Guide roles plus Case/Participant/Report. It defers to the Glossary as canonical and calls Vendor synonymous with Supplier, which the Glossary lists as an alias to avoid. | — |
| `reference/vultron-taxonomy.md` | 300 | platform-developer, project-contributor | revise | 1 | Lists 'The five capability shapes' including Sentinel, while spec Annex G, the Glossary and ADR-0097 say four and exclude Sentinel. Calls Case Manager an 'AS actor', the actor-identity framing ADR-0088 retires. Its 'Audience' note enumerates a competing four-audience list (sponsors, collaborators, implementers, contributors). | — |

### #3625 (R7) — Wire and protocol reference

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `reference/activitypub/objects.md` | 300 | platform-developer | revise | 6 | Lists only six Vultron objects (no CaseProposal, CaseLedgerEntry, CaseParticipantRole that messages/ pages use); 'Why is there a CaseStatus inside ParticipantStatus' says the case owner updates CaseStatus, which contradicts the CASE_MANAGER single-writer rule in the spec and glossary. | Never links to vultron-spec §5.2 Object Types or to messages/index.md, which are the normative and mapping views of the same objects. |
| `reference/draft-vultron-replication-spec.md` | 400 | platform-developer | ok | 0 | Working-draft companion spec (SYNC-01..15), withheld from the build by the draft-*.md pattern; the banner says it is not ready for circulation. | — |
| `reference/iso_crosswalks/index.md` | 200 | cvd-practitioner | revise | 5 | Three-row routing table. The link text for ISO/IEC TR 5895 reads 'ISO 5898'. | — |
| `reference/iso_crosswalks/iso_29147_2018.md` | 400 | cvd-practitioner | ok | 2 | Clause-to-page map with $q^{rm}$ formal transitions. Most targets are topics/behavior_logic design-history pages, and none are vultron-spec sections. | — |
| `reference/iso_crosswalks/iso_30111_2019.md` | 400 | cvd-practitioner | ok | 2 | Clause 7 mapped to RM/CS states, BT design pages and formal transitions; consistent and compact. | — |
| `reference/iso_crosswalks/iso_5895_2022.md` | 400 | cvd-practitioner | revise | 1 | Row 9.2 labels the Invalid-state link 'Valid'. Row 9.3 links Accepted and Fix Readiness without anchors. Clause 6 'MPCVD Stakeholders' maps only to terms.md. | — |
| `reference/messages/case_management.md` | 400 | platform-developer, project-contributor | revise | 10 | Says the case owner mints Create/Update(VulnerabilityCase) and sends Announce(VulnerabilityCase) to seed joiners, while ledger_replication.md and the spec attribute seeding and case writes to the CASE_MANAGER. It also names extractor/factory module paths in a protocol reference. | — |
| `reference/messages/case_proposal.md` | 400 | platform-developer, project-contributor | ok | 2 | Three-message bootstrap flow with CP spec IDs and example artifacts; scoped and consistent with ADR-0023. | — |
| `reference/messages/cs.md` | 400 | platform-developer | ok | 4 | Explains the participant-scoped VFD vs case-scoped PXA wire split (ADR-0075) and the discriminators; follows the index's page template. | — |
| `reference/messages/em.md` | 400 | platform-developer | ok | 3 | Documents the EV/EJ/EC collapse and the Question retirement (ADR-0100); follows the page template. | — |
| `reference/messages/faults_and_acknowledgements.md` | 400 | platform-developer, project-contributor | revise | 8 | Sends readers to specs/message-semantics-mapping.yaml and notes/message-type-reference.md, neither of which is published. Its 'See also' names this page itself as the primary page. | — |
| `reference/messages/general.md` | 400 | platform-developer | ok | 4 | GI expansion across notes and actor suggestion, with worked examples; consistent with case_management.md's cross-reference. | — |
| `reference/messages/index.md` | 400 | platform-developer | ok | 7 | Routes to 8 pages and explains the many-to-many formal vs wire mapping statuses; good routing surface. | — |
| `reference/messages/ledger_replication.md` | 400 | platform-developer, project-contributor | ok | 3 | Announce/Reject(CaseLedgerEntry) and case seeding with SYNC IDs, patterns, factories. | — |
| `reference/messages/rm.md` | 400 | platform-developer | ok | 4 | RS..RE with triggering transitions, wire forms and examples; explains Join/Ignore case-scoped verbs. | — |
| `reference/specs/architecture.md` | 400 | platform-developer, project-contributor | ok | 7 | Generated architecture-tier requirements with a one-paragraph scope statement; 7 inbound. | — |
| `reference/specs/index.md` | 400 | platform-developer, project-contributor | ok | 1 | Four-tier routing table matching ADR-0038; consistent with the tier pages. | — |
| `reference/specs/protocol.md` | 400 | platform-developer | ok | 592 | Generated normative protocol requirements; the most-linked page in the shard (592 inbound), so any move is expensive. | — |
| `reference/ssvc_crosswalk.md` | 400 | cvd-practitioner | revise | 6 | Renders a visible '{== TODO merge with SSVC section of Situation Awareness ==}' marker and pins SSVC v2.1 PDF links; the mappings themselves are formal and coherent. | — |
| `reference/trigger-api.md` | 400 | platform-developer | ok | 7 | Generated endpoint reference with a short orientation and a link to wire_capability background. The prose hard-codes '23 endpoints'. | — |
| `reference/user_stories/index.md` | 200 | cvd-practitioner, process-researcher | revise | 3 | Support levels are defined against 'Vultron Protocol v0.4.0' (pre-CalVer), and the page never links traceability.md, which carries the story-to-spec mapping. | No forward link to the Traceability Matrix, its nav sibling. |
| `reference/versioning.md` | 200 | cvd-practitioner, platform-developer | ok | 1 | Short CalVer definition with examples; self-contained. | — |
| `reference/vultron-spec/index.md` | 400 | platform-developer | ok | 220 | ~2,840-line include-assembled normative spec (220 inbound) written for implementers and conformance reviewers. It states its audience and N/I markers. | — |

### #3626 (R8) — Research: measuring, other uses, future work

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `topics/future_work/federation.md` | 400 | platform-developer, project-contributor | ok | 1 | Deployment-design explanation (gateway to own tracker, Announce relay, DNS/mTLS peering, connectors) with requirement IDs and inline open questions; speaks directly to someone building a coordination service. | Only inbound links are from its own section; case_ledger_sync.md, ownership_transfer.md and reference_architecture.md do not link forward to it, though it points back to them. |
| `topics/future_work/index.md` | 300 | platform-developer, project-contributor | ok | 0 | 36-line routing page that separates 'protocol excludes' from 'not yet built' and explains the scope: production convention; orients and routes only. | Zero inbound links: topics/index.md grid lists Measuring CVD and Other Uses but not Future Work, so the section is reachable only via nav. |
| `topics/future_work/open_questions.md` | 400 | platform-developer, project-contributor | ok | 4 | Pure aggregation of _oq-* include fragments grouped by topic, each naming its tracking issue; defines the two meanings of an entry. | — |
| `topics/measuring_cvd/benchmarking.md` | 500 | process-researcher | revise | 6 | Sound benchmarking argument (c_d, Cyentia-derived alpha estimates), but its 'MPCVD' routing bullet links to #cvd-benchmarks on this page instead of benchmarking_mpcvd.md. | Missing forward link to benchmarking_mpcvd.md, which is its announced continuation and the next nav page. |
| `topics/measuring_cvd/benchmarking_mpcvd.md` | 500 | process-researcher | revise | 0 | Only measuring_cvd page without the not_normative banner; refers to 'randomness assumptions outlined above' and 'the 5 dimensions ... we have presented above' that live on other pages; 0 inbound links. | Assumes alpha_d, D and the benchmark constant c_d from benchmarking.md and discriminating_skill_and_luck.md; links benchmarking.md only at the very end. |
| `topics/measuring_cvd/desirable_histories.md` | 500 | process-researcher | revise | 8 | Formal desiderata set D and the poset over H are correct in intent, but a 4-space-indented _history_constraints include follows an unindented one (likely renders as a code block) and 'partiarl' typo. | — |
| `topics/measuring_cvd/discriminating_skill_and_luck.md` | 500 | process-researcher | ok | 4 | Derives the skill coefficient alpha_d as a binomial skill/luck mixture with Beta credible intervals; research voice for a research reader. | — |
| `topics/measuring_cvd/index.md` | 200 | process-researcher | revise | 4 | Section index is only a pasted paper abstract plus citation; lists none of its 10 child pages, and the abstract promises stakeholder reflections that actually live in other_uses/roles_influence.md. | No route from the index to possible_histories.md, the first page of the sequence. |
| `topics/measuring_cvd/mod_sim.md` | 500 | process-researcher | merge | 0 | 25-line 2022 anticipation piece with a 2026 historical-context patch; its only substantive content is 'reward functions and BTs could enable simulation', which reward_functions.md already carries. | — |
| `topics/measuring_cvd/observing_skill.md` | 500 | process-researcher | ok | 3 | Proof-of-concept application of alpha_d to ZDI/Microsoft 2017-2020 and NVD/Metasploit data with method and intervals stated. | — |
| `topics/measuring_cvd/possible_histories.md` | 500 | process-researcher | ok | 7 | Defines sequences, histories and the 70 valid histories via the CS DFA, linking each CS page it relies on; forward-links the columns defined later. | — |
| `topics/measuring_cvd/random_walk.md` | 500 | process-researcher | revise | 2 | Principle-of-indifference baseline and PageRank table are sound, but the Eva quotation says 'equal initial credence of n' where 1/n is meant. | — |
| `topics/measuring_cvd/reasoning_over_histories.md` | 500 | process-researcher | ok | 8 | Computes f_h and f_d, builds the partial order on desiderata and the -log(f_d) skill ranking; each prior concept is linked. | — |
| `topics/measuring_cvd/reward_functions.md` | 500 | process-researcher | ok | 5 | Sketches RM and EM reward-function criteria against the linked RM/EM grammars; historical note states plainly that nothing is implemented. | — |
| `topics/other_uses/action_rules.md` | 400 | process-researcher | ok | 3 | Framed as 'another application of the CS model'; 50-row state-subset/role/action/reason table, formal notation throughout. | — |
| `topics/other_uses/cvd_directory.md` | 300 | platform-developer, process-researcher | merge | 1 | 2022 position-paper essay on contact discovery ('We especially like...'); not a use of the case state model at all, and the same problem is now carried with current design by the actor-discovery open question and federation trust section. | — |
| `topics/other_uses/index.md` | 200 | process-researcher | revise | 1 | Hand-written landing page lists 6 of 7 children (omits cvd_directory.md), in an order that disagrees with nav, under a title ('uses of the case state model') that cvd_directory does not fit. | — |
| `topics/other_uses/policy_formalization.md` | 400 | process-researcher | ok | 1 | Shows SLEs as timers between CS transitions and sketches a policy-statement form; speculative research voice appropriate to its reader. | — |
| `topics/other_uses/roles_influence.md` | 500 | process-researcher | ok | 1 | Per-stakeholder desiderata subsets (D_v, D_s, D_c, D_g) built on the measuring_cvd notation, which it links; about vendors/coordinators, addressed to a researcher. | It is the stakeholder-reflection conclusion promised by measuring_cvd/index.md, but neither page links the other in that role. |
| `topics/other_uses/situation_awareness.md` | 500 | process-researcher | ok | 2 | Single worked example normalizing random_walk PageRank over Vf.... to infer likely case state; linked prerequisites. | — |
| `topics/other_uses/vep.md` | 400 | process-researcher | ok | 2 | Maps VEP charter definitions onto CS state subsets to derive S_VEP = {vfdpxa, vfdpxA}; policy analysis in formal voice. | — |
| `topics/other_uses/zero_day.md` | 400 | process-researcher | revise | 2 | Formal zero-day/forever-day definitions are useful, but the text still says 'presented in this whitepaper' and 'a reviewer stated', which addresses a paper reviewer rather than a site reader. | — |

### Section landing pages — owned by #3527

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `howto/index.md` | 200 | platform-developer | revise | 11 | Hand-maintained landing: lists the case_object tombstone as content, omits demos/fvv-demo.md, carries a stale "will expand over time" wish list, and opens with "a few additional suggestions" rather than routing by task. | — |
| `reference/index.md` | 200 | ALL | revise | 10 | Landing page has drifted from the nav: it describes Specifications with the retired six-kind taxonomy (General, Pattern, Domain, Language, Implementation, Dev Process) instead of the four tiers, and routes to topics/measuring_cvd. It omits Quick Reference, the Protocol Specification, Glossary, Concept Taxonomy, AS Objects, Messages' siblings and FV Demo Protocol. | — |
| `topics/index.md` | 200 | ALL | revise | 10 | Explanation landing card list omits Protocol Event Flow, Capability Model, Demo Scenarios and Future Work that nav carries, and lists two Reference pages. | — |
| `tutorials/index.md` | 200 | cvd-practitioner, platform-developer | revise | 4 | Hand-maintained list omits worked_example.md (in nav under Tutorials); tells newcomers to leave Tutorials for Explanation first; no sense of which tutorial to start with or why. | — |

### Reclassified as working record — tagging owned by #3528

| Page | Level | Addressed to | Verdict | Inbound | Evidence | Continuity |
|---|---|---|---|---|---|---|
| `about/contributing.md` | — | project-contributor (working record) | ok | 1 | Includes CONTRIBUTING.md and ContributionInstructions.md; addressed to people contributing to this repository. | — |
| `reference/behaviors/case_handlers.md` | — | project-contributor (working record) | relocate | 2 | Generated py_trees renderings of vultron/core/behaviors/case and sync; generated code documentation belongs to the working record, but it is enumerated inline in the Reference nav. | — |
| `reference/behaviors/cs_handlers.md` | — | project-contributor (working record) | relocate | 0 | Generated trees for status receive-side; 0 inbound links because behaviors/index.md's category table omits it (the nav lists it). | behaviors/index.md does not route to this page, so the only way in is the nav. |
| `reference/behaviors/em_handlers.md` | — | project-contributor (working record) | relocate | 2 | One generated tree plus EMB requirement links; generated code documentation enumerated in the reader-facing nav. | — |
| `reference/behaviors/index.md` | — | project-contributor (working record) | revise | 26 | Routing page for generated BT reference (26 inbound); its category table omits cs_handlers.md, which the nav includes. | — |
| `reference/behaviors/rm_handlers.md` | — | project-contributor (working record) | relocate | 3 | Generated RM trees with RMB requirement links; generated code documentation enumerated in the Reference nav. | — |
| `reference/ontology/index.md` | — | project-contributor (working record) | ok | 0 | Tombstone that records the unmaintained OWL files and the unreconciled namespace; withdrawn from the nav on purpose (#3551). | — |
| `reference/specs/process.md` | — | project-contributor (working record) | relocate | 1 | Generated CI/GitHub/agent-convention requirements. This is project working record, enumerated in the reader-facing Reference nav. | — |
| `reference/specs/project.md` | — | project-contributor (working record) | relocate | 21 | Generated Python-codebase-specific requirements (21 inbound). It is working-record material for contributors, not reader reference. | — |
| `reference/user_stories/traceability.md` | — | project-contributor (working record) | ok | 0 | Story-to-spec matrix routing all 111 stories (the pattern the IA note endorses). Its contributor-facing features include a hand-edit EDITOR NOTES comment, a ToC with a 'Line' column, and gap analysis keyed to issue numbers. 0 inbound links apart from the nav. | — |
