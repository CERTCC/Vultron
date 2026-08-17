---
title: caplog captures records from a test's setup phase, not only the at_level() block
type: learning
timestamp: 2026-08-05T00:00:00Z
source: ISSUE-1988-caplog-setup
signal: tooling-issue
---

`caplog.at_level(...)` sets a level; it does **not** scope capture to the
`with` block. Records emitted earlier in the same test — including arrange-phase
calls made before the block — are already in `caplog.records` when the
assertions run.

This produced two tests in ISSUE-1988 that passed in isolation and failed in the
full suite. Both asserted on "the first narrative record", but their arrange
phase drove the state machine forward a step or two first:

```python
update_participant_rm_state(case, actor, RM.RECEIVED, dl)   # arrange — logs!
update_participant_rm_state(case, actor, RM.VALID, dl)      # arrange — logs!
with caplog.at_level(logging.INFO, logger=NAME):
    update_participant_rm_state(case, actor, RM.ACCEPTED, dl)
records[0]  # ← the START → RECEIVED line from arrange, not the assertion target
```

The order-dependence is what makes it nasty: in isolation the arrange-phase
records were below the effective level and never captured, so the test was
green. Once an earlier test in the session had raised the level on that logger,
they *were* captured and `records[0]` silently became the wrong record.

**Fix:** call `caplog.clear()` immediately before the `at_level()` block that
the assertion targets, whenever the arrange phase exercises the same logger.

Corollary for tests asserting *absence* (`assert not records`): these are the
most exposed, since any arrange-phase record makes them fail. Always clear
first.

**Promoted**: 2026-08-17 — captured in AGENTS.md pitfall: caplog captures fixture-setup-phase records.
Docs PR: <https://github.com/CERTCC/Vultron/pull/2330>.
