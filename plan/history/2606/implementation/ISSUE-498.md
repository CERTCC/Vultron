---
source: ISSUE-498
timestamp: '2026-06-22T17:43:53.549898+00:00'
title: Light cleanup of test_two_actor_demo.py
type: implementation
---

## Issue #498 — P7 (optional): Light cleanup of test_two_actor_demo.py

Extracted the repeated `_make_client` helper to `test/demo/_helpers.py` as
`make_client()`, removing identical duplicate definitions from
`test_two_actor_demo.py`, `test_multi_vendor_demo.py`, and
`test_three_actor_demo.py`. Promoted scattered local imports in
`test_two_actor_demo.py` to module level (`call`, `patch`, `CliRunner`,
`demo.cli.main`, wire `VulnerabilityCase`) and removed one redundant
local re-import of `make_testclient_call`. No structural reorganisation;
file remains a single module.

Full suite: 3691 passed, 37 skipped, 5 xfailed. All linters clean.

PR: [#1101](https://github.com/CERTCC/Vultron/pull/1101)
