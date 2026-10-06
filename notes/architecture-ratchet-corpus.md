---
title: Architecture Ratchet Corpus
status: active
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

Design decisions and measurements for the shared corpus pattern in
`test/architecture/`. Normative requirements are in
`specs/testability.yaml` TB-13. Why a new baseline should be a named set or a
per-item marker, never a bare count pinned to its live value, is in
[testing-pitfalls](testing-pitfalls.md) § "A Two-Sided Count Pin Races Every
Concurrent PR".

---

## Key Timeout Measurement

The `pytest-timeout` setting of `timeout = 5` (configured in
`pyproject.toml`) covers:

- ✅ **test function call time** — covered
- ✅ **fixture setup time (session, module, function scope)** — covered
- ❌ **module import time** — **exempt** (verified experimentally)

This means a module-level corpus (read at import time) is not subject to
the per-test timeout. A session-scoped fixture is subject to it, and a
cold parse of all 1 179 files (~2.3 s) would recreate exactly the margin
problem it was meant to fix.

## Meta-Ratchet

`test/architecture/test_ratchet_hygiene.py` enforces the pattern by
failing when any sibling file contains `ast.parse(` or `.rglob(` outside
of `_corpus.py`. This makes the shared-corpus requirement self-enforcing.

## The Markdown Tier

The corpus also caches `docs/**/*.md` text, for ratchets that assert
documentation prose against code. Accessors are `docs_mentioning(*fragments)`
and `all_docs()`, mirroring `sources_mentioning` / `all_sources`.

There is **no lazy tier for markdown**, because these ratchets match on text
and never parse. The whole cache is populated at import time: 564 files and
2.8 MB read in ~0.03 s, an order of magnitude cheaper than the Python cold
parse that motivated the lazy AST tier.

**No directory is excluded.** An earlier version of this tier skipped any path
component named `codebase`, on the theory that it held a gitignored scan
artifact whose embedded `search_index.json` would dominate the byte count and
produce false matches on retired content. That reasoning was wrong twice over,
and both errors are worth recording because they are easy to repeat. The
artifacts are `.codebase-scan.txt` files, so a `*.md` glob never sees them and
the byte-count argument cannot apply. What the exclusion actually dropped was
the eight **tracked, authored** reference pages under `docs/reference/codebase/`
— and `test_codebase_docs_paths.py`, which reads exactly those eight files, is
the obvious candidate to migrate onto `all_docs()`, so the migration would have
turned it silently vacuous. Match on the path *relative to* the scan root if a
future exclusion is ever genuinely needed: the old check tested `Path.parts` of
the absolute path, so a clone under any directory named `codebase` emptied the
entire cache.

`UnicodeDecodeError` is not an `OSError`, and this loop runs at import time, so
the read is guarded against both. Letting one escape would error out every
ratchet module at collection rather than skipping a single file.

The markdown tier exists because the meta-ratchet forbids `.rglob(` in
siblings, and the first docs-versus-code ratchet
(`test_docs_activity_verbs.py`, ISSUE-3402) needed to walk `docs/`. Extending
the corpus was the correct response to that ratchet rather than reaching for a
glob spelling it does not pattern-match: the hygiene rule is about routing
discovery through one cache, not about the literal substring.

Note the spec gap: TB-13-003 is what *forces* routing through the corpus, but
TB-13-001 scopes the shared corpus to tests "that scan the source tree," and no
TB-13 entry governs `docs_mentioning` / `all_docs`. The markdown tier is
currently convention rather than requirement.

Prefilter markdown ratchets the same way as Python ones. The activity-verb
ratchet filters on `"subgraph as:"` and `` "(`as:" ``, which selects 9 of 564
files.

## xdist Compatibility

`pytest-xdist` is a declared dependency (`pyproject.toml`) but not
currently enabled in CI or local runs. Enabling `-n auto` could reduce
full-suite wall-clock by 50–70% on multi-core runners.

Known xdist hazards in this codebase:

- `py_trees.blackboard.Blackboard.storage` is a process-global dict.
  Tests that do not reset it (some BT tests) would race under parallel
  execution.
- Module-level singletons used by some demo tests (e.g., actor
  configuration globals).

A compatibility audit (TB-13-005) is a prerequisite before enabling xdist.

## Spec Requirements

See `specs/testability.yaml` TB-13-001 through TB-13-005.

## Related

- CONCERN-2020 — source issue
- `test/architecture/_corpus.py` — the shared corpus module
- `test/architecture/test_ratchet_hygiene.py` — the meta-ratchet
- `notes/flaky-tests.md` — tracking issue for known-flaky tests

## Check a Ratchet's Goal State Against the Spec Corpus Before Adding the `xfail`

The ARCH-22 goal test asserted `vultron/wire/` could reach zero
`vultron.core.models` imports, which three MUST-level requirements made
impossible (ARCH-12-001, ARCH-12-010, and formerly ARCH-20-002). Target the
declared exemption set, not empty, and enumerate each exemption with the
requirement that mandates it. See ARCH-22-003 and
[notes/wire-core-boundary.md](wire-core-boundary.md).

Source: CONCERN-2830

## Every Non-Empty Baseline Names an Owner

A ratchet baseline records *what* is exempt, not *who* retires it. When the
issue that created a baseline closes with entries left, the test stays green and
the debt goes unseen (CONCERN-3927). ARCH-18-003 closes that gap with a comment
beside each baseline:

- `# owner: #N` — the open issue that drives the baseline to its terminal
  value (empty set, or the ceiling's floor).
- `# permanent: <reference>` — the issue, ADR, or spec requirement that made the
  baseline permanent by design. A permanent marker that cites nothing fails. The
  ratchet-versus-pinned-exemption-set split is ARCH-18-005; see the next section.

Two checks, split by what they need:

- **Offline, in the unit suite.** Scans `test/` for ratchet-named constants and
  fails when a non-empty one has neither marker. It never calls GitHub, so it
  gives the same answer on every run.
- **Online, outside the merge path (ARCH-18-004).** A scheduled CI job asks
  GitHub whether each cited owner is still open and files or updates one tracking
  issue when one is closed. It does not fail the build. A hard failure would turn
  `main` red when an unrelated issue closes — the same race as a two-directional
  count pin, where two pull requests that are each green land together and
  `main` goes red (`plan/history/2609/learning/ISSUE-3828.md`).

MS-10-006 is the precedent: the spec-corpus ceiling table in
`vultron/metadata/specs/verification.py` already requires an owner per non-zero
ceiling, but checks only that one is named, not that it is still open.

## Ratchets and Pinned Exemption Sets Are Different Things

Both are exact sets checked with bidirectional equality (ARCH-18-001), so a
reader cannot tell them apart from the assertion. What differs is whether an
end state exists (ARCH-18-005):

- A **ratchet** has a terminal value — an empty set or a zero ceiling — and an
  `# owner: #N` issue that drives it there. Each entry is a defect awaiting a
  fix. Only ratchets are open debt.
- A **pinned exemption set** has no terminal value and no owner. Each entry is
  exempt by a recorded decision, so the set grows when a new site falls under
  that decision and shrinks when a site goes away. It carries
  `# permanent: <reference>` (ARCH-18-003), and its module says "pinned
  exemption set", not "ratchet" or "backlog".

Several sets began as shrinking backlogs and were later decided to be permanent,
but their files still called them ratchets, so a count of open debt included
them (#3933). Their entries vary with the code, so this table names the
decision rather than a count (MS-16-001):

| Constant | File | Why it is a pin |
|---|---|---|
| `_RM_FORCE_QUARANTINE` | `test_participant_status_validation.py` | bootstrap writes of a first status, which has no predecessor for the RM adjacency rule (BTND-10-001); closure never forces (RMB-14-005, #3106) |
| `_DECLARED_EXCLUSIONS` | `test_participant_status_validation.py` | ADR-0089 end state: two writer exclusions (receive and replica-apply paths) plus the permanent non-writer over-catch |
| `_DECLARED_EXCLUSIONS` | `test_no_broad_except_outside_bt_update.py` | framework, bridge and persistence boundaries, each justified inline (CS-23-001) |
| `KNOWN_ALLOWLIST` | `test_case_resolution_uses_helpers.py` | the ADR-0087 regime exceptions |
| `AUDITED_SITES` | `test_vfd_rm_pxa_write_sites.py` | the list *is* the BTND-10-001 audit |
| `BLANK_SENTINEL_FIELDS` | `test_core_reference_fields_reject_blank.py` | documented "not yet" sentinels (CS-08-001, #3877) |
| `_SANCTIONED_SHADOWS` | `test_vocab_registry_keys.py` | the enumerated `as_Vultron*` exception (VM-01-008) |

The writer exclusions in `test_participant_status_validation.py` looked like
candidates for a separate ratchet. They are not: ADR-0089 names the receive path
and the replica-apply path as its deliberate end state, dispositions the emit
evaluator must not apply (ADR-0061, RSH-05-021). An entry that *is* awaiting a fix leaves the pinned set
for its own ratchet constant with an owner.
