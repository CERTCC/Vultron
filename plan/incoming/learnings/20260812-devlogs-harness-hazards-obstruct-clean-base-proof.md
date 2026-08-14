---
title: Tooling — devlog accumulation and a hardcoded /app default make the mandated clean-base proof actively hazardous
type: learning
timestamp: 2026-08-12
source: ISSUE-2232
signal: tooling-issue
---

`completeness-doctrine.md` requires proving a test failure pre-existing on a
clean `origin/main` before classifying it as not branch-owned. Two properties
of the demo/invariant harness fight that requirement. Both are filed as #2273.

**1. `DEVLOGS_DIR` defaults to a hardcoded absolute path.**
`vultron/demo/scenario/fv_demo.py:898` reads
`os.environ.get("DEVLOGS_DIR", "/app/devlogs")`. A demo run from any other
checkout — a git worktree, a second clone, CI — writes into `/app/devlogs`
rather than its own tree. My first attempt at the clean-base proof produced no
devlogs in the worktree at all and instead **overwrote the artifacts of the
branch I was comparing against**. The tool for establishing a clean baseline
destroys the baseline. `vultron/demo/report.py:66` already resolves this
repo-root-relative, so the fix pattern exists in-tree.

**2. Devlogs accumulate across runs and corrupt hash-chain assertions.**
`devlogs/` is gitignored and demo runs append rather than replace, so three
runs left three case-ledger files per actor. `load_devlogs()` concatenates
every `*-case-ledger.jsonl` for an actor, chaining entries from unrelated
cases, and `test_invariant_1_local_hash_chain_consistent` then reports a
mismatch at every logIndex for every actor.

That second one is the dangerous one: three actors failing hash-chain
continuity at every index reads as a serious integrity regression. It cost real
time to recognise as an artifact of leftover files. The invariant suite should
either scope per `case_id` or require a clean `devlogs/` directory and say so
when it isn't.

**Bearing on this session:** after clearing `devlogs/` and regenerating, three
of the four failures vanished. The fourth,
`test_invariant_5_expected_event_types_present[validate_report]`, reproduced
byte-identically on a clean `origin/main` worktree and is genuinely
pre-existing — see #2273 and the cross-reference on #2266.
