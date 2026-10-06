---
status: accepted
date: 2026-09-17
created: 2026-09-17
updated: 2026-09-17
revision: 1
deciders: Allen D. Householder
consulted: —
informed: —
stakeholder_type: [project-contributor]
---

# Lint Fragments as Source, and Evaluate Page-Scoped Style Rules on the Rendered Page

## Context and Problem Statement

`lint-docs` is the semantic prose linter for `docs/`. It checks what
`markdownlint-cli2` and `mkdocs build --strict` cannot see: terminology, voice,
concept order, filler, spelling, acronym expansion. Its Phase 1 target
resolution dropped "anything matching `not_in_nav`'s generated patterns", and
that list includes `_*.md`.

The Vultron Protocol Specification is assembled entirely from `_*.md` fragments
via the `mkdocs-include-markdown` plugin. So the largest reference document in
the tree — 35 fragments, roughly 2,800 lines of normative prose — was outside the
target set of the tool whose job is checking it. So were 38 other fragments
elsewhere under `docs/`.

The specification is published as a Reference section of pages, each a thin shell of `include-markdown` directives over the same fragments.
A routing landing page links six body pages, one page per annex, an Open Questions page, and an all-in-one page that renders every section fragment in document order.
Each section fragment is authored once, and each one a body or annex page includes appears on at least two pages: that page and the all-in-one page.

Two facts make this more than a missed pattern.

**The exemption was written for a category the specification does not belong
to.** The `_` prefix means "exclude from the MkDocs nav". `lint-docs` read it as
"this is not really a page". Those are different claims, and the second is false
for prose-heavy normative reference material that merely happens to be
*delivered* as fragments.

**The gate that should have caught this reported success.** `write-docs` step 1
and `check-docs-sync` step 3 both invoke `lint-docs`, and `check-docs-sync`
calls it a blocking gate (DF-09-001). When PR #3265 wrote the 35 fragments, the
gate resolved to an empty target set and passed. An American-spelling regression
("unmodelled") was introduced during that review round and survived
`markdownlint`, `mdlint.sh`, and a clean strict build. Seven further SG-37
violations were still resident in the fragments when this decision was taken.

The question is not merely *whether* to lint fragments, but *which rules can be
evaluated against a fragment at all*.

## Decision Drivers

- Some style rules are page-scoped by construction.
  SG-07 and DF-09-003 require acronym expansion "at first use on each page".
  Applied to the fragments standalone, the rule demands a fresh expansion in every fragment that uses the acronym, though several fragments render together on one body page and all of them render on the all-in-one page: across the document that is 12 expansions of "VFD", 10 of "RM", 9 of "EM", 8 each of "CS" and "PEC", 5 of "CVD".
  SG-10 concept order is a property of the assembled page.
  SG-21, SG-39 and SG-41 refer to the H1 and the nav label, which a fragment does not have — and `heading-offset` demotes the headings it does have.
- Findings must carry usable line numbers. The document is roughly 2,800 lines
  and is edited as fragments, so a finding located in the assembly is a finding a
  maintainer cannot act on directly.
- The include graph is not a tree.
  `includes/_rm-states-table.md` has several host parents, one of them the Explanation page `docs/topics/case_lifecycle/a_case_under_vultron.md`.
  Most of the specification's `_oq-*.md` files are included at point of use, in the open-questions appendix, and on the Explanation page `docs/topics/future_work/open_questions.md`.
  Every section fragment a body or annex page includes is rendered by at least two pages: that page and the all-in-one page.
  Hosts cross Diátaxis quadrants: `docs/tutorials/worked_example.md` and `docs/topics/measuring_cvd/possible_histories.md` are both included into the reference specification's annexes.
  Quadrant selects the voice rules, so a fragment's quadrant cannot be read off its own path.
- Prefer existing tooling over new project-specific machinery. Anything built
  here has to be maintained alongside `markdownlint-cli2` and MkDocs, which
  already own mechanical markdown and link validity respectively.
- `lint-docs` is prompt-only. It has no scripts, so any "resolver" would be
  prose instructions an agent follows, not code — and prose instructions are
  the thing most likely to be skipped under context pressure.

## Considered Options

- **Suppress the page-scoped rules on fragments; evaluate them on the rendered
  page** (chosen)
- **Exempt fragments by content shape** — skip files with no prose (pure table,
  pure diagram, pure admonition) and lint the rest
- **Carve out the specification only** — add
  `docs/reference/vultron-spec/**` as an explicit include overriding `_*.md`
- **Lint the assembled page instead of the fragments**
- **Build an include-graph resolver** that maps each fragment to its hosts and
  computes the applicable rule set per fragment
- **Adopt Vale** as a general-purpose prose linter and express the style guide
  as Vale rules

## Decision Outcome

Chosen option: **suppress the page-scoped rules on fragments; evaluate them on
the rendered page.**

A fragment is linted as source, with its own line numbers, for every rule whose scope is a sentence or a block.
The rules whose scope is a page — SG-07, SG-09, SG-10, SG-11, SG-12, SG-21, SG-32, SG-33, SG-39, SG-41, SG-44 — are not evaluated against a fragment.
They are evaluated against every assembling page: each page that includes fragments, assessed as it is published (DF-09-003).

For the Protocol Specification, under `docs/reference/vultron-spec/`, the assembling pages are:

- the six body pages `introduction.md`, `layers.md`, `tracking-models.md`, `interactions.md`, `conformance.md` and `considerations.md`;
- the seven annex pages, `annex-a-single-vendor.md` through `annex-g-capability-shapes.md`;
- `open-questions.md`;
- `full.md`, the all-in-one page, which includes every section fragment in document order;
- the landing page `index.md`, a routing page (DF-11-005) whose only fragment is the shared tip `_full-page-tip.md` that every content page also carries.

`notes/rfc-spec-authoring.md` § "Page Map" lists the fragments each page includes.

No new machinery is needed, because every assembling page is already in the target set: none is `_`-prefixed.
`full.md` is outside the nav and excluded from search, and it is a target all the same, because nav visibility is not a lint-scope class (below).
The only instruction needed is to read each page's include directives in order.

A fragment rendered by several pages is assessed on each of them.
An acronym is expanded at its first use on every page that uses it, so the fragment that opens a body page may carry an expansion that an earlier page already made, and `full.md` then renders both.
That repetition is SG-44 and DF-11-007 working: each page is self-sufficient for a reader who lands on it directly.
It is not a defect on `full.md`, whose first use is still expanded.

Quadrant is a property of the host page, not the fragment path. A fragment with
several hosts must satisfy each of them.

This follows a precedent already in the repository. `.markdownlint-cli2.yaml`
disables MD041 ("First line in file should be a top level header") with the
comment *"Disabled because we use `include-markdown` plugin for merging markdown
files"*. The repository had already met this class of fragment-only artifact and
resolved it by naming the page-scoped rule and switching it off, rather than by
teaching the tool about assembly.

Two changes follow from the same reasoning.

**The exemption list becomes an explicit content-class list.** `not_in_nav` is a
nav-visibility mechanism, and its list also holds `developer/**` and
`agents/*.md`, which the style guide's scope table puts explicitly *in* scope.
Pointing lint scope at a nav mechanism is the general form of the defect this
ADR corrects; `_*.md` was one instance of it.

**The auto-fix guard gates on edit kind, not file count.**
A guard that switches to report-only above a number of target files gates on a proxy for the property that matters: whether a fix is a deterministic substitution or a model rewriting prose.
SG-08, SG-35 and SG-37 are substitutions and are safe at any scale, which is why `markdownlint --fix` and `black` run tree-wide with no threshold.
SG-02, SG-24 and SG-17 through SG-19 are model rewrites whose per-edit risk does not shrink with volume.
A count conflates them, blocking the safe fixes above the threshold while permitting the risky ones below it.
It is also partly redundant: SG-17 through SG-19 already self-cap on "*isolated*" occurrences, with SG-20 routing pervasive drift to a Phase 4 finding.

**`codespell` becomes the mechanical floor for SG-37.**
Of the eight rules violated in PR #3265, spelling is the only one with off-the-shelf tooling.
`codespell` is configured in `pyproject.toml` and runs as a stock pre-commit hook, so British spelling does not depend on an agent noticing it.

The `lint-docs` target set, the rule-scope split, the empty-target-set failure and the `codespell` configuration are implemented by #3318.
The page set listed above is built by #4061.

### Consequences

- Good, because the largest reference document in the tree comes under the
  linter, and the seven resident SG-37 violations become visible.
- Good, because findings keep source line numbers, so they are actionable
  without mapping back through the assembly.
- Good, because no project-specific tooling is added. The change is skill prose,
  a `pyproject.toml` block, and an upstream pre-commit hook.
- Good, because the empty-target-set failure removes a gate that reported
  success while checking nothing — the most dangerous state a gate can be in.
- Bad, because the fragment/page rule split is a distinction a future editor of
  `lint-docs` must preserve. Collapsing it in either direction reintroduces one
  of the two failure modes: false positives on every fragment, or no coverage
  at all.
- Bad, because a fragment's page-scoped findings depend on which pages render it.
  Moving a fragment to another page, or reordering a page's includes, can create a page-scoped finding without any edit to the fragment.
- Bad, because SG-37 enforcement is split across two mechanisms — a dictionary for the mechanical class and agent reading for the rest.
- Neutral, because every fragment remains excluded from nav.
  Nav visibility and lint scope are independent, which is the point.

## Validation

Validated by all three of:

- `lint-docs` invoked on `docs/reference/vultron-spec/` resolves a non-empty target set including every fragment under that directory.
- `codespell` over `docs/` with the configured dictionary and exclusions exits 0.
- `check-docs-sync` fails rather than passes when its `lint-docs` invocation
  resolves to zero targets.

*Validated 2026-09-28 (#3318):* all three hold.
The `lint-docs` target-set rule is skill prose, so the first and third are checked by reading the skill; the second is the `codespell` pre-commit hook and `codespell docs/` exiting 0.
The first is to be re-checked when #4061 lands: the resolved target set then also holds every assembling page the decision lists, `full.md` included.

## Pros and Cons of the Options

### Exempt fragments by content shape

Skip files with no prose; lint the rest.

- Good, because it targets the property the original exemption was reaching for.
- Bad, because the population does not have that shape. Of 73 fragments, fewer
  than ten are genuinely content-free — the six `includes/_*-table.md` files,
  `cs/_events_table.md`, and `measuring_cvd/_table_possible_histories.md`. The
  rest carry prose, *including the ones that look content-free*: `_em_blurb.md`
  is five lines and a pure admonition; `_nda_sidebar.md` is a pure admonition
  carrying fourteen lines of substantive argument about NDAs and bug bounty
  programs; even `measuring_cvd/_history_constraints.md`, which reads as a table,
  has seven lines of prose around it. "Skip pure admonitions" would exempt
  exactly the wrong files.
- Bad, because classifying by content shape requires reading every file, which
  is what linting is. The rule buys nothing and adds a judgment call per file.

### Carve out the specification only

Add `docs/reference/vultron-spec/**` as an explicit include.

- Good, because it is the smallest possible change.
- Bad, because it leaves 38 fragments uncovered and leaves `not_in_nav` as the
  source of truth for lint scope, so the next fragment-assembled page inherits
  the same gap.
- Bad, because it does not avoid the hard part. The 35 specification fragments
  still trip every page-scoped rule, so the false-positive problem arrives
  anyway, just scoped to one directory.

### Lint the assembled page instead of the fragments

- Good, because it matches how the document is read, and page-scoped rules are
  correct by construction.
- Bad, because findings land in the assembly rather than the source, so every fix requires mapping a line number back through every include of `full.md`, roughly 2,800 lines.
- Bad, because the assembled artifact cannot be edited. Every finding needs
  that mapping before it can be acted on.

### Build an include-graph resolver

Map each fragment to its hosts and compute the applicable rule set.

- Good, because it handles multi-host fragments and cross-quadrant includes
  explicitly rather than by convention.
- Bad, because it is project-specific machinery to maintain for a problem the
  MD041 precedent shows can be resolved by naming the rules instead.
- Bad, because `lint-docs` is prompt-only, so the "resolver" would be prose an
  agent follows. Reading a page's include lines in order achieves the same
  result without a resolver to keep in sync with the plugin's arguments.

### Adopt Vale

- Good, because it would make more of the style guide mechanically enforced
  rather than agent-checked, which is the deeper limitation here.
- Bad, because it is a new dependency whose rule definitions would need
  maintaining alongside the style guide, replacing prose we own with a rule
  dialect we would also own. The maintenance added exceeds the maintenance
  removed.
- Neutral, because the decision is separable. Nothing here blocks adopting Vale
  later if agent-checked rules prove insufficient.

## More Information

The `codespell` configuration is narrow. The exclusions below are the ones with a
measured case; #3318 carries the full list, including the remaining `skip`
entries for `docs/adr`, `docs/reference/code`, `docs/reference/case_states`,
`pyproject.toml`, and the draft spec file.

| Exclusion | Reason |
|---|---|
| `ignore-words-list = "dialogues"` | `## Example Dialogues` in the glossary becomes "Dialogs", a UI term |
| `ignore-words-list = "cna,ot"` | Defensive only. Both fire under `codespell`'s default dictionaries — `CNA` is corrected to `CAN` 37 times — but not under `builtin = "en-GB_to_en-US"`, which *replaces* the defaults rather than adding to them. Kept so that widening the builtin later does not silently mangle `CNA` |
| `ignore-regex` for `py_trees\.behaviour\.Behaviour` | `docs/howto/wire_capability.md` uses the third-party API on ten lines, in code fences and inline code spans. `codespell` has no notion of a code fence, so `--write-changes` would rewrite documentation into code that raises `AttributeError` |
| `ignore-regex` for `Analysing an Email Corpus` | The title of a cited external paper. A published title is not ours to correct |
| `skip` for `docs/reference/codebase` | Regenerated by `acquire-codebase-knowledge`; fix the generator, not the output |

Scope is `docs/` only. `vultron/` and `test/` cannot be included at all:
`behaviour` appears there as `py_trees.behaviour.Behaviour` — a third-party API —
well over a thousand times across more than two hundred files. `notes/` and
`specs/` are outside SG-37's scope by the style guide's own scope table.

`write-changes` belongs in the pre-commit hook arguments rather than in
`pyproject.toml`, matching how `markdownlint` carries `--fix`. The config stays
declarative, and a manual `codespell docs/` is read-only rather than silently
rewriting a developer's tree.

Two hazards found while validating the configuration are recorded because both
are silent:

- With `write-changes` in `pyproject.toml` and the whole repository as the
  target, `codespell` rewrites `pyproject.toml` itself, mangling the
  `ignore-regex` that protects the py_trees API. The hook's `files:` filter and
  an explicit `skip` entry both prevent this.
- `skip` patterns must match the path as `codespell` sees it, which depends on
  how the target is passed. A `./`-prefixed pattern silently fails to match when
  the target is given as `docs/`, inflating the finding count from 94 to 222
  with no error.

The general lesson for the implementation: what makes `--write-changes` safe is
not the dictionary but an audit that no finding sits inside a code fence, an
inline code span, an external citation title, or a link target.

`notes/rfc-review-rubric.md` keeps the retired warning that recorded this gap, per that rubric's own rule not to delete retired items, and names `lint-docs` and `codespell` as its covering mechanisms.

Design rationale and the fragment inventory: `notes/documentation-strategy.md` § "Nav Visibility Is Not a Content Class: Fragments vs. Assembly Units".
The Protocol Specification's pages and the fragments each one includes: `notes/rfc-spec-authoring.md` § "Page Map".

Generated spec requirements: `diataxis-requirements.yaml` DF-09-003,
DF-09-007, DF-09-008, DF-09-009.
