---
title: "spec_corpus marker + architecture ratchet preferred over path enumeration for CI coverage of spec-reading tests"
type: learning
timestamp: "2026-08-31"
source: ISSUE-2903
signal: design-question
---

When spec-reading tests were missing from `spec-check.yml` (Bug #2903), two fix
options existed:

1. **Path enumeration**: add `specs/**` to `python-app.yml` `paths:` filter so
   every spec-only PR triggers the full pytest run.

2. **Pytest marker + ratchet**: add `@pytest.mark.spec_corpus` to tests that
   read from `specs/`, add a `spec-tests` job to `spec-check.yml` that runs
   only those tests, and add an architecture ratchet that enforces the marker
   on any future spec-reading test.

**Decision**: Option 2 was chosen because Option 1 only catches up to the
current set of tests and allows drift — a new test added without the marker
would again go uncovered on specs-only PRs. Option 2 is self-enforcing: the
ratchet (`test/architecture/test_spec_corpus_marker.py`) fails the next time
someone adds a spec-reading test function without the marker, before it ever
reaches a specs-only PR.

**How to apply**: whenever a CI trigger omits a file-change path, prefer a
marker + ratchet pattern over path enumeration. The marker documents the
dependency at the call site; the ratchet enforces it structurally.
