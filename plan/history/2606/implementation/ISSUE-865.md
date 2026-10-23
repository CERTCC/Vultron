---
source: ISSUE-865
timestamp: '2026-06-22T20:03:48.693341+00:00'
title: 'FUZZ-06: Port publication workflow fuzzer nodes'
type: implementation
---

## Issue #865 — FUZZ-06: Port publication workflow fuzzer nodes to vultron/demo/fuzzer/report_management/publication.py

Ported all 14 publication workflow fuzzer nodes from the legacy
`vultron/bt/report_management/fuzzer/publication.py` to the new demo layer
at `vultron/demo/fuzzer/report_management/publication.py`.

Each node is a proper py_trees `Behaviour` subclass using base types from
FUZZ-01, with a full semantic docstring covering semantic function, input
category, success probability, and automation potential (BT-16-003, BT-16-005).

Nodes ported: `AllPublished`, `PublicationIntentsSet`,
`PrioritizePublicationIntents`, `Publish`, `NoPublishExploit`, `ExploitReady`,
`PrepareExploit`, `ReprioritizeExploit`, `NoPublishFix`, `PrepareFix`,
`ReprioritizeFix`, `NoPublishReport`, `PrepareReport`, `ReprioritizeReport`.

Re-exports added to `vultron/demo/fuzzer/report_management/__init__.py` and
`vultron/demo/fuzzer/__init__.py`. 98 unit tests added in
`test/demo/fuzzer/report_management/test_publication.py`.

All 4261 tests pass; Black, flake8, mypy, pyright clean.

PR: [#1116](https://github.com/CERTCC/Vultron/pull/1116)
