---
title: fv Demo Integration has a class of async race windows beyond genesis-unavailable
type: learning
timestamp: 2026-07-31
source: ISSUE-1873
signal: concern
---

ISSUE-1873 fixed the genesis-unavailable race (Announce arrives before Create/VulnerabilityCase is seeded on the Finder replica).  The demo checkpoint `wait_for_case_on_container` reduces flakiness for that specific window.

However, HTTP BackgroundTasks delivery is inherently unordered and the demo relies on `time.sleep`-based polling loops (`wait_for_contiguous_ledger_coverage`, etc.) to absorb timing jitter.  Other orderings — e.g. multiple CaseLedgerEntry Announces arriving before a non-genesis predecessor is committed — can still trigger CLP-08-005 or hash-mismatch retries that exceed the polling timeout.

Candidate follow-up: review all `wait_for_*` polling loops in `fv_demo.py` for whether their timeouts are sized correctly relative to worst-case BackgroundTasks delivery latency, and whether additional per-step checkpoints would catch failures faster.
