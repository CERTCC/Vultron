---
title: Architecture Ratchet Corpus
status: active
kind: guidance
description: >
  Rules for the shared source/markdown corpus behind test/architecture/
  ratchets, for ratchets that start from a live object, for applying the
  prefilter per definition rather than per file, for the two TB-13-004 time
  tiers, for stating whether each loose reading can miss a violation or
  invent one (and trading an inventing reading for a missing one), for the
  two meta-ratchets that police the gates themselves — one corpus, and every
  `xfail` strict — and for baselines: owner markers and the
  ratchet-versus-pinned-exemption-set split.
related_specs:
  - specs/architecture.yaml
  - specs/testability.yaml
related_notes:
  - notes/demo-scenario-tree.md
  - notes/wire-core-boundary.md
  - notes/spec-authoring-rules.md
  - notes/testing-pitfalls.md
  - notes/domain-validation.md
---

# Architecture Ratchet Corpus

Rules for the shared corpus pattern in `test/architecture/`
(`test/architecture/_corpus.py`). Normative requirements: `specs/testability.yaml`
TB-13. Why a new baseline should be a named set or a per-item marker, never a
bare count pinned to its live value, is in
[testing-pitfalls](testing-pitfalls.md) § "A Two-Sided Count Pin Races Every
Concurrent PR".

---

## Build the Corpus at Import Time

`pytest-timeout` covers test call time and fixture setup at every scope, but not
module import time. A module-level corpus is therefore exempt from the per-test
timeout; a session-scoped fixture is not, and a cold parse of the whole tree in
one would recreate the margin problem the corpus exists to fix.

Every import-time read, Python or prose, catches `UnicodeDecodeError` as well as
`OSError` (the former is not an `OSError`): an escaped error fails collection of
every ratchet module instead of skipping one file. `_corpus._read_into` is the
one read all three caches share.

## Meta-Ratchets

`test/architecture/test_ratchet_hygiene.py` holds the checks that police the
other gates. Two live there.

**One corpus.** It fails when any sibling file contains `ast.parse(` or
`.rglob(` outside `_corpus.py` (TB-13-003, TB-13-009), so every ratchet routes
discovery through the one cache. When a new ratchet needs a file set the corpus
does not offer, extend the corpus rather than reaching for a spelling the
hygiene check does not pattern-match: the rule is about one cache, not the
literal substring.

**Every `xfail` is strict.** TB-17-001 is the rule and
`test_every_xfail_is_strict` is its check: it fails on any `xfail` under
`test/` that omits or disables `strict`, generalising ARCH-21-008 from a
backlog's companion goal test to every marker. A non-strict goal xfail keeps
passing after the work lands, so the marker outlives its defect and the
assertion it guards stops being checked — the gate goes inert (#3934). A
genuine exception goes in `_NON_STRICT_XFAIL_EXEMPTIONS` with its reason — a
pinned exemption set, named `_EXEMPTIONS` so that a later entry is a baseline
`test_ratchet_baselines_name_an_owner.py` can see. The matcher keys on the
marker, so it covers a `pytest.param(marks=…)` entry, loses no subjects to a
rename (#5535), and counts a bare `@pytest.mark.xfail` as lax, that being the
laxest spelling of all and the one a call-keyed matcher misses.

## The Markdown Tier

The corpus also caches `docs/**/*.md` text for ratchets that assert
documentation prose against code: `docs_mentioning(*fragments)` and `all_docs()`,
mirroring `sources_mentioning` / `all_sources`. `all_prose()` does the same for
the authored non-Python text elsewhere — `specs/` YAML, `notes/` Markdown, and the
Markdown, YAML and text beside the code in `vultron/` — for terminology ratchets
that scan every authored word (`test_ledger_verdict_wording.py`, CLP-02-012). No
TB-13 entry governs these tiers yet; they are convention.

- **No lazy tier.** These ratchets match text and never parse, and reading every
  page at import time is an order of magnitude cheaper than the Python cold parse.
- **No directory is excluded.** If an exclusion is ever genuinely needed, match on
  the path *relative to* the scan root: testing `Path.parts` of the absolute path
  empties the whole cache for a clone under a directory with the excluded name.
- **Prefilter markdown ratchets** on a substring the same way as Python ones.

## Ratchets That Start From a Live Object

Some ratchets start from a live object — a routed use case, a tree factory —
rather than from a file scan. Two rules keep them inside TB-13:

- **Get the definition from the shared parse.**
  `_corpus.function_definition(fn, mentioning=...)` returns the cached AST node
  that defines `fn`; `inspect.getsource` plus `parse_inline` re-reads the file
  and parses each function a second time. With `mentioning`, a module that
  contains none of the fragments is skipped unparsed (TB-13-008).
  `_corpus.source_of(path)` gives a `(path, tree)` holder the cached text.
- **Pause the collector around an AST-heavy derivation.** Each allocation
  threshold during a large parse triggers a collection that walks the whole
  pytest heap. `@_corpus.gc_paused()` on the derivation, plus a per-process
  `functools.cache`, leaves every test after the first at nil cost, which is
  what TB-13-004's 0.5 s tier measures. The first reader pays the derivation,
  which TB-13-004 holds to its 10 s tier instead: one that parses a few hundred
  modules costs seconds. State the measured figure in the module docstring
  (`_guard_reachability.py`).

To find the names that *may* reach a target without parsing, use
`_corpus.names_reaching(seeds, under=...)`: a text-only fixed point that follows
top-level import and assignment aliases. Pass `classes=False` to follow functions
only, because a class span holds every method, so one matching method would make
every caller of the class match. Then parse only the candidate modules
(`_corpus.paths_under`, `_corpus.tree_of`). Prefiltering files by *mentioning* a
class name instead parses every module that imports one.
`_ledger_commit_inventory.py` is the worked example.

## Prefilter Per Definition, and Only for the Arm That Needs It

TB-13-002's substring prefilter applies inside a file too. A ratchet that
judges each function by walking its own scope pays that walk for every
definition in every matched file, and most of them cannot match: testing the
fragment against the definition's own source span first
(`lineno`..`end_lineno`) measurably cut the guard-reachability derivation.
The span includes any nested definition, so the prefilter only ever
admits a candidate the walk then judges.

Give each arm the prefilter it needs, not the strictest one. The same
derivation's second arm looks for a parameter that gates a *delegated*
refusal, so a `raise` fragment in the span is the wrong test — it skipped the
only function the ratchet exists to catch. A `None` default read off the
signature costs no walk and is the necessary condition there
(`_guard_reachability.py`, #3156).

## A Coverage-Shape Arm Keyed on Spec Markers Has No Subjects Here

Do not re-propose this one without re-measuring. The guard-reachability
ratchet was asked for a second shape: for a guard raising a spec-cited error,
require one test reaching it *through* its production entry point rather than
by direct call. Keyed on `@pytest.mark.spec` — a requirement whose markers all
sit on test functions that name the private guard — it finds no subjects in
this repo and costs tens of seconds, so it can only ever pass. Keyed on
`names_reaching` instead, a class span carries every method, so the reacher set
grows until every guard reads as covered. The rule is real and is recorded as a
test-authoring rule in [testing-pitfalls](testing-pitfalls.md) § "Drive a Guard
Through Its Production Entry Point"; what has no structural form is the check
(#3156).

## Say, Per Loose Reading, Whether It Can Miss or Invent

A ratchet reading source by name rather than by binding is imprecise in both
directions, and the two directions are not equally safe: a reading that **misses**
a violation costs coverage, while one that **invents** one fails correct code and
gets the ratchet switched off. List each loose reading in the module docstring
with its direction, and narrow every reading that can invent. A docstring that
claims one-sidedness for all of them stops anyone looking.

Where a reading cannot be narrowed without resolving bindings or intent, say so
rather than dropping it from the list, and say whether the package holds an
instance today: a reader meeting a red arm needs to know which of its subjects
were never the thing the arm names. Where a reading that invents can be traded
for one that misses, trade it: arm B of the guard-reachability derivation counts
a delegated refusal only when the branch hands the gating parameter itself to a
callee that tests it, so a refuser handed a derived value now reads as refusing
nothing rather than an optional step reading as a gate
(`_guard_reachability.py`, #5896).

## Key a Ratchet on the Act, Not on the Name of What Performs It

A ratchet that selects its subjects by an implementation name — a
`_phase_<x>` function, a class, a module — covers only the code that still
carries that name, so refactoring the name away removes subjects silently:
the non-empty guard still passes on whatever is left. Select on the act
instead, the call or the state the requirement is actually about, which
survives every rename and reaches a second shape of the same code. The
ADR-0053 non-party-broadcast ratchet selected on `def _phase_ownership_handoff(`
and would have narrowed from two scenarios to one the moment one of them was
written as a story fragment; keyed on the offer trigger it covers both
(#5535, `test/architecture/test_handoff_scenarios_verify_broadcast.py`).

A guard on "the subject set is non-empty" is not enough for the same reason:
it cannot tell one subject from two. A ratchet whose subjects come in known
shapes asserts something per shape, so retiring an arm is a deliberate edit
(#5535): **each shape is still found** while both are live, and, once a
migration has emptied one, **that shape is found no more** — which is what
`test_demo_scenario_waits_in_demo_context.py` and
`test_handoff_scenarios_verify_broadcast.py` now assert for their `_phase_*`
arms, every scenario being written as composition (#5536). Flipping the arm
beats deleting it: the scan still covers the shape, so one written again is
reported rather than silently exempt.

When the subject is a value rather than a call, the act is its construction:
the story-prop ratchet selects every `StoryProp(...)` call under
`vultron/demo/`, so a renamed constant, a renamed family module or a module
split moves no subject out of the scan. Pair that with failing a construction
that is *not* a module-level constant, and the enumeration is complete rather
than best-effort: every construction is then either a subject the arms check
or a failure (#5598).

Flipping is for an arm whose act is still forbidden. When a rule change
abolishes the property a name-keyed baseline measured, delete that baseline and
let the shape scan that replaced it carry the coverage: an inverted set asserts
the old property still holds, which the new rule has made false.
`KNOWN_SECOND_AUTHORITY_ASKERS` listed the classes that answered "is this actor
the case authority" besides the one sanctioned node, so inverting it would have
asserted that no other class asks — while ARCH-24-008 makes several of them
correct askers and the replacement's own compliant-asker control requires them
to exist (#5784, #5921). What must survive the deletion is the act's coverage in
both polarities: a shape scan with a control per shape, a permanently non-empty
subject scan, and a permanently non-empty set of compliant callers.

## Check a Ratchet's Goal State Against the Spec Corpus Before Adding the `xfail`

A goal state that MUST-level requirements make impossible is a test that can
never pass. Target the declared exemption set, not empty, and enumerate each
exemption with the requirement that mandates it (ARCH-22-003,
[notes/wire-core-boundary.md](wire-core-boundary.md)).

## Every Non-Empty Baseline Names an Owner

A ratchet baseline records *what* is exempt, not *who* retires it, so when the
issue behind it closes with entries left, the debt goes unseen. Each non-empty
baseline carries a comment (ARCH-18-003):

- `# owner: #N` — the open issue that drives it to its terminal value (empty
  set, or the ceiling's floor).
- `# permanent: <reference>` — the issue, ADR, or spec requirement that made it
  permanent by design. A permanent marker that cites nothing fails.

What the offline check
(`test/architecture/test_ratchet_baselines_name_an_owner.py`) enforces, through
the one marker parser `vultron/metadata/ratchet_markers.py`:

- **Which constants.** Module-level constant-case names matching `KNOWN_*`,
  `*_BASELINE`, `MAX_*` or `*_EXEMPTIONS` (leading underscores ignored)
  anywhere under `test/`, including inside import-time `if`/`for`/`while`/
  `try`/`with`/`match` blocks and (nested) tuple or list unpacking. A constant
  with a ratchet name that is not a baseline (a search depth, a fixture host
  list) is renamed out of the pattern rather than given an invented marker.
  The check finds baselines only by name, so a real baseline named otherwise
  (a `*_BACKLOG`) is renamed into the pattern, or the rule cannot see it.
- **Terminal needs no marker.** An empty literal, a zero, or an empty
  `frozenset()` / `MappingProxyType({})` call. A computed value, or one grown
  in place at module level (`|=`, `.add()`, item assignment), counts as
  non-empty.
- **Where the marker sits.** A real comment (`#` or `#:`, never text in a
  string) in the comment block touching the assignment's first line, or
  trailing that line; a blank line in between detaches it.
- **What fails.** No marker on a non-empty baseline; `# owner:` without `#N`
  (even on a terminal baseline); `# permanent:` whose line cites no `#N`,
  `ADR-NNNN` or spec ID; both markers on one constant (ARCH-18-005).

Read the markers through `ratchet_markers` (`baselines_in` for a cached parse,
`baselines_in_source` or `scan_paths` without one). The marker check runs offline
in the unit suite, so it gives the same answer every run.

Whether a cited owner is still open is checked by `ratchet-owners`
(`vultron/metadata/ratchet_owners.py`), run daily and on demand by
`.github/workflows/ratchet-baseline-owners.yml` (ARCH-18-004). Rules it keeps:

- **Never fail the build.** The step runs with `continue-on-error`: a hard failure
  would turn `main` red whenever an unrelated issue closes.
- **Fail closed on a lookup.** A missing issue, a merged pull request's number, or
  an unreadable one is listed with the closed ones: a check that cannot see an
  issue has not shown it open.
- **One tracker, through `notify-failure`.** The script writes its list with
  `--report`, and the action's `details-file` input puts it in the issue body or
  update comment; the issue lookup is the shared `gh_issue_state` in
  `vultron/metadata/base.py`, not a second client.

## Ratchets and Pinned Exemption Sets Are Different Things

Both are exact sets checked with bidirectional equality (ARCH-18-001), so the
assertion cannot tell them apart. What differs is whether an end state exists
(ARCH-18-005):

- A **ratchet** has a terminal value — an empty set or a zero ceiling — and an
  `# owner: #N` issue that drives it there. Each entry is a defect awaiting a
  fix. Only ratchets are open debt.
- A **pinned exemption set** has no terminal value and no owner. Each entry is
  exempt by a recorded decision, so the set grows and shrinks with the code. It
  carries `# permanent: <reference>`, and its module says "pinned exemption
  set", not "ratchet" or "backlog".

An entry in a pinned set that *is* awaiting a fix moves to its own ratchet
constant with an owner; do not leave it in the pin. Calling a pin a ratchet
inflates the count of open debt (#3933).
