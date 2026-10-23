---
source: CONCERN-2020
timestamp: '2026-08-06T17:47:32.472902+00:00'
title: AST-walking architecture ratchets sit near the 5s per-test timeout and fail
  non-deterministically under full-suite load
type: learning
---

Several architecture ratchets parse every file under `vultron/` with `ast`
and run close to the repo's 5s per-test timeout. Under full-suite load one
of them times out non-deterministically — a different test on each run —
which is the signature of a load-dependent margin rather than a specific
slow test.

Measured in isolation: `test_activity_factory_imports.py::test_vocab_activities_boundary`
~3.4s; `test_no_asgi_transport_in_app_code.py` ~1.9s;
`test_core_no_adapter_imports.py` ~1.2s. Full-suite wall-clock profiled at
~170s (demo=46s, core=30.8s, metadata=27.7s, architecture=10.4s).

Root cause: each ratchet calls `rglob` + `ast.parse` independently inside
the test function body, which is inside the 5s timeout window.
Module-import time is exempt.

**Resolved**: 2026-08-06 — implementation tracked in #2038 (shared corpus +
meta-ratchet), #2039 (xdist audit), #2040 (metadata spec-dump cost as
separate concern).
Docs PR: <https://github.com/CERTCC/Vultron/pull/2037>.
Spec: `specs/testability.yaml` TB-13-001..005.
Notes: `notes/architecture-ratchet-corpus.md`.
