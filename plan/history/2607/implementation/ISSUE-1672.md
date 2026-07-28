---
source: ISSUE-1672
timestamp: '2026-07-27T15:16:59.074538+00:00'
title: In-process STOCHASTIC bundle demo scenario
type: implementation
---

## Issue #1672 — In-process STOCHASTIC bundle demo scenario with call-out point outcome logging

Added `vultron/demo/fuzzer/stochastic_demo.py` and 4 companion tests in `test/demo/fuzzer/test_stochastic_demo.py`.

The demo exercises STOCHASTIC call-out point bundles across validation, prioritization, and embargo domains in a single in-process run. Each tick logs node name + SUCCESS/FAILURE. The embargo domain additionally runs the full ManageEmbargoBT tree via BTBridge + in-memory SqliteDataLayer.

Satisfies all 6 acceptance criteria including issue #1152 AC-4 (probabilistic fuzzer backend with outcome logging).

PR: <https://github.com/CERTCC/Vultron/pull/1711>
