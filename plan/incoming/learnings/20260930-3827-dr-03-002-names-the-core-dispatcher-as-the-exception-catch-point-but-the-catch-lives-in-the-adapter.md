---
title: DR-03-002 says `DirectActivityDispatcher` catches and logs handler exceptions at ERROR, but the core dispatcher lets them propagate — the catch lives one layer up in the FastAPI inbox handler
type: learning
timestamp: 2026-09-30T18:30:00Z
source: ISSUE-3827
signal: spec-contradiction
---

While giving every handler-protocol (HP) requirement a real, cited
`verification:` clause, the spec backstop pulled in DR-03 because the new
dispatcher tests name `DirectActivityDispatcher`. DR-03-002 reads:

> The DirectActivityDispatcher MUST catch and log handler exceptions at ERROR
> level

`vultron/core/dispatcher.py` does not do this. `DispatcherBase._handle()` catches
exactly one type — `UnroutableActivityError`, which it logs at ERROR and turns
into a `REFUSED` verdict — and lets every other handler exception propagate.
`test_dispatch_rejects_a_use_case_that_returns_no_handler_result` in
`test/test_behavior_dispatcher.py` depends on that propagation: it asserts a
`TypeError` *escapes* `dispatch()`.

The catch-and-log-at-ERROR behaviour DR-03-002 describes exists, but in the
driving adapter: `vultron/adapters/driving/fastapi/inbox_handler.py` wraps the
dispatch call in `except VultronProtocolViolationError` / `except Exception`
arms that log at ERROR and decide whether to re-queue (#2865). That placement is
the deliberate one — a blanket catch in core would collide with CS-23-001 (no
broad `except` outside a BT node's `update()`) and with HP-05-001 (handlers
raise for unrecoverable errors).

So DR-03-002 names the wrong component, and it carries no `verification:`
clause (nor does DR-03-001), so nothing ever noticed. Neither was touched by the
HP-scoped work in #3827. The requirement should either be restated as an
adapter-boundary obligation (the inbox handler catches, logs at ERROR, and
re-queues or drops) with a clause naming the `inbox_handler` tests that show
it, or be removed per MS-09-001 as superseded by the inbox-pipeline
requirements that already govern that boundary.
