---
title: Architecture Ratchet Corpus
status: active
related_notes:
  - notes/wire-core-boundary.md
---

# Architecture Ratchet Corpus

Design decisions and measurements for the shared corpus pattern in
`test/architecture/`. Normative requirements are in
`specs/testability.yaml` TB-13.

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
