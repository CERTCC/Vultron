---
title: Documentation Strategy Notes
status: active
description: >
  Documentation chronology and strategy for interpreting conflicting
  documentation generations in Vultron.
related_notes:
  - notes/bt-integration.md
  - notes/case-state-model.md
  - notes/documentation-sweeps.md
  - notes/message-type-reference.md
  - notes/rfc-spec-authoring.md
  - notes/site-information-architecture.md
  - notes/spec-authoring-rules.md
  - notes/vocabulary-registry.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/docs-build-workflow.yaml
relevant_packages:
  - vultron/bt
  - vultron/core
  - vultron/demo
  - vultron/wire/as2
---

# Documentation Strategy Notes

## Documentation Chronology and Trust Levels

The Vultron documentation has multiple generations, written at different
times with different purposes. Understanding this chronology is critical for
correctly interpreting documentation when it conflicts with implementation.

### Generation 1: Pre-implementation design docs

**Files**: `docs/topics/**/*.md`, `docs/reference/formal_protocol/**/*.md`,
`docs/howto/**/*.md`

These were written **before the ActivityStreams-based implementation** and
served as the original source material for early implementation iterations.
They describe the intended behavior patterns, state machine logic, and formal
protocol definitions.

**Trust**: High for understanding *intent and design rationale*. Low for
*specific field names, class hierarchies, or API details*, as these changed
with the ActivityStreams adoption.

### Generation 2: State-based model and simulation

**Files**: `vultron/core/case_states/**/*.py`, `vultron/core/states/**/*.py`,
`vultron/bt/**/*.py`
(including `vultron/bt/base/demo/cvd.py`)

These were some of the earliest Python implementations, based on:

- [*A State-Based Model for Coordinated Vulnerability Disclosure*](
  https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf)
  (CMU/SEI-2021-SR-021) — basis for `vultron/core/case_states/hypercube.py` and
  the VFD/PXA state machines.
- [*Designing Vultron*](
  https://www.sei.cmu.edu/documents/1954/2022_003_001_887202.pdf)
  (CMU/SEI-2022-SR-019) — basis for the behavior tree simulator in
  `vultron/bt/**/*.py` (including the CVD self-simulation demo
  `vultron/bt/base/demo/cvd.py`).

These implementations came **before** the decision to use ActivityStreams
vocabulary. They remain valuable as reference implementations for protocol
logic, but MUST NOT be directly reused in prototype handlers. See
`notes/bt-integration.md` for the BT translation strategy.

### Generation 3: Current ActivityStreams-based implementation

**Files**: `vultron/wire/as2/vocab/**/*.py`, `vultron/adapters/**/*.py`,
`vultron/core/behaviors/**/*.py`, `vultron/wire/as2/extractor.py`,
`vultron/core/use_cases/use_case_map.py`, etc.

This is the current prototype codebase. Documentation in `docs/howto/activitypub/`
and `specs/**/*.md` reflects this generation.

---

## When Documentation Diverges from Implementation

When the implementation significantly diverges from the documentation,
evaluate:

1. **Is the divergence intentional?** If the ActivityStreams adoption required
   a design change, the documentation may be deliberately different and should
   be updated to reflect the new design.

2. **Is the implementation wrong?** If the implementation drifts from the
   intended design without a documented reason, consider whether the
   implementation should be corrected.

3. **Is the documentation outdated?** If the documentation reflects an earlier
   design that has since been superseded, mark it as historical or update it.

**Decision framework**:

- Divergence with documented rationale → update docs to reflect new reality.
- Divergence without clear rationale → investigate before changing either.
- Outdated design docs with no corresponding implementation → mark as
  historical or archive.

**State machine enums are authoritative**: When documentation and enum
definitions disagree on state names or valid states, the enum code wins.
Update the documentation to match the enum, never the reverse (unless the
enum itself is explicitly identified as a bug by a maintainer). Canonical
enum files: `vultron/core/states/rm.py` (RM),
`vultron/core/states/em.py` (EM),
`vultron/core/states/cs.py` (CS/VFD/PXA).

---

## Process Models and Formal Protocol Documentation

### Process Models

Detailed process model documentation is in `docs/topics/process_models/`:

- `rm/` — Report Management state machine
- `em/` — Embargo Management state machine
- `cs/` — Case State transitions and interaction with RM/EM
- `model_interactions/` — how the three state machines interact

These describe the **intended behavior** of protocol participants and were
used as the design source for the behavior tree simulator in `vultron/bt/`.

### Formal Protocol

`docs/reference/formal_protocol/` provides formal state machine definitions:

- `states.md` — formal state enumeration
- `transitions.md` — allowed state transitions with conditions
- `messages.md` — message types and their semantic effects

These are normative for protocol correctness. When implementing new handlers
or BT nodes, verify that state transitions conform to the formal protocol
definitions.

---

## Behavior Simulator as Implementation Reference

`vultron/bt/**/*.py` contains a substantial behavior tree simulator that
encodes the protocol logic from *Designing Vultron*. Although it uses a
custom BT engine incompatible with the prototype's `py_trees`-based approach,
it is an invaluable reference for:

1. **State machine logic**: Condition checks, transition guards, and ordering
   constraints are encoded as BT node compositions.
2. **Protocol behavior patterns**: The full CVD workflow (report intake,
   validation, embargo management, case coordination) is represented as
   composable BT subtrees.
3. **Correspondence with documentation**: The simulator trees correspond
   directly to the documentation in `docs/topics/behavior_logic/*.md`.

### Three Views of Behavior, and Which One to Edit

Behavior is documented from three directions. Writing into the wrong one is the
recurring mistake, because all three describe "what an actor does".

| View | Answers | Quadrant | Source of truth |
|---|---|---|---|
| `docs/topics/behavior_logic/*_bt.md` | What behavior does the protocol call for, and why | Explanation | *Designing Vultron* + the `vultron/bt/` simulator |
| `docs/topics/behavior_logic/use-cases/` | Per use case: what is mechanical, what is delegated, what is emitted | Explanation | `vultron/core/behaviors/` + the RMB/EMB/CSB/CP specs |
| `docs/reference/behaviors/` | What trees the prototype builds today | Reference | `vultron/core/behaviors/`, rendered at build time |

The `*_bt.md` pages are **historical**: they are the original design and the
formal behavioral specification, and `index.md` frames them that way. Do not
update them to track implementation drift — that is what the other two views are
for. They change only when the *design* changes.

The `use-cases/` pages are the place for conceptual statements about current
behavior: call-out points and the judgment each represents, the ordering
constraints and why they are load-bearing, and the conformance obligations a
participant carries regardless of whether it uses behavior trees. Keep node
inventories out of them — a list of node names belongs in
`docs/reference/behaviors/`, which generates it.

### Current-Implementation Reference

`docs/reference/behaviors/` provides auto-generated reference documentation
rendered from the *current* `vultron/core/behaviors/` implementation using
`py_trees.display.unicode_tree()`. These pages complement (and will eventually
supersede) the simulator-era `behavior_logic/` pages — use them when you need
to understand what the prototype actually does, rather than what the original
design envisioned.

| Reference page | Implementation source |
|---|---|
| `reference/behaviors/rm_handlers.md` | `vultron/core/behaviors/report/` |
| `reference/behaviors/em_handlers.md` | `vultron/core/behaviors/embargo/` |
| `reference/behaviors/case_handlers.md` | `vultron/core/behaviors/case/`, `sync/` |
| `reference/behaviors/cs_handlers.md` | `vultron/core/behaviors/status/` |

### Documentation-to-Simulator Correspondence

| Documentation file | Simulator module |
|-------------------|-----------------|
| `behavior_logic/cvd_bt.md` | `vultron/bt/` (top-level) |
| `behavior_logic/em_bt.md` | `vultron/bt/embargo_management/` |
| `behavior_logic/do_work_bt.md` | `vultron/bt/` (do_work nodes) |
| `behavior_logic/fix_dev_bt.md` | `vultron/bt/` (fix dev subtrees) |
| `behavior_logic/deployment_bt.md` | `vultron/bt/` (deployment subtrees) |
| `behavior_logic/monitor_threats_bt.md` | `vultron/bt/` (monitoring subtrees) |
| `behavior_logic/id_assignment_bt.md` | `vultron/bt/` (ID assignment subtrees) |
| `behavior_logic/acquire_exploit_bt.md` | `vultron/bt/` (exploit acquisition) |

**Recommended approach** for mining the simulator: Map each `vultron/bt/`
subtree to its documentation source, then identify which prototype handlers
the subtree informs. Use this as a guide for implementing BT nodes in
`vultron/behaviors/`. See `notes/bt-integration.md` for the translation
strategy.

---

## Sequence Diagrams vs. Demo Scripts

The demo scripts are the canonical reference for each workflow, so a diagram in
`docs/howto/activitypub/activities/*.md` that disagrees with its scenario is the
diagram's defect.

The pre-demo-era diagrams were the concrete instance of this. Six sequence
diagrams on `report_vulnerability.md` depicted an `APIv1` box and `/api/v1/*`
handler calls, which ADR-0011 removed. They were retired in #3003 rather than
resynced, because the internal handler choreography they drew is neither task
content nor something a reader of a how-to guide acts on — the remaining diagrams
are inter-actor flows, which are what an implementer needs.

Several checks keep the survivors honest, and since #3456 they read the diagram in
two places. `test_docs_activity_verbs.py` asserts that the verb a
`subgraph as:Verb` block attributes to an activity is the verb the wire class or
its registered pattern declares — that check reads the mermaid node **id**, which
is now only an edge handle and is never rendered. The node **label** carries the
reader-facing name, so a second and stronger check compares the label's wire-form
line against the form derived from the registered `ActivityPattern`: it compares
the whole object composition rather than the verb alone, catching
`Read(VulnerabilityReport)` where the pattern requires
`Read(Offer(VulnerabilityReport))`. A third check covers wire forms stated in
guide prose, because the guides that draw no diagram would otherwise carry
hand-typed forms past every gate; it scans the guides directory rather than a list
of pages, so a guide added later is covered the day it lands. Each guide also
names the demo scenario that runs the same flow, so a diverged diagram is one
`vultron-demo` run from being caught.

What no check covers is a diagram whose *edges* are wrong while every activity
name and verb stays right — the verb test reads the `subgraph as:Verb` blocks, not
the arrows between them. `manage_embargo.md` was the instance: its flowchart routed
`RemoveEmbargoFromCase` back into the `Propose?` loop and left `AnnounceEmbargo`
with no edges at all, contradicting the page's own warning that termination is not
a revision. Both survived every check the tree has. When you touch a scenario,
read its guide's diagram in the same change, and read the arrows, not just the
node names.

---

## ISO Standards Cross-References

High-level cross-references to relevant ISO standards are documented in
`docs/reference/iso_crosswalks/`:

- `iso_29147_2018.md` — ISO/IEC 29147:2018 (Vulnerability Disclosure)
- `iso_30111_2019.md` — ISO/IEC 30111:2019 (Vulnerability Handling Processes)
- `iso_5895_2022.md` — ISO/IEC 5895:2022 (Multi-Party Coordinated Vulnerability Disclosure)

**Current state**: Cross-references are at a high level, mapping general
protocol concepts to ISO standard sections.

**Future work**: As the ActivityStreams vocabulary implementation matures,
it would be valuable to add more specific cross-references — linking
particular `MessageSemantics` values, handler behaviors, and vocabulary
types to the ISO standard requirements they satisfy. This would help
demonstrate standards alignment and identify any gaps.

**Priority**: Low for the prototype, but useful for eventual standardization
efforts or external communication about the project's standards alignment.

---

## Archiving Historical Documentation

As the prototype matures, some documentation may be appropriate to archive
into a clearly marked "historical" section rather than delete:

- `docs/howto/case_object.md` — original UML design superseded by
  ActivityStreams model; worth preserving as historical reference.
- Some `docs/topics/process_models/` content — predates ActivityStreams;
  may be worth preserving with a note about its historical context.
- `docs/reference/formal_protocol/` — still normative; do NOT archive.

A reasonable convention: add a front-matter note to historical docs stating
the document predates the ActivityStreams implementation and may not reflect
current design. This preserves historical context without causing confusion.

## Where a Page Belongs Is a Separate Question

This file covers how to *interpret* and *trust* the documentation generations,
and which of the three behavior views to edit. It does not decide where a page
sits or what it may assume of its reader — that is
[site-information-architecture.md](site-information-architecture.md) (ADR-0102,
DF-11): stakeholder types, the invisible 100–500 prerequisite levels, the
working-record exclusion, and the routing rule for landing pages and large leaf
sets.

## MkDocs `not_in_nav`, `exclude_docs` and `draft_docs` Are Not the Same

Files excluded from nav MUST ALSO be listed in `not_in_nav`; the overlay list
*replaces* the base list rather than extending it.

There are three keys, and they answer different questions. `not_in_nav` means
"no nav entry, and no omitted-file warning" — the file is still published.
`exclude_docs` means "not processed at all", in `build` and `serve` alike.
`draft_docs` means "published by `mkdocs serve`, absent from `mkdocs build`",
which is what withholding an artifact from the site while keeping it reviewable
locally requires. `docs/developer/` and `docs/ns/` both use it.

Three mechanics bite here, and each one has cost something:

- **A `draft_docs` pattern withholds static files too, not only pages.**
  `set_exclusions` in `mkdocs/structure/files.py` assigns an inclusion level to
  every file it walks, and `copy_static_files` filters on the same
  `is_included()` predicate that `documentation_pages()` uses. So
  `docs/ns/context.jsonld` goes with `docs/ns/index.md` under a single `ns/`
  pattern. Do not reach for `exclude_docs` to catch the non-Markdown half.
- **`draft: true` in page frontmatter does nothing.** `draft` is a key of the
  Material *blog* plugin, not of MkDocs. `docs/ns/index.md` carried it and
  published anyway. Whoever wrote it believed the page was suppressed, and
  nothing contradicted them, because the page was only ever checked by reading
  the frontmatter that claimed to suppress it. Withholding happens in
  `mkdocs.yml` and nowhere else.
- **Patterns are relative to `docs_dir` and fail silently when mis-anchored.**
  `docs/developer/` matched a nonexistent `docs/docs/developer/` and those pages
  shipped for as long as nobody looked (DOCBW-03-004).

All three failures share one shape: the withholding claim and the build output
were never compared. `uv run docs-withheld`
(`vultron/metadata/docs/withheld.py`) is that comparison, and DOCBW-03-005 runs
it after the build in every site-building workflow, through the shared
`check-site-publication` action. It checks the *outcome* rather
than the `mkdocs.yml` mechanism, so a mis-anchored pattern or a plugin-emitted
file fails the gate instead of shipping. Its declaration of what is withheld is
the interim home for the publication axis; #3555's maturity manifest replaces it.

## Withholding Has Two Axes, and Only One Was Checked

`docs-withheld` answers "did a withheld artifact produce files in `site/`". The
opposite question — "does anything *link to* a path the build did not produce" —
is a separate axis, and it stayed unchecked for one release cycle longer.

`docs/ns/` moving into `draft_docs` (#3549) withheld the page, and the What's
New list went on advertising it as `href="../../ns/"` (#3574). The publication
axis was satisfied: nothing under `site/ns/` was built. The reference axis was
violated by the same change, in a different file, and no gate looked.

The reason the link survived every gate is worth keeping separate from the
reason it was wrong. **`mkdocs build --strict` is a claim about the pages MkDocs
parsed, not about the bytes it emitted.** MkDocs rewrites relative `.md` links
with a treeprocessor registered on its *own* `Markdown` instance; `markdown-exec`
converts a block's output on a **child** instance built from the parent's
extension list, which does not carry that treeprocessor. A link printed from an
exec block is therefore never rewritten and never validated — strict did not
check it and pass it, strict never knew it was a link. Anything rendered at
build time is in this position, and the project has several such generators:
`metadata/docs/whats_new.py`, `metadata/demo_scenarios/render.py`,
`metadata/specs/docs_render.py`, and `docs/_scripts/render_trigger_api.py`.
Note the last one is not under `vultron/`, so an audit scoped to
`vultron/metadata/` misses a whole directory.

A second class writes a *committed* source file rather than rendering at build
time: `metadata/adr/index_gen.py` (`docs/adr/index.md`) and
`metadata/docs/landing_pages.py` (the generated block on each section landing
page). Their links are ordinary relative `.md` in a file MkDocs parses, so
`--strict` does see them and a staleness check (`adr-index --check`,
`docs-site --check`) covers drift. That is a weaker exemption than it sounds:
seeing a link is not resolving its target, so a withheld target still exits
through the INFO downgrade below. Nor do these generators know what is withheld
— `landing_pages.py` derives its entries from the `mkdocs.yml` nav and filters
on nothing else, where `whats_new.py` reads `draft_docs`/`exclude_docs`.

Take the membership of both lists as provisional. `landing_pages.py` did not
exist when this gate was planned; it landed on `main` days later, already a
page enumerator. Any check built by enumerating generators decays as the next
one is written, which is the practical case for gating built output instead.

Exec-block rendering is how *this* link hid, but it is not the only way a
reference to a withheld page clears `--strict`, and reading it as the whole
story under-scopes the gate. A hand-written `.md` link whose target is excluded
is downgraded on purpose: MkDocs' relative-path treeprocessor logs "contains a
link to … which is excluded from the built site" at `min(logging.INFO,
validation.links.not_found)`, and `not_found` defaults to `warn`, so the level
resolves to INFO — below anything `--strict` fails on — while the href is still
rewritten to the unbuilt URL. Both paths end at the same artifact: a
well-formed reference with no target. Which is why the gate is over built
output, not over any category of source.

Three design choices in the reference-axis check (DOCBW-03-007) are consequences
of how this one hid, not preferences:

- **Resolution, not link form.** The first instance of exec-rendered breakage
  (#3450) emitted `href="fv.md"`, so the obvious assertion was "no internal
  `href` ends in `.md`". That is a signature check, and this defect does not
  carry the signature: `../../ns/` is exactly what a *correctly* rewritten link
  looks like. It is dead because the target is not built, not because the form
  is wrong. Ask whether the reference resolves and both cases collapse into one
  assertion.
- **Every built page, not a crawl.** `linkchecker site/index.html` follows links
  from one entry point, so the pages nothing links to are never inspected: the
  `includes/` fragments, `reference/codebase/`, `agents/`, `404.html`,
  `print_page/`. That is not the same set as `not_in_nav` — most `not_in_nav`
  pages are linked from a page that *is* in the nav, so nav absence and crawl
  reachability are different properties and only the second one bounds the
  crawl. Worse, the crawl reports success over what it did reach, so the
  omission is invisible. A tree walk over `site/**/*.html` has no reachability
  precondition.
- **Unconditional, because the two declarations are in different files.** The
  withholding lives in `mkdocs.yml`; the generator that advertises the page
  lives in `vultron/` or `docs/_scripts/`. A `docs/**` path filter is the wrong
  predicate for a defect that neither file has to touch — which is why the one
  gate that *could* have caught this (`linkchecker`, conditioned on
  `docs_changed`) did not. Be precise about what DOCBW-03-007 therefore reaches:
  dropping the step-level `docs_changed` condition (DOCBW-04-003) is one of the
  two docs-scoped filters on this workflow. The other is the workflow's own
  `paths:` trigger (DOCBW-02-001), which still omits `vultron/**` — so a PR that
  edits only a generator never runs `docs-build-check.yml`, and the gate first
  sees it in `deploy_site.yml` after merge. Closing that half is #3070.

Deriving rather than mirroring is the complementary half, and it is cheaper
where it applies. `whats_new.py::_unpublished_spec` reads `draft_docs` and
`exclude_docs` out of `mkdocs.yml` through the same `GitIgnoreSpec` matcher
MkDocs uses in `set_exclusions`, so its notion of "published" cannot drift from
the build's. That replaced a hand-maintained tuple under a "keep this in sync
with mkdocs.yml" comment — and #3574 is what that invitation cost. Prefer
deriving in any new generator; the gate is what covers the ones that do not.

## The Third Axis Is Time: a URL Once Served Must Keep Answering

The publication and reference axes compare one build with itself. Neither can
see a URL that an *earlier* build served and this one dropped. Between the
`publish` branch and `main`, 162 pages had moved, been renamed, or been
withdrawn, and a publish would have turned every one of those URLs into a 404
(#3556). `--strict` saw no problem because nothing in the new build linked to
the old paths. The only readers still using them were outside the site.

`uv run docs-legacy-urls` (`vultron/metadata/docs/legacy_urls.py`,
DOCBW-03-008) is the comparison. Three things about it are easy to get wrong:

- **The evidence has to be committed before `publish` advances.** The record of
  what was served is the `publish` branch itself, so a check that derived it at
  check time would compare `main` with `main` after the next publish, and
  pass. `legacy_urls_baseline.txt` holds every `docs/` page any publish has
  built. It only grows (`--snapshot <ref>` adds a ref's pages and drops none),
  because a URL that was cited once can be cited forever.
- **The baseline lists source pages, not nav entries.** On `publish` nothing
  was in `exclude_docs`, so every `_*.md` fragment and `includes/*` file was
  built as a page of its own and answered with a 200. The issue's first count
  left these out as not reader-facing, but they were live URLs all the same.
  "Not in the nav" is a statement about discoverability. It says nothing about
  whether the URL exists.
- **Withdrawn is not redirected.** A page retired on purpose is declared in
  `withheld.py` rather than redirected to whatever page happens to be nearby,
  because a redirect to an unrelated page tells a reader the content moved when
  it did not. `docs-withheld` checks that the withdrawn URL really is absent. A
  page whose content was *folded into* another (`topics/future_work/ontology`
  into the ontology tombstone) is a move, and it redirects.

Confirm a rename by content, not by filename. `howto/general_implementation`
looked like it had become `howto/process_implementation`. In fact it covered
message formats, transport, identity, and encryption, which the commit that
removed it said the ActivityPub mapping had since addressed. So it redirects to
`howto/activitypub/`.

Both publication-side checks run through one composite action,
`.github/actions/check-site-publication`, in `docs-build-check.yml` and in
`deploy_site.yml` before the Pages upload. The action exists so the workflow
that ships is gated by exactly what the workflow that reviews is gated by.

## Nav Visibility Is Not a Content Class: Fragments vs. Assembly Units

`not_in_nav` answers "does this file get a nav entry". It does not answer "is
this file prose that prose rules apply to". Conflating the two is what left the
Protocol Specification — 35 fragments, roughly 2,800 lines of normative reference
material — outside `lint-docs` entirely, because the fragments carry the `_`
prefix that keeps them out of nav. Normative requirements: DF-09-007 through
DF-09-009. Decision record: ADR-0092.

**This section describes the decided target state, not what `lint-docs` does
today.** The tooling changes are tracked in #3318; until they land, `lint-docs`
still drops every `_*.md` fragment.

The `_` prefix was doing double duty. In `mkdocs.yml` it means "exclude from
nav"; `lint-docs` read it as "not really a page". The second claim is false for
prose-heavy content that merely happens to be *delivered* as fragments.

### The two kinds of file

A page assembled from `{% include-markdown %}` directives is an **assembly
unit**; the files it pulls in are **fragments**. Both are prose. They differ in
which rules can be evaluated against them.

| Rule scope | Evaluate against | Examples |
|---|---|---|
| Sentence or block | the fragment, with its own line numbers | spelling, filler, sentence shape, list and table discipline, Mermaid title and type, reference voice |
| Page | the assembly unit | acronym first use (DF-09-003), concept order (DF-09-005), page furniture and anything naming the H1 or nav label |

Applying a page-scoped rule to a fragment produces a finding that is an artifact
of how the document was split, not a defect in the prose. Requiring acronym
expansion in every fragment that uses an acronym renders one expansion per
fragment on a single published page — twelve for "VFD", ten for "RM", nine for
"EM", eight each for "CS" and "PEC".

Note the direction this cuts while #3318 is open: extracting a fragment moves its
prose *out* of `lint-docs`' target set, which drops both `docs/includes/**` and
`_*.md`. Deduplicating by extraction is still right (DF-10-002), but it trades
automated coverage for structural non-duplication, so the claims in an extracted
fragment must be verified by hand at the moment of the move — see
[documentation-sweeps.md](documentation-sweeps.md) and DF-10-001.

Two things make this cheap rather than a tooling problem:

- **The assembly unit is already a lint target.** `index.md` is not
  `_`-prefixed and is in nav, so it is already in scope. Evaluating page-scoped
  rules against it means reading its include directives in order — not building
  an include-graph resolver.
- **There is precedent for suppressing rather than resolving.**
  `.markdownlint-cli2.yaml` disables MD041 ("First line in file should be a top
  level header") with the comment *"Disabled because we use `include-markdown`
  plugin for merging markdown files"*. The repo already met this class of
  fragment-only artifact and named the rule instead of teaching the tool about
  assembly.

### The include graph is not a tree

A fragment can have several hosts, and hosts can sit in different Diátaxis
quadrants. `includes/_rm-states-table.md` has four host parents; each `_oq-*.md`
has two (inline at point of use, plus the open-questions appendix).
`docs/tutorials/worked_example.md` (tutorial) and
`docs/topics/measuring_cvd/possible_histories.md` (explanation) are both
included into the reference specification's annexes. Quadrant selects the voice
rules, so a fragment's quadrant comes from its hosts and never from its own path
(DF-09-008).

### Content shape is not a usable exemption criterion

Exempting "fragments with no prose" sounds principled and does not survive
contact with the population. Of 73 fragments under `docs/`, fewer than ten are
genuinely content-free — the six `vultron-spec/includes/_*-table.md` files,
`process_models/cs/_events_table.md`, and
`measuring_cvd/_table_possible_histories.md`. The rest carry prose, *including
the ones that look content-free*: `_em_blurb.md` is five lines and a pure
admonition; `_nda_sidebar.md` is a pure admonition carrying fourteen lines of
substantive argument; and `measuring_cvd/_history_constraints.md`, which reads as
a table, has seven lines of prose around it. "Skip pure admonitions" would exempt
exactly the wrong files — and classifying by content shape means reading every
file, which is what linting is.

### A gate that resolves zero targets must fail

`check-docs-sync` calls `lint-docs` a blocking gate. When PR #3265 wrote the 35
fragments, the gate resolved to an empty target set and reported success. A
gate that checks nothing and passes is worse than no gate, because the false
clean signal suppresses the review it replaced (DF-09-009).

### Auto-fix scale is about edit kind, not file count

Whether a fix is safe to apply in bulk depends on whether it is a deterministic
substitution or a model rewriting prose, not on how many files are in the target
set. `markdownlint --fix` and `black` run tree-wide with no threshold because
their edits are substitutions. An LLM deleting filler "where the sentence
survives it" or rewriting a sentence for a quadrant's voice carries per-edit
risk that does not shrink with volume. A file-count guard conflates the two: it
blocks the safe fixes above the threshold and permits the risky ones below it.

### `codespell` is the mechanical floor for spelling

Spelling is the only style rule in this project with off-the-shelf tooling, so
it is the only one that need not depend on an agent noticing. `codespell` is to
be configured in `pyproject.toml` with `builtin = "en-GB_to_en-US"` and run as a
stock pre-commit hook over `docs/` (#3318; nothing is configured yet).

Note that `builtin` *replaces* `codespell`'s default dictionaries rather than
adding to them, so a word absent from `en-GB_to_en-US` is not checked at all —
which is why an `ignore-words-list` entry may have no measured case under this
setting and still be worth keeping.

Its scope cannot be widened. `behaviour` appears in `vultron/` and `test/` as
`py_trees.behaviour.Behaviour` — a third-party API — well over a thousand times
across more than two hundred files. `notes/` and `specs/` are outside SG-37's
scope by the style guide's own scope table.

Three hazards, all silent, all found by measurement rather than anticipated:

- **`codespell` has no notion of a code fence.** `docs/howto/wire_capability.md`
  uses `py_trees.behaviour.Behaviour` on ten lines, in fences and inline code
  spans. `--write-changes` would rewrite documentation into code that raises
  `AttributeError`. An `ignore-regex` for the API name covers both tokens in one
  match.
- **`codespell` will rewrite its own config.** Run against the repo root with
  `write-changes` in `pyproject.toml`, it "corrects" the `ignore-regex` line and
  destroys the pattern protecting the API name. Keep `write-changes` in the hook
  args (as `markdownlint` carries `--fix`) and restrict the hook with
  `files: ^docs/.*\.md$`.
- **`skip` patterns must match the path as `codespell` sees it.** A
  `./`-prefixed pattern silently fails to match when the target is passed as
  `docs/`, more than doubling the finding count with no error.

The generalizable rule: what makes `--write-changes` safe is not the dictionary
but an audit that no finding sits inside a code fence, an inline code span, an
external citation title, or a link target. Correcting someone else's published
paper title is a defect, not a fix.
