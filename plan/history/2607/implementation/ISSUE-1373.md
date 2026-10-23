---
source: ISSUE-1373
timestamp: '2026-07-14T17:44:55.844705+00:00'
title: add per-function unit tests for all six actor vocab example functions
type: implementation
---

## Issue #1373 — test: add per-function unit tests for all six actor vocab example functions

Added `test/wire/as2/vocab/test_vocab_actor_examples.py` with 32 unit tests
covering all six actor vocab example functions: `recommend_actor`,
`accept_actor_recommendation`, `reject_actor_recommendation`,
`offer_case_participant`, `accept_case_participant_offer`, and
`reject_case_participant_offer`. Each test class asserts return type, `actor`
field, `to` field, and `object_` reference. All 4679 unit tests pass;
Black/flake8/mypy/pyright clean.

PR: <https://github.com/CERTCC/Vultron/pull/1417>
