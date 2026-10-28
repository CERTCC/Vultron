---
title: Architecture Ratchet Corpus
status: active
kind: guidance
description: >
  Rules for the shared source/markdown corpus behind test/architecture/
  ratchets, for ratchets that start from a live object, and for baselines:
  owner markers and the ratchet-versus-pinned-exemption-set split.
related_specs:
  - specs/architecture.yaml
  - specs/testability.yaml
related_notes:
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

## Meta-Ratchet

`test/architecture/test_ratchet_hygiene.py` fails when any sibling file contains
`ast.parse(` or `.rglob(` outside `_corpus.py` (TB-13-003), so every ratchet
routes discovery through the one cache. When a new ratchet needs a file set the
corpus does not offer, extend the corpus rather than reaching for a spelling the
hygiene check does not pattern-match: the rule is about one cache, not the
literal substring.

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
- **Guard reads against `OSError` and `UnicodeDecodeError`** (the latter is not an
  `OSError`). The loop runs at import time, so an escaped error fails collection
  of every ratchet module instead of skipping one file.
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
  `functools.cache`, keeps each test under the TB-13-004 budget.

To find the names that *may* reach a target without parsing, use
`_corpus.names_reaching(seeds, under=...)`: a text-only fixed point that follows
top-level import and assignment aliases. Pass `classes=False` to follow functions
only, because a class span holds every method, so one matching method would make
every caller of the class match. Then parse only the candidate modules
(`_corpus.paths_under`, `_corpus.tree_of`). Prefiltering files by *mentioning* a
class name instead parses every module that imports one.
`_ledger_commit_inventory.py` is the worked example.

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
