---
status: accepted
date: 2026-09-17
deciders: Allen D. Householder
consulted: —
informed: —
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
the tree — 35 fragments, 2,773 lines of normative prose — was outside the target
set of the tool whose job is checking it. So were 38 other fragments elsewhere
under `docs/`.

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

- Some style rules are page-scoped by construction. SG-07 and DF-09-003 require
  acronym expansion "at first use on each page". Applied to 35 fragments
  standalone, that demands 35 expansions of "CVD" that render as one page.
  SG-10 concept order is a property of the assembled document. SG-21, SG-39 and
  SG-41 refer to the H1 and the nav label, which a fragment does not have — and
  `heading-offset` demotes the headings it does have.
- Findings must carry usable line numbers. The document is 2,773 lines and is
  edited as fragments, so a finding located in the assembly is a finding a
  maintainer cannot act on directly.
- The include graph is not a tree. `includes/_rm-states-table.md` has four host
  parents; each `_oq-*.md` has two. Hosts cross Diátaxis quadrants:
  `docs/tutorials/worked_example.md` and
  `docs/topics/measuring_cvd/possible_histories.md` are both included into the
  reference specification's annexes. Quadrant selects the voice rules, so a
  fragment's quadrant cannot be read off its own path.
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

A fragment is linted as source, with its own line numbers, for every rule whose
scope is a sentence or a block. The rules whose scope is a page — SG-07, SG-09,
SG-10, SG-11, SG-12, SG-21, SG-32, SG-33, SG-39, SG-41 — are not evaluated
against a fragment. They are evaluated against the assembling page, which
requires no new machinery because that page is already in the target set:
`docs/reference/vultron-spec/index.md` is not `_`-prefixed and is in the nav.
The only instruction needed is to read its include directives in order.

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

**The auto-fix guard gates on edit kind, not file count.** The prior guard
switched to report-only above 20 target files. File count is a proxy for the
property that matters: whether a fix is a deterministic substitution or a model
rewriting prose. SG-08, SG-35 and SG-37 are substitutions and are safe at any
scale, which is why `markdownlint --fix` and `black` run tree-wide with no
threshold. SG-02, SG-24 and SG-17 through SG-19 are model rewrites whose
per-edit risk does not shrink with volume. The count conflated them, blocking
the safe fixes above 20 files while permitting the risky ones below it. It was
also partly redundant: SG-17 through SG-19 already self-cap on "*isolated*"
occurrences, with SG-20 routing pervasive drift to a Phase 4 finding.

**`codespell` becomes the mechanical floor for SG-37.** Of the eight rules
violated in PR #3265, spelling is the only one with off-the-shelf tooling.
`codespell` is configured in `pyproject.toml` and run as a stock pre-commit
hook, so British spelling stops depending on an agent noticing it.

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
- Bad, because SG-37 enforcement is now split across two mechanisms — a
  dictionary for the mechanical class and agent reading for the rest.
- Neutral, because 74 fragments remain excluded from nav. Nav visibility and
  lint scope are now independent, which is the point.

## Validation

`lint-docs` invoked on `docs/reference/vultron-spec/` resolves a non-empty
target set including the 35 fragments. `codespell` over `docs/` with the
configured dictionary and exclusions exits 0. `check-docs-sync` fails rather
than passes when its `lint-docs` invocation resolves to zero targets.

## Pros and Cons of the Options

### Exempt fragments by content shape

Skip files with no prose; lint the rest.

- Good, because it targets the property the original exemption was reaching for.
- Bad, because the population does not have that shape. Of 73 fragments, about
  six are genuinely content-free (`includes/_*-table.md`, `cs/_events_table.md`,
  `measuring_cvd/_history_constraints.md`). The rest carry prose, *including the
  ones that look content-free*: `_em_blurb.md` is five lines and a pure
  admonition; `_nda_sidebar.md` is a pure admonition carrying ten lines of
  substantive argument about NDAs and bug bounty programs. "Skip pure
  admonitions" would exempt exactly the wrong files.
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
- Bad, because findings land in the assembly rather than the source, so every
  fix requires mapping a line number back through 24 includes across 2,773
  lines.
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

The `codespell` configuration is narrow, and each exclusion was derived from a
measured case rather than anticipated:

| Exclusion | Reason |
|---|---|
| `ignore-words-list = "cna,ot,dialogues"` | `CNA` is corrected to `CAN` 37 times; `## Example Dialogues` in the glossary becomes "Dialogs", a UI term |
| `ignore-regex` for `py_trees\.behaviour\.Behaviour` | `docs/howto/wire_capability.md` uses the third-party API on ten lines, in code fences and inline code spans. `codespell` has no notion of a code fence, so `--write-changes` would rewrite documentation into code that raises `AttributeError` |
| `ignore-regex` for `Analysing an Email Corpus` | The title of a cited external paper. A published title is not ours to correct |
| `skip` for `docs/reference/codebase` | Regenerated by `acquire-codebase-knowledge`; fix the generator, not the output |

Scope is `docs/` only. `vultron/` and `test/` cannot be included at all:
`behaviour` appears 1,114 times there as `py_trees.behaviour.Behaviour` across
142 files. `notes/` and `specs/` are outside SG-37's scope by the style guide's
own scope table.

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

The `notes/rfc-review-rubric.md` warning that recorded this gap is replaced by a
pointer to the covering mechanism, per that rubric's own instruction not to
delete retired items.

Design rationale and the fragment inventory: `notes/documentation-strategy.md`
§ "Nav Visibility Is Not a Content Class: Fragments vs. Assembly Units".

Generated spec requirements: `diataxis-requirements.yaml` DF-09-003 (amended),
DF-09-007, DF-09-008, DF-09-009.
