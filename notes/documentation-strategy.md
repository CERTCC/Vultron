---
title: Documentation Strategy Notes
status: active
kind: guidance
description: >
  How to trust and edit Vultron's documentation: the three documentation
  generations and which wins on conflict, which of the three behavior views to
  edit, and the MkDocs build rules — withholding, link and anchor checks over
  built output, URL permanence, fragments vs. assembly units, and the codespell
  floor.
related_notes:
  - notes/bt-integration.md
  - notes/case-state-model.md
  - notes/documentation-sweeps.md
  - notes/message-type-reference.md
  - notes/rfc-review-rubric.md
  - notes/rfc-spec-authoring.md
  - notes/site-information-architecture.md
  - notes/spec-authoring-rules.md
  - notes/vocabulary-registry.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/docs-build-workflow.yaml
  - specs/spec-registry.yaml
relevant_packages:
  - vultron/bt
  - vultron/core
  - vultron/demo
  - vultron/metadata/docs
  - vultron/wire/as2
---

# Documentation Strategy Notes

Where a page sits and what it may assume of its reader is a separate question,
owned by [site-information-architecture.md](site-information-architecture.md)
(ADR-0102, DF-11). This note covers how far to trust what a page says, which
page to edit, and how the build checks what it publishes.

## Documentation Generations and Trust

The documentation was written in three generations, and they conflict.

1. **Pre-implementation design docs** — `docs/topics/**`,
   `docs/reference/formal_protocol/**`, `docs/howto/**`, written before the
   ActivityStreams implementation. Trust them for *intent and design
   rationale*, not for field names, class hierarchies, or API details.
2. **State-based model and simulator** — `vultron/core/case_states/`,
   `vultron/core/states/`, `vultron/bt/`, built from the SEI reports
   [*A State-Based Model for CVD*](https://www.sei.cmu.edu/documents/1952/2021_003_001_737890.pdf)
   and [*Designing Vultron*](https://www.sei.cmu.edu/documents/1954/2022_003_001_887202.pdf).
   They predate the ActivityStreams vocabulary: mine them for protocol logic,
   but never reuse them directly in handlers (`notes/bt-integration.md`).
3. **Current ActivityStreams implementation** — `vultron/wire/as2/`,
   `vultron/adapters/`, `vultron/core/behaviors/`, `vultron/core/use_cases/`.
   `docs/howto/activitypub/` and `specs/` describe this generation.

**When a doc and the implementation diverge**, decide which is wrong before
changing either: a divergence with documented rationale means update the doc;
one without rationale means investigate; an outdated design with no
implementation is design history (see site-information-architecture's
working-record exclusion).

**State machine enums are authoritative.** When docs and an enum disagree on
state names, the enum wins and the doc is updated, unless a maintainer has
named the enum a bug. Canonical files: `vultron/core/states/rm.py`,
`vultron/core/states/em.py`, `vultron/core/states/cs.py`.

**Check transitions against the formal protocol, under the specification.**
`docs/reference/formal_protocol/` (`states.md`, `transitions.md`, `messages.md`)
defines correct transitions; check a new handler or BT node against it and never
treat it as historical. It is informative, though: where it differs from the
Protocol Specification, the specification governs (DF-12-007).

## Three Views of Behavior, and Which One to Edit

Behavior is documented from three directions. Writing into the wrong one is the
recurring mistake, because all three describe "what an actor does".

| View | Answers | Quadrant | Source of truth |
|---|---|---|---|
| `docs/topics/behavior_logic/*_bt.md` | What behavior does the protocol call for, and why | Explanation | *Designing Vultron* + the `vultron/bt/` simulator |
| `docs/topics/behavior_logic/use-cases/` | Per use case: what is mechanical, what is delegated, what is emitted | Explanation | `vultron/core/behaviors/` + the RMB/EMB/CSB/CP specs |
| `docs/reference/behaviors/` | What trees the prototype builds today | Reference | `vultron/core/behaviors/`, rendered at build time |

- The `*_bt.md` pages are the original design and the formal behavioral
  specification — working record, reached through
  `topics/behavior_logic/original_design.md` (#3528). They change only when the
  *design* changes; never update them to track implementation drift.
- The `use-cases/` pages hold conceptual statements about current behavior:
  call-out points and the judgment each represents, load-bearing ordering
  constraints, and the obligations a participant carries whether or not it uses
  behavior trees. Keep node inventories out: `docs/reference/behaviors/`
  generates those.

## Sequence Diagrams Follow the Demo Scripts

**Rule.** The demo scenarios are the canonical reference for each workflow, so
a diagram in `docs/howto/activitypub/activities/*.md` that disagrees with its
scenario is the diagram's defect. When you touch a scenario, read its guide's
diagram in the same change — the arrows, not just the node names.

**Reason.** `test/architecture/test_docs_activity_verbs.py` checks the verb and
the wire-form composition each diagram node and each guide's prose attribute to
an activity, against the registered `ActivityPattern`. No check reads the
*edges*: a flowchart can route an activity into the wrong loop while every
name and verb stays right (#3456).

**Draw inter-actor flows, not internal handler choreography.** A how-to reader
acts on the messages between actors, not on calls inside one. When a diagram
draws internals that have since changed, retire it rather than resync it, as
was done for the `/api/v1` handler diagrams that ADR-0011 removed.

## MkDocs `not_in_nav`, `exclude_docs` and `draft_docs` Are Not the Same

Files excluded from nav MUST also be listed in `not_in_nav`; the overlay list
*replaces* the base list rather than extending it.

- `not_in_nav` — no nav entry and no omitted-file warning; the file is still
  published.
- `exclude_docs` — not processed at all, in `build` and `serve` alike.
- `draft_docs` — published by `mkdocs serve`, absent from `mkdocs build`. This
  is how to withhold an artifact while keeping it reviewable locally
  (`docs/developer/`, `docs/ns/`).

Three mechanics bite:

- **A `draft_docs` pattern withholds static files too**, not only pages
  (`docs/ns/context.jsonld` goes with `docs/ns/index.md`). Do not reach for
  `exclude_docs` to catch the non-Markdown half.
- **`draft: true` in page frontmatter does nothing** — it is a Material blog
  plugin key. Withholding happens in `mkdocs.yml` and nowhere else.
- **Patterns are relative to `docs_dir` and fail silently when mis-anchored**
  (DOCBW-03-004).

The withholding claim must be compared with the build output: `uv run
docs-withheld` does that after every site build (DOCBW-03-005), checking the
outcome rather than the `mkdocs.yml` mechanism. Its declaration of what is
withheld is the home of the publication axis (ADR-0106).

## Withholding Has Two Axes: Publication and Reference

`docs-withheld` answers "did a withheld artifact produce files in `site/`".
"Does anything *link to* a path the build did not produce" is a separate axis,
checked by `uv run docs-links` over built output (DOCBW-03-007).

**`mkdocs build --strict` is a claim about the pages MkDocs parsed, not about
the bytes it emitted.** Two ways a link to a withheld page clears it:

- **Exec-block output.** MkDocs rewrites and validates relative `.md` links with
  a treeprocessor on its own `Markdown` instance; `markdown-exec` renders on a
  child instance without it. A link printed by a build-time generator is never
  validated. Generators live under `vultron/metadata/` *and* `docs/_scripts/`,
  so an audit scoped to one directory misses some.
- **Excluded targets are downgraded on purpose.** A hand-written link to an
  excluded page logs at INFO (`min(INFO, validation.links.not_found)`), below
  anything `--strict` fails on, while the href is still rewritten.

Committed-file generators (`adr-index`, `docs-site`) are seen by `--strict`
and have staleness checks, but seeing a link is not resolving it. Hence three
design rules for the reference-axis check, each a consequence of how a dead
link hid (#3574):

- **Check resolution, not link form.** A correctly rewritten link to an unbuilt
  page looks exactly like a good one.
- **Walk every built page, not a crawl.** A crawl from one entry point never
  inspects pages nothing links to, and reports success over what it reached.
  Nav absence and crawl reachability are different properties.
- **Run unconditionally.** The withholding lives in `mkdocs.yml`; the generator
  that advertises the page lives in `vultron/` or `docs/_scripts/`. A `docs/**`
  path filter — on a step *or* on the workflow trigger — is the wrong predicate
  for a defect neither file has to touch.

**Derive rather than mirror** where you can: `whats_new.py::_unpublished_spec`
reads `draft_docs` and `exclude_docs` from `mkdocs.yml` with the same matcher
MkDocs uses, so its idea of "published" cannot drift. Prefer that in any new
generator; the gate covers the ones that do not.

## Exec-Block Anchors Are Invisible to `--strict`, Too

The child-instance mechanism hides *targets* as well as links. MkDocs collects
anchors from the parent element tree and the page's own Markdown source, so it
misses ids inside exec-block output; `markdown-exec` splices back **headings
only**. A heading `{#clp-15}` printed by an exec block is a valid target and an
`<a id="clp-15-001">` beside it was not. The resulting warning ("does not
contain an anchor") is misleading: the built HTML does contain it.

Keep the two consequences apart:

- **Targets.** `vultron/metadata/docs/anchor_ids.py`, under `hooks:` in
  `mkdocs.yml`, adds every id in each rendered page to its anchor set, using
  MkDocs' own collection rule. Prose may therefore cite a requirement by its
  own anchor; a fabricated anchor still fails.
- **Links.** Links *printed by* an exec block are still never validated, and
  `docs-links` strips fragments by design. A generator that emits `#fragment`
  links needs its own test that each fragment exists on its target page — for
  the spec pages, `test_render_for_kind_cross_links_resolve` in
  `test/metadata/specs/test_docs_render.py` (DF-09-009).

## The Third Axis Is Time: a URL Once Served Must Keep Answering

The publication and reference axes compare one build with itself; neither sees
a URL an earlier build served and this one dropped. `uv run docs-legacy-urls`
(DOCBW-03-008) is that comparison. Easy to get wrong:

- **The evidence is committed before `publish` advances.**
  `vultron/metadata/docs/legacy_urls_baseline.txt` only grows (`--snapshot
  <ref>` adds a ref's pages, drops none): a URL cited once can be cited forever.
- **Snapshot the incoming publish, not the outgoing one.** A pull request to
  `publish` fails until every page its head builds is recorded (DOCBW-03-012):
  run `--snapshot origin/main` on `main` and commit it. Recording each publish as
  it ships covers every earlier one, and the check reuses the snapshot's
  definition of a built page, so the two cannot disagree.
- **A snapshot records what the ref built, not what it held** — it applies that
  ref's own `draft_docs` and `exclude_docs`.
- **The baseline lists built pages, not nav entries.** Fragments built as their
  own pages answered 200 too. "Not in the nav" says nothing about whether a URL
  exists.
- **Withdrawn is not redirected.** A page retired on purpose is declared in
  `withheld.py`, because a redirect to an unrelated page claims the content
  moved. Content folded into another page, or a page whose text named its
  successor, is a move and redirects.
- **Confirm a rename by content, not filename** — a look-alike successor page
  may cover different material.

Both publication-side checks run through one composite action,
`.github/actions/check-site-publication`, in `docs-build-check.yml` and in
`deploy_site.yml`, so the workflow that ships is gated by exactly what the
workflow that reviews is gated by.

## Nav Visibility Is Not a Content Class: Fragments vs. Assembly Units

`not_in_nav` (and the `_` prefix that keeps a file out of nav) answers "does
this file get a nav entry", not "do prose rules apply to it". Prose delivered
as fragments is still prose (DF-09-007 through DF-09-009, ADR-0092).
`lint-docs` § "Fragments and assembly units" implements the split below;
collapsing it either way reintroduces false positives on every fragment or no
coverage at all.

### The two kinds of file

A page assembled from `{% include-markdown %}` directives is an **assembly
unit**; the files it pulls in are **fragments**.

| Rule scope | Evaluate against | Examples |
|---|---|---|
| Sentence or block | the fragment, with its own line numbers | spelling, filler, sentence shape, list and table discipline, Mermaid title and type, reference voice |
| Page | the assembly unit | acronym first use (DF-09-003), concept order (DF-09-005), page furniture and anything naming the H1 or nav label |

A page-scoped rule applied to a fragment reports an artifact of the split —
one acronym expansion per fragment on a single published page. Extracting a
fragment keeps its prose in `lint-docs`' targets (`_*.md` and
`docs/includes/**` are targets), so deduplicating by extraction (DF-10-002)
costs no coverage; the claims are still verified at the move
([documentation-sweeps.md](documentation-sweeps.md), DF-10-001). Every assembly
unit is already a target (no page is `_`-prefixed), and evaluating page-scoped
rules means reading its include directives in order, not building a resolver.

### The include graph is not a tree

A fragment can have several hosts in different Diátaxis quadrants (every
Protocol Specification section also renders on `full.md`; some `_oq-*.md`
files render on an Explanation page too). Quadrant selects the voice rules, so
a fragment's quadrant comes from its hosts, never from its own path
(DF-09-008).

### Content shape is not a usable exemption criterion

"Skip fragments with no prose" exempts the wrong files: pure admonitions and
table-looking fragments often carry substantive prose, and classifying by
shape means reading every file, which is what linting is.

### A gate that resolves zero targets must fail

A gate that checks nothing and passes is worse than no gate: its false clean
signal suppresses the review it replaced (DF-09-009).

### Auto-fix scale is about edit kind, not file count

A deterministic substitution (`markdownlint --fix`, `ruff format`) is safe
tree-wide; a model rewriting prose carries per-edit risk that does not shrink
with volume. A file-count guard blocks the safe fixes above its threshold and
permits the risky ones below it.

### `codespell` is the mechanical floor for spelling

Spelling is the one style rule with off-the-shelf tooling. `codespell` runs as
the upstream pre-commit hook over `docs/*.md`, configured in `[tool.codespell]`
in `pyproject.toml` with `builtin = "en-GB_to_en-US"`. `builtin` *replaces*
the default dictionaries, so a word absent from it is not checked at all. Its
scope cannot widen: `py_trees.behaviour.Behaviour` is a third-party API used
throughout `vultron/` and `test/`, and `notes/`/`specs/` are outside SG-37.

Hazards, all silent:

- **No notion of a code fence or inline code span.** Protect an API name with
  `ignore-regex`, never by editing around the hook.
- **It will rewrite its own config.** Keep `--write-changes` in the hook args,
  not `pyproject.toml`, and restrict the hook with `files: ^docs/.*\.md$`.
- **`skip` patterns are `fnmatch`ed against the full path in two shapes** — the
  walked directory (`docs/adr`) and the staged file (`docs/adr/0092-x.md`). End
  each directory pattern in `*` (`docs/adr*`); a `./` prefix never matches.
- **A hyphenated compound is one token** and is never looked up, so `lint-docs`
  still reads for SG-37.

What makes `--write-changes` safe is an audit that no finding sits inside a
code fence, inline code, an external citation title, or a link target:
correcting someone else's published title is a defect, not a fix.
