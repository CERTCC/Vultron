---
source: ISSUE-6727-blackboard-client-release
timestamp: '2026-11-20T20:24:23.694400+00:00'
title: Tree runs release their blackboard clients; rv demo worker growth bounded
type: implementation
---

Issue: #6727. PR: https://github.com/CERTCC/Vultron/pull/6793

Symptom: in large loaded local gates, xdist workers running in-process demo
tests (`test_rv_demo.py`, `test_pcr_late_joiner.py`) died with "node down: Not
properly terminated". The cgroup oom_kill count rose during those runs.

Root cause: py_trees keeps every blackboard `Client` in process-global maps
(`Blackboard.clients` and each key's metadata reader/writer sets) until it is
unregistered, and collecting the `Client` object does not remove it. Nothing
in Vultron unregistered. Every tree run therefore left one entry per node,
about 5,000 clients per rv workflow test (25,830 after five tests). Measured
alone with `-n 0`, `test_rv_demo.py` peaked at 1018 MB, 765 MB at its first
test, of which 588 MB is the app import.

Fix (BT-25-004): `BTBridge.execute_with_setup` (including its setup failure
and leadership-skip paths) and the inbox `process_payload` release the run's
clients with `clear=False`. They use a release of their own, because py_trees'
`unregister()` raises `KeyError` when two ports share one blackboard key.
`SettleReceivedOutcome` now attaches its client to its node.

Guards: a per-test registry check on demo tests outside `test/demo/fuzzer/`,
and a 210 MiB peak-growth budget on `test_rv_demo.py`.

After the fix: peak 917 MB, and the file's growth fell from at least 253 MiB
to 165 MiB.

Left over: one loaded-gate worker death (the recorder smoke test,
oom_kill 67 to 68) was reported, not rerun; CI is the loaded check. #6554
keeps its ratchet and fixture ACs.

