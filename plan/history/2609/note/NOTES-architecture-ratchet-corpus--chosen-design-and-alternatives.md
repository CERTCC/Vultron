---
source: NOTES-architecture-ratchet-corpus--chosen-design-and-alternatives
timestamp: '2026-09-17T17:10:50.567189+00:00'
title: 'Ratchet corpus: Chosen Design and Alternatives Considered'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered
**Superseded by:** test/architecture/_corpus.py, test_ratchet_hygiene.py

---

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
