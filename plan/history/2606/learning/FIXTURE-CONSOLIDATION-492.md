---
source: FIXTURE-CONSOLIDATION-492
timestamp: '2026-06-22T19:36:53.087741+00:00'
title: 'Fixture consolidation: test_trigger_actor.py has 3 fixture variants per use
  case'
type: learning
---

`test_trigger_actor.py` grew to have 3+ fixture variants per use case class
(base, with embargo, with CASE_MANAGER) that are nearly identical. A
parameterized fixture factory reducing this to a single parametrized fixture
per use case would cut the file by ~60% and make new use-case tests easier
to add correctly.

**Promoted**: 2026-06-22 — created GitHub issue #1108 to track the
`test_trigger_actor.py` fixture cleanup. No immediate code change.
Docs PR: <https://github.com/CERTCC/Vultron/pull/1112>.
