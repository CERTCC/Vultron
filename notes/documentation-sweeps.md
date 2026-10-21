---
title: Documentation Sweeps — Verification Budget
status: active
kind: guidance
description: >
  Rules for moving, extracting, or republishing content under docs/: a moved
  claim must be re-verified against its authority, shared content belongs in
  an include-markdown fragment, and a table that mirrors a code or spec
  inventory keeps only the columns a test can hold.
related_notes:
  - notes/diataxis-framework.md
  - notes/documentation-strategy.md
  - notes/site-information-architecture.md
  - notes/specs-vs-adrs.md
related_specs:
  - specs/diataxis-requirements.yaml
  - specs/meta-specifications.yaml
---

# Documentation Sweeps — Verification Budget

A mechanical pass over prose — a naming sweep, a Diátaxis extraction, a page
split — forces an agent to read claims it would otherwise skim. A sweep that
only *moves* text carries the source's errors forward with more authority than
they had in place, and the move is the cheapest moment to catch them.

## Moving a claim is not verifying it

**Rule.** When a sweep moves, extracts, or republishes content, re-read every
claim as an assertion and verify it against its authority before committing
(DF-10-001). Authorities, in descending precedence:

1. The source code — for any claim about what the implementation does.
2. A spec entry in `specs/*.yaml` — for any normative statement.
3. A reference page in `docs/reference/` — for any factual summary.

"The original page said this" is not an authority.

**Reason.** In place, a diagram is page furniture; on a page whose job is to
justify a design, each arrow becomes a falsifiable claim. A faithful copy
satisfies "all content accounted for" while republishing a falsehood. The
mechanism is not specific to `docs/`: it applies to a sweep over `specs/` too.

A ratchet for the claim class you moved is the best outcome of a sweep, not a
substitute for reading: `test/architecture/test_docs_activity_verbs.py` holds
only activity-to-verb pairings, and only in the shapes it recognises.

**Budget the verification before starting.** Before a sweep of more than a few
pages, identify which moving content carries first-order empirical claims (code
behavior, verb attributions, state transitions) and budget time to check them.

## Prefer includes over copying

When the same content belongs on two pages, make an `{% include-markdown %}`
fragment instead of copying prose — one source, many render points
(DF-10-002). Three mechanics matter:

- **Placement.** Put a fragment beside its hosts as `_<slug>.md` (e.g.
  `docs/topics/process_models/cs/_events_sigma.md`). Reserve `docs/includes/`
  for banners included across the whole tree (`normative.md`), which carry no
  `_` prefix.
- **Path.** The include argument resolves relative to the *including* file, not
  to `docs/`: `mkdocs.yml` sets no `base_path`. A `docs/`-rooted argument fails
  the strict build.
- **Lint scope.** A fragment is linted as source for sentence- and block-scoped
  rules; page-scoped rules (acronym first use, concept order) run on the
  assembled page (DF-09-007), and its quadrant comes from its including pages
  (DF-09-008). Pass a new fragment to `lint-docs` explicitly. Lint checks the
  prose, not the claims, so the claims are still verified at the move.
- **Near-copies merge too.** A copy that has drifted is merged into one
  fragment, not left as two. Pick the wording that is correct against its
  authority and verify it at the merge (DF-10-001); two near-copies are twice
  the upkeep and already disagree (SG-43).

## Mirrored tables rot in the column no test can hold

**Rule.** A doc table that mirrors a code, spec, or config inventory keeps only
columns a test can hold; triage the columns before syncing it (MS-16-002).

**Reason.** Such tables drift unevenly: source-derivable columns stay roughly
right while the columns no test could check go wholly wrong — and they read as
confident answers, not as uncertainty (a per-actor pass/fail column naming
long-closed issues, ISSUE-3337; a free-prose column naming four actors for a
five-actor scenario, CONCERN-3466).

### The column-triage procedure

1. **Disaggregate first.** A column answering two questions at once
   ("participants *and* notable feature") is unverifiable as a unit while each
   part may be derivable. Split it, then sort each part. Splitting the scenario
   table's column is what let ADR-0098 generate the whole table from the
   `@scenario` decorator.
2. **Ratchetable** (derivable from source, specs, or config): keep it and add
   the ratchet in the same PR, following
   `test/ci/invariants/test_universal_semantic_types.py` or
   `test/architecture/test_codebase_docs_paths.py`.
3. **Not ratchetable** (a runtime outcome, a schedule, a forecast, a count that
   changes under you): remove it and point at whatever holds the live answer. A
   doc that resists this is trying to be a dashboard, and a dashboard in git is
   always stale.

The discriminator is MS-16-002: could a test fail on this sentence? A restated
count (MS-16-001) is the commonest instance; see `notes/specs-vs-adrs.md`
§ "Never State Unverifiable, Drift-Prone Facts in Long-Lived Docs".
