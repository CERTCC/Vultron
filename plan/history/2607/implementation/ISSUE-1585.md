---
source: ISSUE-1585
timestamp: '2026-07-22T20:05:32.279755+00:00'
title: Audit integration test script against current scenario set
type: implementation
---

## Issue #1585 — chore: audit integration_tests/demo/run_multi_actor_integration_test.sh against current scenario set

Updated VALID_SCENARIOS from stale `three-actor`/`multi-vendor`/`two-actor` to the current CI-tested set (`fv fvv fvcv-extension fvcv-handoff`). Also updated Makefile targets, integration_tests/README.md scenario table, and docker/README.md integration test section.

PR: <https://github.com/CERTCC/Vultron/pull/1622>
