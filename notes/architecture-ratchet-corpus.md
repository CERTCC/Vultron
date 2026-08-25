---
title: Architecture Ratchet Corpus
status: active
---

# Architecture Ratchet Corpus

Design decisions and measurements for the shared corpus pattern in
`test/architecture/`. Normative requirements are in
`specs/testability.yaml` TB-13.

---

## Problem

`test/architecture/` contains ~18 files that enforce architectural
boundaries by walking the source tree with `ast`. As of CONCERN-2020
(2026-08-06), the three slowest tests approach or exceed the 5 s per-test
timeout under full-suite load:

| Test | Isolated | Under full-suite load |
|---|---|---|
| `test_vocab_activities_boundary` | 3.8 s | times out non-deterministically |
| `test_no_asgi_transport_in_app_code` | 2.76 s | |
| `test_core_no_adapter_imports` | 0.88 s | |

The full-suite timing profile (all markers, single process):

| Directory | Total time |
|---|---|
| `test/demo` | 46 s |
| `test/core` | 30.8 s |
| `test/metadata` | 27.7 s |
| `test/adapters` | 17.1 s |
| `test/architecture` | 10.4 s |
| others | ~7 s |
| **total** | **~170 s** |

## Root Cause

Each ratchet independently calls `pathlib.Path.rglob("*.py")` and
`ast.parse()` inside a test function. With ~1 179 Python files across
`vultron/` + `test/`, this means:

- **Read cost**: ~0.25–0.18 s per `rglob` pass (I/O, file system)
- **Parse cost**: ~0.65 s for `vultron/`, ~1.64 s for `test/`
- **Walk cost**: ~0.47–0.71 s per tree walk

Each ratchet pays some or all of those costs independently; the costs are
not shared. Under full-suite load the reads compete for disk I/O and
CPU time, pushing already-marginal tests over the 5 s ceiling.

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

## Chosen Design: Module-Level Source Cache + Lazy AST Cache

`test/architecture/_corpus.py` reads all `*.py` source files at import
time (import-time cost ~1 s, memory ~18 MB). ASTs are cached lazily on
first demand. Each ratchet:

1. Calls `_corpus.files_mentioning(*fragments, under=root)` which uses a
   plain `in` substring check (~1 µs per file) to filter before calling
   `ast.parse()`.
2. Receives an iterator of `(path, ast.AST)` pairs for matching files
   only.

Measured after applying the shared corpus + prefilter to
`test_vocab_activities_boundary`:

| Before | After |
|---|---|
| 3.8 s (scans vultron + test, parses all) | 0.13 s (CI-verified) |

For `test_no_asgi_transport_in_app_code` (target string: `"ASGITransport"`):

| Before | After |
|---|---|
| 2.76 s + 0.95 s (two tests, no prefilter) | ~0.003 s (0 matches in vultron/) |

## Alternatives Considered

### Session-scoped pytest fixture

A `@pytest.fixture(scope="session")` that parses all files once was the
original preferred approach (issue body). Rejected because:

- Session-fixture setup is inside the 5 s timeout window.
- A cold parse of all 1 179 files takes ~2.3 s, leaving only 2.7 s before
  timeout, which is the same marginal budget the design is meant to fix.
- Holding all parsed ASTs in memory requires ~211 MB vs ~18 MB for the
  source-string cache.

### Inline substring prefilter (no shared module)

Applying the prefilter in-place to each ratchet (as done in
`test_infrastructure_logs_not_at_info.py`) reduces the worst offenders to
<0.1 s but:

- Duplicates the file-discovery pattern across ~14 files (violates
  CS-22-001 DRY).
- Does nothing to prevent the next ratchet author from writing
  another unfiltered scanner.
- No structural enforcement (no meta-ratchet).

### Raise the per-test timeout for `test/architecture/`

Using `@pytest.mark.timeout(N)` hides cost rather than removing it. Noted
as the weakest option in the issue body; rejected.

## Meta-Ratchet

`test/architecture/test_ratchet_hygiene.py` enforces the pattern by
failing when any sibling file contains `ast.parse(` or `.rglob(` outside
of `_corpus.py`. This makes the shared-corpus requirement self-enforcing.

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
