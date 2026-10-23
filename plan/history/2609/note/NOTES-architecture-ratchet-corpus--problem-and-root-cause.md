---
source: NOTES-architecture-ratchet-corpus--problem-and-root-cause
timestamp: '2026-09-17T17:10:50.292317+00:00'
title: 'Ratchet corpus: Problem and Root Cause'
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) shared-corpus pattern delivered; rests on stale 5s-timeout premise (now 30s)
**Superseded by:** test/architecture/_corpus.py, test_ratchet_hygiene.py (#2270)

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
