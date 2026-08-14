---
title: load_devlogs case_id filtering has no DEMOCI spec entry
type: learning
timestamp: 2026-08-13
source: ISSUE-2273
signal: spec-gap
---

`load_devlogs` in `test/ci/invariants/common.py` now filters entries by the
manifest `caseId` when a manifest is present. Without this filter, accumulated
JSONL files from multiple local demo runs chain entries from different cases and
break `test_invariant_1_local_hash_chain_consistent`.

The new behaviour (scope to the manifest's `caseId`) is not covered by any
existing DEMOCI or DEMOMA spec entry. DEMOCI-10 covers manifest-presence
detection; DEMOMA-17-001 covers `_DEVLOGS_DIR` resolution. Neither addresses
multi-run accumulation or per-case scoping.

A spec entry is needed under DEMOCI-10 or a new DEMOCI-11 group to formalise
the invariant: "when a manifest is present with a non-null `caseId`, `load_devlogs`
MUST restrict returned entries to that `caseId`."
